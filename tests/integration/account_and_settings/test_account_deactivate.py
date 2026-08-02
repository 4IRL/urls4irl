"""Integration tests for the reversible self-deactivation endpoint
(``PUT /users/<id>/deactivate``).

Mirrors ``test_change_password.py``'s fixture/CSRF conventions (the
``login_first_user_with_register`` fixture, the meta-tag CSRF scrape, and the
autouse ``reauth-fail:*`` Redis reset), but asserts the *inverse* session
outcome: deactivate must log the acting session out (``perform_self_deactivation``
skips ``restamp_current_session``), so a follow-up gated GET redirects instead of
surviving. Also covers the sole-admin 403 guard and the end-to-end
reactivate-on-login round-trip. The OAuth-only round-trip is covered separately
in ``test_account_removal_oauth_proof.py``.
"""

from __future__ import annotations

from typing import Generator, Tuple
from unittest import mock

import pytest
from flask import Flask, g, url_for
from flask.testing import FlaskClient
from redis import Redis

from backend import db
from backend.api_v1.services.tokens import issue_refresh_token
from backend.metrics.events import EventName
from backend.models.api_refresh_tokens import ApiRefreshTokens
from backend.models.users import User_Role, Users
from backend.schemas.users import AccountRemovalResponseSchema
from backend.users.constants import DeactivateAccountErrorCodes
from backend.utils.all_routes import ROUTES
from backend.utils.constants import USER_CONSTANTS
from backend.utils.strings import model_strs
from backend.utils.strings.config_strs import CONFIG_ENVS
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.splash_form_strs import LOGIN_FORM
from backend.utils.strings.user_strs import (
    ACCOUNT_DEACTIVATED_SUCCESS,
    REDIRECT_URL,
    USER_FAILURE,
)
from tests.conftest import AjaxFlaskLoginClient
from tests.integration.system.metrics_helpers import count_counter_keys
from tests.integration.utils import assert_response_conforms_to_schema
from tests.models_for_test import valid_user_1
from tests.utils_for_test import get_csrf_token

pytestmark = pytest.mark.account_and_support

_SPLASH_PATH = "/"
_CURRENT_PASSWORD = valid_user_1[model_strs.PASSWORD]
_WRONG_PASSWORD = "TotallyWrongPassword!23"


@pytest.fixture(autouse=True)
def _reset_reauth_failure_counter(app: Flask) -> Generator[None, None, None]:
    """Clear the worker-scoped ``reauth-fail:*`` Redis counter before and after
    every test in this module (copied from ``test_change_password.py`` — the
    per-user re-auth lockout counter survives DB teardown, so without this a
    wrong-password test would 429 a later unrelated test on the same xdist
    worker)."""

    def _clear() -> None:
        redis_uri = app.config.get(CONFIG_ENVS.REDIS_URI)
        if not redis_uri or redis_uri == "memory://":
            return
        client = Redis.from_url(redis_uri)
        try:
            keys = client.keys("reauth-fail:*")
            if keys:
                client.delete(*keys)
        finally:
            client.close()

    _clear()
    yield
    _clear()


def _deactivate_payload(
    *, current_password: str | None = _CURRENT_PASSWORD
) -> dict[str, str | None]:
    return {"currentPassword": current_password}


def _login_payload() -> dict[str, str]:
    return {
        LOGIN_FORM.USERNAME: valid_user_1[LOGIN_FORM.USERNAME],
        LOGIN_FORM.PASSWORD: valid_user_1[LOGIN_FORM.PASSWORD],
    }


def _clear_flask_login_request_cache() -> None:
    """Drop Flask-Login's per-request user cache (``g._login_user``) so the next
    request consults the user_loader again — matching production per-request
    behavior (mirrors ``test_account_state_gates.py``)."""
    if hasattr(g, "_login_user"):
        delattr(g, "_login_user")


def _seed_refresh_token(app: Flask, user_id: int) -> int:
    with app.app_context():
        user: Users = Users.query.get(user_id)
        issue_refresh_token(user=user)
        token_row: ApiRefreshTokens = ApiRefreshTokens.query.filter_by(
            user_id=user_id
        ).first()
        return token_row.id


