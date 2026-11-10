"""Email validation redirects a user who signed up from an invite to that invite.

Covers Step 2 of the invite signup handoff: the stored ``pending_invite`` is read
at validation, the user is validated and logged in, and the redirect goes to
``/invite/<token>``. Nothing here may ever add a member.
"""

import threading
from html import unescape
from typing import Any, Generator
from unittest import mock
from urllib.parse import urlparse

import pytest
from flask import Flask, g, url_for
from flask.testing import FlaskClient
from flask.wrappers import Response

from backend import db
from backend.metrics.events import EventName
from backend.models.email_validations import Email_Validations
from backend.models.users import Users
from backend.models.utub_invite_links import Utub_Invite_Links
from backend.models.utub_members import Utub_Members
from backend.utils.all_routes import ROUTES
from backend.utils.strings.email_validation_strs import EMAILS
from backend.utils.strings.invite_link_strs import INVITE_LINK_PAGE
from backend.utils.strings.splash_form_strs import INVITE_NEXT, REGISTER_FORM
from tests.integration.invite_links.invite_route_helpers import seed_dead
from tests.integration.short_links.short_link_helpers import (
    CREATOR_ID,
    FIRST_UTUB_ID,
    anonymous_client,
)
from tests.integration.splash.conftest import (
    create_user,
    patch_email_confirmation_spy,
    register_json,
)
from tests.integration.system.metrics_helpers import count_counter_keys
from tests.utils_for_test import add_invite_link

pytestmark = pytest.mark.splash

PASSWORD = "InvitePass1234"
NOTIFICATION_TIMEOUT_SECONDS = 5.0
_UNKNOWN_TOKEN = "not-a-real-validation-token"
_UNDECODABLE_TOKEN = "undecodable-stored-token"


def _identity(index: int) -> dict[str, str]:
    """A register identity that never collides with the mock users."""
    email = f"validateinvite{index}@email.com"
    return {
        REGISTER_FORM.USERNAME: f"ValidateInvite{index}",
        REGISTER_FORM.EMAIL: email,
        REGISTER_FORM.CONFIRM_EMAIL: email,
        REGISTER_FORM.PASSWORD: PASSWORD,
        REGISTER_FORM.CONFIRM_PASSWORD: PASSWORD,
    }


@pytest.fixture
def notified(monkeypatch) -> Generator[threading.Event, None, None]:
    """Stub the confirmation send and the welcome notification POST.

    Yields an event set whenever the welcome notification (sent from a thread on a
    successful validation) is dispatched.
    """
    patch_email_confirmation_spy(monkeypatch)
    event = threading.Event()

    def _post(*args: Any, **kwargs: Any) -> object:
        event.set()
        return type("MockResponse", (), {"status_code": 200})()

    with mock.patch(
        "backend.extensions.notifications.notifications.requests.post",
        side_effect=_post,
    ):
        yield event


def _token_of(app: Flask, invite_id: int) -> str:
    with app.app_context():
        invite = db.session.get(Utub_Invite_Links, invite_id)
        assert invite is not None
        return invite.token


def _seed_invite(app: Flask, state: str) -> int:
    if state == "live":
        return add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)
    if state == "revoked":
        return add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID, revoked=True)
    return seed_dead(app, state)


def _register(
    client: FlaskClient,
    csrf: str,
    identity: dict[str, str],
    invite_token: str | None = None,
) -> None:
    extra = {} if invite_token is None else {INVITE_NEXT: f"/invite/{invite_token}"}
    response = client.post(
        url_for(ROUTES.SPLASH.REGISTER),
        json={**register_json(identity), **extra},
        headers={"X-CSRFToken": csrf},
    )
    assert response.status_code == 200


def _stored_validation_token(app: Flask, identity: dict[str, str]) -> str:
    with app.app_context():
        db.session.expire_all()
        user = Users.query.filter(
            Users.email == identity[REGISTER_FORM.EMAIL].lower()
        ).one()
        return user.email_confirm.validation_token


def _set_stored_validation_token(
    app: Flask, identity: dict[str, str], token: str
) -> None:
    with app.app_context():
        user = Users.query.filter(
            Users.email == identity[REGISTER_FORM.EMAIL].lower()
        ).one()
        user.email_confirm.validation_token = token
        db.session.commit()


def _user_id(app: Flask, identity: dict[str, str]) -> int:
    with app.app_context():
        return (
            Users.query.filter(Users.email == identity[REGISTER_FORM.EMAIL].lower())
            .one()
            .id
        )


