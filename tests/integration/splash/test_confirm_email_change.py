"""Integration tests for the anonymous confirm-email-change route.

Covers ``GET /confirm-email-change/<token>`` and the confirm service
(``backend/splash/services/change_email.py``): the pending→live email swap, the
closed-set outcome codes, and the banner-mapping render on BOTH DD-9 paths
(anonymous splash + already-logged-in HOME).
"""

from __future__ import annotations

from typing import Tuple
from unittest import mock
from urllib.parse import parse_qs, urlparse

from flask import Flask, g, url_for
from flask.testing import FlaskClient
from markupsafe import escape
import pytest
from sqlalchemy.exc import IntegrityError

from backend import db
from backend.models.users import Users
from backend.splash.services.change_email import (
    EMAIL_CHANGE_STATUS_ALREADY_CONFIRMED,
    EMAIL_CHANGE_STATUS_INVALID,
    EMAIL_CHANGE_STATUS_QUERY_PARAM,
    EMAIL_CHANGE_STATUS_SUCCESS,
    EMAIL_CHANGE_STATUS_TAKEN,
    build_email_change_banner,
)
from backend.utils.all_routes import ROUTES
from backend.utils.strings.splash_form_strs import LOGIN_FORM
from backend.utils.strings.user_strs import (
    EMAIL_CHANGE_CONFIRM_INVALID,
    EMAIL_CHANGE_CONFIRM_TAKEN,
    EMAIL_CHANGE_SUCCESS,
    EMAIL_CHANGE_SUCCESS_AUTHENTICATED,
)
from tests.models_for_test import valid_user_1
from tests.utils_for_test import get_csrf_token

pytestmark = pytest.mark.splash

_NEW_EMAIL = "new_confirmed@example.com"


def _login_payload() -> dict[str, str]:
    return {
        LOGIN_FORM.USERNAME: valid_user_1[LOGIN_FORM.USERNAME],
        LOGIN_FORM.PASSWORD: valid_user_1[LOGIN_FORM.PASSWORD],
    }


def _status_from_redirect(response) -> str | None:
    """Extract the confirm-outcome code from a 302 redirect's Location header."""
    location = response.headers.get("Location", "")
    query_params = parse_qs(urlparse(location).query)
    values = query_params.get(EMAIL_CHANGE_STATUS_QUERY_PARAM)
    return values[0] if values else None


def _confirm_url(app: Flask, token: str) -> str:
    with app.test_request_context():
        return url_for(ROUTES.SPLASH.CONFIRM_EMAIL_CHANGE, token=token)


def _clear_flask_login_request_cache() -> None:
    """Drop Flask-Login's per-request user cache (``g._login_user``).

    The test harness keeps one app context alive for the whole test, so
    Flask-Login's per-request cache persists across sequential test-client
    requests. Clearing it forces the next request to consult the user_loader
    again, matching production per-request behavior.
    """
    if hasattr(g, "_login_user"):
        delattr(g, "_login_user")


# --------------------------------------------------------------------------- #
# Happy path + DD-3 session invalidation.
# --------------------------------------------------------------------------- #


def test_confirm_valid_token_swaps_email_and_invalidates_sessions(
    app: Flask, register_first_user
) -> None:
    """A valid token + staged pending email swaps the live email, clears
    pending, keeps ``email_validated`` True, bumps ``sessions_invalidated_at``
    (DD-3), and redirects to splash with the SUCCESS code. A session issued
    before the confirm is rejected on its next request."""
    _, registered_user = register_first_user
    user_id = registered_user.id

    # A second client logged in on the still-live (old) email — proves DD-3.
    logged_in_client: FlaskClient = app.test_client()
    csrf_token = get_csrf_token(logged_in_client.get("/").get_data(), meta_tag=True)
    with app.test_request_context():
        login_url = url_for(ROUTES.SPLASH.LOGIN)
        home_url = url_for(ROUTES.UTUBS.HOME)
    assert (
        logged_in_client.post(
            login_url, json=_login_payload(), headers={"X-CSRFToken": csrf_token}
        ).status_code
        == 200
    )
    assert logged_in_client.get(home_url).status_code == 200

    with app.app_context():
        user: Users = Users.query.get(user_id)
        assert user.sessions_invalidated_at is None
        user.stage_email_change(_NEW_EMAIL)
        db.session.commit()
        token = user.get_email_change_token()

    confirm_response = app.test_client().get(_confirm_url(app, token))

    assert confirm_response.status_code == 302
    assert _status_from_redirect(confirm_response) == EMAIL_CHANGE_STATUS_SUCCESS

    with app.app_context():
        refreshed: Users = Users.query.get(user_id)
        assert refreshed.email == _NEW_EMAIL
        assert refreshed.pending_email is None
        assert refreshed.email_validated is True
        assert refreshed.sessions_invalidated_at is not None

    _clear_flask_login_request_cache()
    assert logged_in_client.get(home_url).status_code == 302