def test_deactivate_password_happy_path_pauses_and_logs_out(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A valid deactivate returns 200 with the splash ``redirectUrl``, sets both
    reversible-pause flags, bumps ``sessions_invalidated_at``, revokes the
    refresh token, and logs the acting session out (a follow-up gated GET
    302-redirects — the inverse of change-password's session-survival)."""
    client, csrf_token, user, app = login_first_user_with_register
    user_id = user.id
    refresh_token_id = _seed_refresh_token(app, user_id)

    response = client.put(
        url_for(ROUTES.USERS.DEACTIVATE_ACCOUNT, user_id=user_id),
        json=_deactivate_payload(),
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    assert response.content_type == "application/json"
    response_json = response.get_json()
    assert_response_conforms_to_schema(
        response_json,
        AccountRemovalResponseSchema,
        expected_keys={STD_JSON.STATUS, STD_JSON.MESSAGE, REDIRECT_URL},
    )
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[STD_JSON.MESSAGE] == ACCOUNT_DEACTIVATED_SUCCESS
    assert response_json[REDIRECT_URL] == url_for(ROUTES.SPLASH.SPLASH_PAGE)

    with app.app_context():
        refreshed: Users = Users.query.get(user_id)
        assert refreshed.is_suspended is True
        assert refreshed.self_deactivated_at is not None
        assert refreshed.sessions_invalidated_at is not None
        revoked_token: ApiRefreshTokens = ApiRefreshTokens.query.get(refresh_token_id)
        assert revoked_token.revoked_at is not None

    # The acting session was NOT re-stamped and the account is now suspended, so
    # the next gated request resolves to anonymous and redirects.
    _clear_flask_login_request_cache()
    settings_response = client.get(url_for(ROUTES.USERS.SETTINGS))
    assert settings_response.status_code == 302


def test_deactivate_wrong_password_returns_400_field_error(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A wrong current password fails re-auth → 400 with the INVALID_PASSWORD
    code and a ``currentPassword`` field error; no state is mutated."""
    client, csrf_token, user, app = login_first_user_with_register
    user_id = user.id

    response = client.put(
        url_for(ROUTES.USERS.DEACTIVATE_ACCOUNT, user_id=user_id),
        json=_deactivate_payload(current_password=_WRONG_PASSWORD),
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 400
    response_json = response.get_json()
    assert (
        response_json[STD_JSON.ERROR_CODE]
        == DeactivateAccountErrorCodes.INVALID_PASSWORD
    )
    assert USER_FAILURE.CURRENT_PASSWORD_INCORRECT in (
        response_json[STD_JSON.ERRORS]["currentPassword"]
    )

    with app.app_context():
        refreshed: Users = Users.query.get(user_id)
        assert refreshed.is_suspended is False
        assert refreshed.self_deactivated_at is None


def test_deactivate_password_account_missing_password_returns_400_field_error(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A password account that omits ``currentPassword`` (the field is optional
    so OAuth-only accounts can omit it) is treated as a failed re-auth → a clean
    400 field error, NOT a 500 crash on ``is_password_correct(None)``. No state
    is mutated."""
    client, csrf_token, user, app = login_first_user_with_register
    user_id = user.id

    response = client.put(
        url_for(ROUTES.USERS.DEACTIVATE_ACCOUNT, user_id=user_id),
        json=_deactivate_payload(current_password=None),
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 400
    response_json = response.get_json()
    assert (
        response_json[STD_JSON.ERROR_CODE]
        == DeactivateAccountErrorCodes.INVALID_PASSWORD
    )
    assert USER_FAILURE.CURRENT_PASSWORD_INCORRECT in (
        response_json[STD_JSON.ERRORS]["currentPassword"]
    )

    with app.app_context():
        refreshed: Users = Users.query.get(user_id)
        assert refreshed.is_suspended is False
        assert refreshed.self_deactivated_at is None


def test_deactivate_self_ownership_mismatch_returns_403(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A PUT whose URL user_id is not the acting user is rejected 403."""
    client, csrf_token, user, _ = login_first_user_with_register

    response = client.put(
        url_for(ROUTES.USERS.DEACTIVATE_ACCOUNT, user_id=user.id + 999),
        json=_deactivate_payload(),
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 403


def test_deactivate_sole_admin_returns_403(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """The last active admin cannot deactivate their own account → 403 with the
    SOLE_ADMIN_CANNOT_LEAVE message; no state is mutated."""
    client, csrf_token, user, app = login_first_user_with_register
    user_id = user.id

    with app.app_context():
        admin_user: Users = Users.query.get(user_id)
        admin_user.role = User_Role.ADMIN
        db.session.commit()

    response = client.put(
        url_for(ROUTES.USERS.DEACTIVATE_ACCOUNT, user_id=user_id),
        json=_deactivate_payload(),
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 403
    response_json = response.get_json()
    assert (
        response_json[STD_JSON.ERROR_CODE]
        == DeactivateAccountErrorCodes.SOLE_ADMIN_FORBIDDEN
    )
    assert response_json[STD_JSON.MESSAGE] == USER_FAILURE.SOLE_ADMIN_CANNOT_LEAVE

    with app.app_context():
        refreshed: Users = Users.query.get(user_id)
        assert refreshed.is_suspended is False
        assert refreshed.self_deactivated_at is None


def test_deactivate_then_login_reactivates_end_to_end(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """End-to-end: deactivate (account locked) → a subsequent successful login
    auto-lifts the pause (both flags cleared) and lands authenticated."""
    client, csrf_token, user, app = login_first_user_with_register
    user_id = user.id

    deactivate_response = client.put(
        url_for(ROUTES.USERS.DEACTIVATE_ACCOUNT, user_id=user_id),
        json=_deactivate_payload(),
        headers={"X-CSRFToken": csrf_token},
    )
    assert deactivate_response.status_code == 200

    with app.app_context():
        locked: Users = Users.query.get(user_id)
        assert locked.is_suspended is True
        assert locked.self_deactivated_at is not None

    # A fresh login with the correct credentials reactivates the account.
    _clear_flask_login_request_cache()
    splash_response = client.get(_SPLASH_PATH)
    fresh_csrf = get_csrf_token(splash_response.get_data(), meta_tag=True)
    login_response = client.post(
        url_for(ROUTES.SPLASH.LOGIN),
        json=_login_payload(),
        headers={"X-CSRFToken": fresh_csrf},
    )
    assert login_response.status_code == 200

    with app.app_context():
        reactivated: Users = Users.query.get(user_id)
        assert reactivated.is_suspended is False
        assert reactivated.self_deactivated_at is None


# --------------------------------------------------------------------------- #
# Brute-force re-auth lockout (DD-1) — real Redis via provide_redis.
# --------------------------------------------------------------------------- #


def test_deactivate_locks_out_after_max_reauth_failures(
    provide_redis: Redis | None,
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """``MAX_REAUTH_FAILURES`` wrong-password attempts each return 400; a further
    attempt returns 429 with the TOO_MANY_ATTEMPTS code — even when the correct
    password is supplied."""
    if provide_redis is None:
        pytest.skip("Requires a real Redis instance (Docker stack)")

    client, csrf_token, user, _ = login_first_user_with_register
    user_id = user.id

    for _ in range(USER_CONSTANTS.MAX_REAUTH_FAILURES):
        response = client.put(
            url_for(ROUTES.USERS.DEACTIVATE_ACCOUNT, user_id=user_id),
            json=_deactivate_payload(current_password=_WRONG_PASSWORD),
            headers={"X-CSRFToken": csrf_token},
        )
        assert response.status_code == 400

    blocked = client.put(
        url_for(ROUTES.USERS.DEACTIVATE_ACCOUNT, user_id=user_id),
        json=_deactivate_payload(),
        headers={"X-CSRFToken": csrf_token},
    )
    assert blocked.status_code == 429
    blocked_json = blocked.get_json()
    assert (
        blocked_json[STD_JSON.ERROR_CODE]
        == DeactivateAccountErrorCodes.TOO_MANY_ATTEMPTS
    )
    assert blocked_json[STD_JSON.MESSAGE] == USER_FAILURE.TOO_MANY_PASSWORD_ATTEMPTS


def test_deactivate_success_clears_reauth_counter(
    provide_redis: Redis | None,
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A couple of wrong attempts accrue failures; a successful deactivate clears
    the per-user counter."""
    if provide_redis is None:
        pytest.skip("Requires a real Redis instance (Docker stack)")

    client, csrf_token, user, _ = login_first_user_with_register
    user_id = user.id
    failure_key = f"reauth-fail:{user_id}"

    for _ in range(3):
        client.put(
            url_for(ROUTES.USERS.DEACTIVATE_ACCOUNT, user_id=user_id),
            json=_deactivate_payload(current_password=_WRONG_PASSWORD),
            headers={"X-CSRFToken": csrf_token},
        )
    assert provide_redis.get(failure_key) == b"3"

    success = client.put(
        url_for(ROUTES.USERS.DEACTIVATE_ACCOUNT, user_id=user_id),
        json=_deactivate_payload(),
        headers={"X-CSRFToken": csrf_token},
    )
    assert success.status_code == 200
    assert provide_redis.get(failure_key) is None


def test_deactivate_fails_open_when_reauth_redis_errors(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """When the re-auth throttle Redis client raises, the deactivate still
    processes (200) — the lockout is defense-in-depth, not the sole gate."""
    client, csrf_token, user, app = login_first_user_with_register
    user_id = user.id

    raising_client = mock.MagicMock()
    raising_client.get.side_effect = Exception("redis down")
    raising_client.incr.side_effect = Exception("redis down")
    raising_client.delete.side_effect = Exception("redis down")

    with mock.patch(
        "backend.utils.reauth_throttle._build_reauth_redis",
        return_value=raising_client,
    ):
        response = client.put(
            url_for(ROUTES.USERS.DEACTIVATE_ACCOUNT, user_id=user_id),
            json=_deactivate_payload(),
            headers={"X-CSRFToken": csrf_token},
        )

    assert response.status_code == 200
    assert response.get_json()[STD_JSON.STATUS] == STD_JSON.SUCCESS
    with app.app_context():
        assert Users.query.get(user_id).is_suspended is True


# --------------------------------------------------------------------------- #
# ACCOUNT_DEACTIVATED domain metric.
# --------------------------------------------------------------------------- #


def test_deactivate_records_account_deactivated_metric(
    metrics_enabled_app: Flask,
    provide_metrics_redis: Redis | None,
    register_first_user,
) -> None:
    """A successful self-deactivation writes exactly one ACCOUNT_DEACTIVATED
    counter key to the metrics Redis DB (the per-flow emit coverage that lets
    ACCOUNT_DEACTIVATED sit in DOMAIN_EVENTS_TESTED_ELSEWHERE)."""
    if provide_metrics_redis is None:
        pytest.skip("metrics Redis is unavailable in this environment")

    app = metrics_enabled_app
    app.test_client_class = AjaxFlaskLoginClient
    with app.app_context():
        user_id: int = Users.query.get(1).id

    assert count_counter_keys(provide_metrics_redis, EventName.ACCOUNT_DEACTIVATED) == 0

    with app.app_context():
        user_to_login: Users = Users.query.get(user_id)

    with app.test_client(user=user_to_login) as logged_in_client:
        home_response = logged_in_client.get("/home")
        csrf_token = get_csrf_token(home_response.get_data(), meta_tag=True)
        response = logged_in_client.put(
            url_for(ROUTES.USERS.DEACTIVATE_ACCOUNT, user_id=user_id),
            json=_deactivate_payload(),
            headers={"X-CSRFToken": csrf_token},
        )
        assert response.status_code == 200

    assert count_counter_keys(provide_metrics_redis, EventName.ACCOUNT_DEACTIVATED) == 1