def _validate(
    client: FlaskClient,
    token: str,
    notified: threading.Event,
    *,
    follow: bool = True,
) -> Response:
    """GET the validation link as a fresh page load (stale login cache cleared)."""
    notified.clear()
    with client.application.test_request_context():
        g.pop("_login_user", None)
    return client.get(
        url_for(ROUTES.SPLASH.VALIDATE_EMAIL, token=token), follow_redirects=follow
    )


def _use_count(app: Flask, invite_id: int) -> int:
    with app.app_context():
        db.session.expire_all()
        invite = db.session.get(Utub_Invite_Links, invite_id)
        assert invite is not None
        return invite.use_count


def _membership_count(app: Flask, user_id: int) -> int:
    with app.app_context():
        return Utub_Members.query.filter_by(
            utub_id=FIRST_UTUB_ID, user_id=user_id
        ).count()


def _assert_validated_and_not_joined(
    app: Flask,
    client: FlaskClient,
    identity: dict[str, str],
    metrics_redis,
    notified: threading.Event,
    use_count_before: int | None,
    invite_id: int | None,
) -> None:
    """The user is validated, logged in and was never joined or counted as joined."""
    assert notified.wait(timeout=NOTIFICATION_TIMEOUT_SECONDS)
    user_id = _user_id(app, identity)
    with app.app_context():
        db.session.expire_all()
        user = db.session.get(Users, user_id)
        assert user is not None
        assert user.email_validated
        assert user.email_confirm is None
    # Read the client's own session, so this holds for any browser that validated
    with client.session_transaction() as client_session:
        assert client_session["_user_id"] == str(user_id)
        assert client_session[EMAILS.EMAIL_VALIDATED_SESS_KEY] is True
    assert _membership_count(app, user_id) == 0
    if invite_id is not None:
        assert _use_count(app, invite_id) == use_count_before
    assert count_counter_keys(metrics_redis, EventName.MEMBER_ADDED) == 0
    # Positive control: metrics are wired up, so the zero above is meaningful.
    assert count_counter_keys(metrics_redis, EventName.EMAIL_VERIFIED) == 1


@pytest.mark.parametrize("state", ["live", "revoked", "expired", "used_up"])
def test_validation_redirects_to_invite(
    metrics_enabled_app,
    provide_metrics_redis,
    app,
    every_user_makes_a_unique_utub,
    load_register_page,
    notified,
    state,
):
    """
    GIVEN a user who registered with an invite token (live or dead)
    WHEN they open their validation link
    THEN they are validated and logged in, redirected to /invite/<token>, which shows
        the join form (live) or the dead page, and are never joined.
    """
    client, csrf = load_register_page
    invite_id = _seed_invite(app, state)
    token = _token_of(app, invite_id)
    use_count_before = _use_count(app, invite_id)
    identity = _identity(1)
    _register(client, csrf, identity, token)

    response = _validate(client, _stored_validation_token(app, identity), notified)

    assert len(response.history) == 1
    assert response.history[0].status_code == 302
    assert response.history[0].location == url_for(
        ROUTES.INVITE_LINKS.INVITE_PAGE, token=token
    )
    page = response.get_data(as_text=True)
    if state == "live":
        assert response.status_code == 200
        assert 'id="inviteJoinForm"' in page
    else:
        # The uniform dead page is a 404 for every dead state
        assert response.status_code == 404
        assert INVITE_LINK_PAGE.DEAD_HEADING in unescape(page)
    _assert_validated_and_not_joined(
        app,
        client,
        identity,
        provide_metrics_redis,
        notified,
        use_count_before,
        invite_id,
    )


@pytest.mark.parametrize("case", ["never_stored", "invite_deleted"])
def test_null_reference_redirects_home(
    metrics_enabled_app,
    provide_metrics_redis,
    app,
    every_user_makes_a_unique_utub,
    load_register_page,
    notified,
    case,
):
    """
    GIVEN a user whose stored invite reference is NULL (never stored, or the invite
        row was deleted so ON DELETE SET NULL cleared it)
    WHEN they open their validation link
    THEN they are validated, logged in and land on /home with no flash.
    """
    client, csrf = load_register_page
    identity = _identity(1)
    if case == "never_stored":
        _register(client, csrf, identity)
    else:
        invite_id = add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)
        _register(client, csrf, identity, _token_of(app, invite_id))
        with app.app_context():
            # Bulk delete so the DB-level ON DELETE SET NULL clears the reference,
            # not an ORM cascade; expire_all drops any stale identity map.
            Utub_Invite_Links.query.filter_by(id=invite_id).delete()
            db.session.commit()
            db.session.expire_all()
            row = Email_Validations.query.filter_by(
                user_id=_user_id(app, identity)
            ).one()
            assert row.pending_invite_id is None

    response = _validate(client, _stored_validation_token(app, identity), notified)

    assert len(response.history) == 1
    assert response.history[0].location == url_for(ROUTES.UTUBS.HOME)
    assert response.status_code == 200
    _assert_validated_and_not_joined(
        app, client, identity, provide_metrics_redis, notified, None, None
    )