# --------------------------------------------------------------------------- #
# Invalid / expired / no-user tokens — never destructive.
# --------------------------------------------------------------------------- #


def test_confirm_expired_token_is_invalid_and_user_not_deleted(
    app: Flask, register_first_user
) -> None:
    """An expired token redirects with INVALID and — unlike the registration
    consume path — leaves the user (and their live email) intact."""
    _, registered_user = register_first_user
    user_id = registered_user.id

    with app.app_context():
        user: Users = Users.query.get(user_id)
        original_email = user.email
        user.stage_email_change(_NEW_EMAIL)
        db.session.commit()
        token = user.get_email_change_token(expires_in=0)

    response = app.test_client().get(_confirm_url(app, token))

    assert response.status_code == 302
    assert _status_from_redirect(response) == EMAIL_CHANGE_STATUS_INVALID
    with app.app_context():
        survivor: Users = Users.query.get(user_id)
        assert survivor is not None
        assert survivor.email == original_email
        assert survivor.pending_email == _NEW_EMAIL


def test_confirm_garbage_token_is_invalid(app: Flask, register_first_user) -> None:
    """A malformed token (jwt DecodeError) redirects with INVALID, not a 500."""
    response = app.test_client().get(_confirm_url(app, "not-a-real-jwt"))
    assert response.status_code == 302
    assert _status_from_redirect(response) == EMAIL_CHANGE_STATUS_INVALID


def test_confirm_wrong_purpose_token_is_invalid_not_500(
    app: Flask, register_first_user
) -> None:
    """A validly-signed but wrong-purpose token — here the user's own
    email-validation JWT, minted with the same SECRET_KEY but carrying the
    VALIDATE_EMAIL claim instead of CHANGE_EMAIL — lacks the claim the confirm
    route reads. verify_token's payload lookup raises KeyError; the service must
    redirect INVALID rather than surface an unhandled 500."""
    _, registered_user = register_first_user
    user_id = registered_user.id

    with app.app_context():
        wrong_purpose_token = Users.query.get(user_id).get_email_validation_token()

    response = app.test_client().get(_confirm_url(app, wrong_purpose_token))

    assert response.status_code == 302
    assert _status_from_redirect(response) == EMAIL_CHANGE_STATUS_INVALID


def test_confirm_token_for_deleted_user_is_invalid_not_500(
    app: Flask, register_first_user
) -> None:
    """DD-2: a token whose embedded username no longer resolves to a row makes
    ``verify_token``'s ``first_or_404()`` raise ``NotFound``; the service must
    catch it and redirect with INVALID rather than surface a 500."""
    _, registered_user = register_first_user
    user_id = registered_user.id

    with app.app_context():
        user: Users = Users.query.get(user_id)
        user.stage_email_change(_NEW_EMAIL)
        db.session.commit()
        token = user.get_email_change_token()
        db.session.delete(user)
        db.session.commit()

    response = app.test_client().get(_confirm_url(app, token))

    assert response.status_code == 302
    assert _status_from_redirect(response) == EMAIL_CHANGE_STATUS_INVALID


# --------------------------------------------------------------------------- #
# Already-confirmed / stale / TOCTOU / race.
# --------------------------------------------------------------------------- #