def test_third_party_browser_validates_and_lands_on_invite(
    metrics_enabled_app,
    provide_metrics_redis,
    app,
    every_user_makes_a_unique_utub,
    load_register_page,
    notified,
):
    """
    GIVEN a user who registered with an invite in browser A
    WHEN the validation link is opened in a fresh browser B
    THEN B is logged in as that user and lands on /invite/<token> without joining.
    """
    client, csrf = load_register_page
    invite_id = add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)
    token = _token_of(app, invite_id)
    identity = _identity(1)
    _register(client, csrf, identity, token)

    use_count_before = _use_count(app, invite_id)
    fresh_client = anonymous_client(app)
    response = _validate(
        fresh_client, _stored_validation_token(app, identity), notified
    )

    assert response.history[0].location == url_for(
        ROUTES.INVITE_LINKS.INVITE_PAGE, token=token
    )
    assert 'id="inviteJoinForm"' in response.get_data(as_text=True)
    _assert_validated_and_not_joined(
        app,
        fresh_client,
        identity,
        provide_metrics_redis,
        notified,
        use_count_before,
        invite_id,
    )


def _failure_outcome(
    app: Flask,
    client: FlaskClient,
    csrf: str,
    notified: threading.Event,
    identity: dict[str, str],
    invite_token: str | None,
    case: str,
) -> tuple[int, str, bool, bool]:
    """Register, break the validation link per ``case`` and request it.

    Returns (status, redirect path or "", user still exists, row still exists).
    """
    _register(client, csrf, identity, invite_token)
    if invite_token is not None:
        # The comparison is only meaningful if the reference really is stored
        assert _pending_invite_id(app, identity) is not None
    stored = _stored_validation_token(app, identity)
    if case == "unknown_token":
        probe = _UNKNOWN_TOKEN
    elif case == "undecodable_stored":
        _set_stored_validation_token(app, identity, _UNDECODABLE_TOKEN)
        probe = _UNDECODABLE_TOKEN
    else:
        with app.app_context():
            user = Users.query.filter(
                Users.email == identity[REGISTER_FORM.EMAIL].lower()
            ).one()
            probe = user.get_email_validation_token(expires_in=0)
        _set_stored_validation_token(app, identity, probe)
    assert probe != stored

    response = _validate(client, probe, notified, follow=False)

    # Not logged in, and never sent to an invite.
    home = client.get(url_for(ROUTES.UTUBS.HOME))
    assert home.status_code == 302
    assert urlparse(home.location).path == url_for(ROUTES.SPLASH.SPLASH_PAGE)
    location = response.location or ""
    assert not urlparse(location).path.startswith("/invite/")

    with app.app_context():
        db.session.expire_all()
        user = Users.query.filter(
            Users.email == identity[REGISTER_FORM.EMAIL].lower()
        ).first()
        row_exists = (
            Email_Validations.query.filter(
                Email_Validations.validation_token.in_([stored, probe])
            ).first()
            is not None
        )
        return (
            response.status_code,
            urlparse(location).path,
            user is not None,
            row_exists,
        )


@pytest.mark.parametrize(
    "case", ["unknown_token", "undecodable_stored", "expired_token"]
)
def test_failure_paths_unchanged_with_stored_reference(
    app, every_user_makes_a_unique_utub, load_register_page, notified, case
):
    """
    GIVEN a pending user with a stored invite reference, and one without
    WHEN each requests a failing validation link of the same kind
    THEN both get exactly the same status, redirect and deletions: no login and no
        redirect to an invite.
    """
    client, csrf = load_register_page
    invite_token = _token_of(app, add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID))

    with_ref = _failure_outcome(
        app, client, csrf, notified, _identity(1), invite_token, case
    )
    without_ref = _failure_outcome(
        app, client, csrf, notified, _identity(2), None, case
    )

    expected = {
        "unknown_token": (404, "", True, True),
        "undecodable_stored": (404, "", False, False),
        "expired_token": (
            302,
            urlparse(url_for("splash.validate_email_expired")).path,
            True,
            True,
        ),
    }[case]
    assert with_ref == expected
    assert without_ref == expected


# ---------------------------------------------------------------------------
# Keep-reference flows: resend, re-mint and reissue never drop the stored invite
# ---------------------------------------------------------------------------


def _pending_user_with_invite(app: Flask) -> tuple[dict[str, str], int, str]:
    """A pending (unvalidated) user whose row references a live invite.

    The reference is set directly on the row, not through register.
    """
    identity = _identity(7)
    create_user(
        app,
        identity[REGISTER_FORM.USERNAME],
        identity[REGISTER_FORM.EMAIL],
        PASSWORD,
        validated=False,
    )
    invite_id = add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)
    with app.app_context():
        user = Users.query.filter(
            Users.email == identity[REGISTER_FORM.EMAIL].lower()
        ).one()
        user.email_confirm.pending_invite_id = invite_id
        db.session.commit()
    return identity, invite_id, _token_of(app, invite_id)


def _pending_invite_id(app: Flask, identity: dict[str, str]) -> int | None:
    with app.app_context():
        db.session.expire_all()
        user = Users.query.filter(
            Users.email == identity[REGISTER_FORM.EMAIL].lower()
        ).one()
        return user.email_confirm.pending_invite_id


def _assert_link_lands_on_invite(
    client: FlaskClient, notified: threading.Event, token: str, invite_token: str
) -> None:
    response = _validate(client, token, notified, follow=False)
    assert response.status_code == 302
    assert response.location == url_for(
        ROUTES.INVITE_LINKS.INVITE_PAGE, token=invite_token
    )
    # The welcome notification thread must finish before the stub is removed
    assert notified.wait(timeout=NOTIFICATION_TIMEOUT_SECONDS)


@pytest.mark.parametrize("keyed_by", ["email", "resend_token"])
@pytest.mark.parametrize("stored", ["healthy", "expired"])
def test_resend_keeps_reference(
    app, every_user_makes_a_unique_utub, load_register_page, notified, keyed_by, stored
):
    """
    GIVEN a pending user with a stored invite reference (healthy or expired token)
    WHEN a resend runs (email-keyed or token-keyed, re-minting the token if expired)
    THEN the reference is unchanged and the resulting link redirects to the invite.
    """
    client, csrf = load_register_page
    identity, invite_id, invite_token = _pending_user_with_invite(app)
    if stored == "expired":
        with app.app_context():
            user = Users.query.filter(
                Users.email == identity[REGISTER_FORM.EMAIL].lower()
            ).one()
            expired = user.get_email_validation_token(expires_in=-10)
        _set_stored_validation_token(app, identity, expired)
    if keyed_by == "email":
        body: dict[str, str] = {"email": identity[REGISTER_FORM.EMAIL]}
    else:
        with app.app_context():
            user = Users.query.filter(
                Users.email == identity[REGISTER_FORM.EMAIL].lower()
            ).one()
            body = {"resendToken": user.get_resend_validation_token()}

    response = client.post(
        url_for(ROUTES.SPLASH.RESEND_REGISTRATION_EMAIL),
        json=body,
        headers={"X-CSRFToken": csrf},
    )

    assert response.status_code == 200
    assert _pending_invite_id(app, identity) == invite_id
    new_token = _stored_validation_token(app, identity)
    if stored == "expired":
        assert new_token != expired
    _assert_link_lands_on_invite(client, notified, new_token, invite_token)


def test_expired_token_reissue_keeps_reference(
    app, every_user_makes_a_unique_utub, load_register_page, notified
):
    """
    GIVEN a pending user with a stored invite reference and an expired token
    WHEN they visit /validate/expired (which re-mints the token)
    THEN the reference is unchanged and the new link redirects to the invite.
    """
    client, _ = load_register_page
    identity, invite_id, invite_token = _pending_user_with_invite(app)
    with app.app_context():
        user = Users.query.filter(
            Users.email == identity[REGISTER_FORM.EMAIL].lower()
        ).one()
        expired = user.get_email_validation_token(expires_in=0)
    _set_stored_validation_token(app, identity, expired)

    response = client.get(url_for("splash.validate_email_expired", token=expired))

    assert response.status_code == 200
    assert _pending_invite_id(app, identity) == invite_id
    new_token = _stored_validation_token(app, identity)
    assert new_token != expired
    _assert_link_lands_on_invite(client, notified, new_token, invite_token)