def test_confirm_no_pending_email_is_already_confirmed_noop(
    app: Flask, register_first_user
) -> None:
    """A replayed token whose user has no pending email is a no-op redirect with
    ALREADY_CONFIRMED — single-use is enforced by the cleared pending email."""
    _, registered_user = register_first_user
    user_id = registered_user.id

    with app.app_context():
        user: Users = Users.query.get(user_id)
        original_email = user.email
        user.stage_email_change(_NEW_EMAIL)
        db.session.commit()
        token = user.get_email_change_token()
        user.pending_email = None  # simulate an already-consumed change
        db.session.commit()

    response = app.test_client().get(_confirm_url(app, token))

    assert response.status_code == 302
    assert _status_from_redirect(response) == EMAIL_CHANGE_STATUS_ALREADY_CONFIRMED
    with app.app_context():
        assert Users.query.get(user_id).email == original_email


def test_confirm_superseded_token_is_invalid(app: Flask, register_first_user) -> None:
    """DD-5: a token minted for one pending email is stale once a *different*
    pending email is staged; confirming with it redirects INVALID, leaves the
    live email unchanged, and does NOT clear the newer pending email."""
    _, registered_user = register_first_user
    user_id = registered_user.id

    with app.app_context():
        user: Users = Users.query.get(user_id)
        original_email = user.email
        user.stage_email_change("first_target@example.com")
        db.session.commit()
        stale_token = user.get_email_change_token()
        user.stage_email_change("second_target@example.com")
        db.session.commit()

    response = app.test_client().get(_confirm_url(app, stale_token))

    assert response.status_code == 302
    assert _status_from_redirect(response) == EMAIL_CHANGE_STATUS_INVALID
    with app.app_context():
        refreshed: Users = Users.query.get(user_id)
        assert refreshed.email == original_email
        assert refreshed.pending_email == "second_target@example.com"


def test_confirm_toctou_email_taken_redirects_taken(
    app: Flask, register_multiple_users
) -> None:
    """TOCTOU: if another account already owns the pending email at confirm
    time, the pending email is cleared, the live email is unchanged, and the
    redirect carries TAKEN."""
    with app.app_context():
        changing_user: Users = Users.query.get(1)
        other_user: Users = Users.query.get(2)
        original_email = changing_user.email
        taken_email = other_user.email
        changing_user.stage_email_change(taken_email)
        db.session.commit()
        token = changing_user.get_email_change_token()

    response = app.test_client().get(_confirm_url(app, token))

    assert response.status_code == 302
    assert _status_from_redirect(response) == EMAIL_CHANGE_STATUS_TAKEN
    with app.app_context():
        refreshed: Users = Users.query.get(1)
        assert refreshed.email == original_email
        assert refreshed.pending_email is None


def test_confirm_integrity_error_race_returns_taken_not_500(
    app: Flask, register_first_user
) -> None:
    """DD-4: if the UNIQUE-constraint race trips on the finalize commit, the
    service rolls back, clears pending, and redirects with TAKEN — never a 500.

    ``side_effect=[IntegrityError, None]`` fails the finalize commit but lets the
    subsequent cleanup commit succeed (mirrors the change-username race test's
    ``mock.patch`` style; setup commits run outside the patch)."""
    _, registered_user = register_first_user
    user_id = registered_user.id

    with app.app_context():
        user: Users = Users.query.get(user_id)
        original_email = user.email
        user.stage_email_change(_NEW_EMAIL)
        db.session.commit()
        token = user.get_email_change_token()

    confirm_url = _confirm_url(app, token)
    integrity_error = IntegrityError(
        "UPDATE Users SET email=...",
        {},
        Exception("duplicate key value violates unique constraint"),
    )

    with mock.patch(
        "backend.splash.services.change_email.db.session.commit",
        side_effect=[integrity_error, None],
    ):
        response = app.test_client().get(confirm_url)

    assert response.status_code == 302
    assert _status_from_redirect(response) == EMAIL_CHANGE_STATUS_TAKEN
    with app.app_context():
        refreshed: Users = Users.query.get(user_id)
        assert refreshed.email == original_email
        assert refreshed.pending_email is None


# --------------------------------------------------------------------------- #
# DD-11 banner mapping — unit + both DD-9 render paths.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "status_code, expected_kind",
    [
        (EMAIL_CHANGE_STATUS_SUCCESS, "success"),
        (EMAIL_CHANGE_STATUS_ALREADY_CONFIRMED, "success"),
        (EMAIL_CHANGE_STATUS_INVALID, "error"),
        (EMAIL_CHANGE_STATUS_TAKEN, "error"),
    ],
)
def test_build_email_change_banner_maps_each_code(status_code, expected_kind) -> None:
    anonymous_banner = build_email_change_banner(status_code, authenticated=False)
    authenticated_banner = build_email_change_banner(status_code, authenticated=True)

    assert anonymous_banner["kind"] == expected_kind
    assert authenticated_banner["kind"] == expected_kind
    if expected_kind == "success":
        # DD-15: the HOME/authenticated path drops the login clause.
        assert anonymous_banner["message"] == EMAIL_CHANGE_SUCCESS
        assert authenticated_banner["message"] == EMAIL_CHANGE_SUCCESS_AUTHENTICATED
    else:
        # Error copy carries no login clause, so authenticated is irrelevant.
        assert anonymous_banner["message"] == authenticated_banner["message"]


def test_build_email_change_banner_none_for_unknown_code() -> None:
    assert build_email_change_banner("", authenticated=False) is None
    assert build_email_change_banner("bogus", authenticated=True) is None


@pytest.mark.parametrize(
    "status_code, expected_message",
    [
        (EMAIL_CHANGE_STATUS_SUCCESS, EMAIL_CHANGE_SUCCESS),
        (EMAIL_CHANGE_STATUS_ALREADY_CONFIRMED, EMAIL_CHANGE_SUCCESS),
        (EMAIL_CHANGE_STATUS_INVALID, EMAIL_CHANGE_CONFIRM_INVALID),
        (EMAIL_CHANGE_STATUS_TAKEN, EMAIL_CHANGE_CONFIRM_TAKEN),
    ],
)
def test_splash_renders_banner_for_status(
    app: Flask, status_code, expected_message
) -> None:
    """DD-9 anonymous path: GET /?email_change_status=<code> renders the banner
    on splash with the login-clause success copy."""
    response = app.test_client().get(
        f"/?{EMAIL_CHANGE_STATUS_QUERY_PARAM}={status_code}"
    )

    assert response.status_code == 200
    assert b"EmailChangeStatusBanner" in response.data
    assert str(escape(expected_message)).encode() in response.data


@pytest.mark.parametrize(
    "status_code, expected_message",
    [
        (EMAIL_CHANGE_STATUS_SUCCESS, EMAIL_CHANGE_SUCCESS_AUTHENTICATED),
        (EMAIL_CHANGE_STATUS_ALREADY_CONFIRMED, EMAIL_CHANGE_SUCCESS_AUTHENTICATED),
        (EMAIL_CHANGE_STATUS_INVALID, EMAIL_CHANGE_CONFIRM_INVALID),
        (EMAIL_CHANGE_STATUS_TAKEN, EMAIL_CHANGE_CONFIRM_TAKEN),
    ],
)
def test_home_renders_banner_for_status(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    status_code,
    expected_message,
) -> None:
    """DD-9 authenticated path: GET /home?email_change_status=<code> is neither
    404'd by validate_home_query_params() nor dropped — it renders the banner on
    HOME with the login-clause-free success copy."""
    client, _, _, app = login_first_user_with_register
    with app.test_request_context():
        home_url = url_for(
            ROUTES.UTUBS.HOME, **{EMAIL_CHANGE_STATUS_QUERY_PARAM: status_code}
        )

    response = client.get(home_url)

    assert response.status_code == 200
    assert b"EmailChangeStatusBanner" in response.data
    assert str(escape(expected_message)).encode() in response.data
