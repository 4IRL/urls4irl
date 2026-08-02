"""Integration tests for the OAuth-proof account-removal round-trip (Step 5 of
the settings-account-removal feature).

A password-less (OAuth-only) account cannot re-auth inline, so
``PUT /users/<id>/deactivate`` / ``DELETE /users/<id>`` stash a removal intent
and 200-redirect the client into ``GET /oauth/<provider>/link``; the
authenticated provider callback then executes the stashed removal via
``linking_service.handle_authenticated_oauth_callback`` →
``removal_oauth.execute_removal_intent``.

Authlib calls are mocked at the call sites used inside
``google_service``/``linking_service`` — the same convention as
``test_oauth_linking.py``, whose ``oauth_only_google_user_logged_in`` fixture
(conftest) seeds the password-less user under test.
"""

from __future__ import annotations

from typing import Tuple
from unittest import mock

import pytest
from flask import Flask, redirect, url_for
from flask.testing import FlaskClient

from backend import db
from backend.admin.account_data_service import is_tombstoned
from backend.api_v1.services.tokens import issue_refresh_token
from backend.models.api_refresh_tokens import ApiRefreshTokens
from backend.models.audit_log import AuditLog
from backend.models.users import User_Role, Users
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utubs import Utubs
from backend.splash.services.oauth.constants import (
    OAUTH_LINK_INTENT_SESSION_KEY,
    REMOVAL_INTENT_ACTION_DEACTIVATE,
    REMOVAL_INTENT_ACTION_DELETE,
)
from backend.utils.all_routes import OAUTH_ROUTES, ROUTES
from backend.utils.datetime_utils import utc_now
from backend.utils.strings import model_strs
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.splash_form_strs import LOGIN_FORM
from backend.utils.strings.user_strs import (
    ACCOUNT_AUDIT_ACTIONS,
    OAUTH_PROOF_REDIRECT_PENDING,
    REDIRECT_URL,
    USER_FAILURE,
)
from tests.integration.account_and_settings.conftest import (
    _OAUTH_ONLY_EMAIL,
    _OAUTH_ONLY_GOOGLE_SUBJECT,
)
from tests.models_for_test import valid_user_1

pytestmark = pytest.mark.account_and_support

_FAKE_CODE = "fake-authorization-code"
_FAKE_STATE = "fake-state-value"
_MOCK_GOOGLE_CONSENT_URL = "https://accounts.google.com/o/oauth2/mock-consent"
_MISMATCHED_GOOGLE_SUBJECT = "a_different_unlinked_google_subject"

_LINKING_GOOGLE_AUTHORIZE_REDIRECT_TARGET = (
    "backend.splash.services.oauth.linking_service.oauth.google.authorize_redirect"
)
_GOOGLE_AUTHORIZE_ACCESS_TOKEN_TARGET = (
    "backend.splash.services.oauth.google_service.oauth.google.authorize_access_token"
)


def _build_mocked_google_token(*, subject: str, email: str) -> dict:
    return {"userinfo": {"sub": subject, "email": email, "email_verified": True}}


def _seed_user(app: Flask, *, username: str, email: str) -> int:
    """Create a non-admin email-validated password user; return its id."""
    with app.app_context():
        user = Users(username=username, email=email, plaintext_password="OtherPass1!")
        user.email_validated = True
        db.session.add(user)
        db.session.commit()
        return user.id


def _seed_solo_utub(app: Flask, *, creator_id: int, name: str) -> int:
    with app.app_context():
        new_utub = Utubs(name=name, utub_creator=creator_id, utub_description="")
        db.session.add(new_utub)
        db.session.flush()
        db.session.add(
            Utub_Members(
                utub_id=new_utub.id,
                user_id=creator_id,
                member_role=Member_Role.CREATOR,
            )
        )
        db.session.commit()
        return new_utub.id


def _seed_shared_utub(app: Flask, *, creator_id: int, other_id: int, name: str) -> int:
    with app.app_context():
        new_utub = Utubs(name=name, utub_creator=creator_id, utub_description="")
        db.session.add(new_utub)
        db.session.flush()
        db.session.add_all(
            [
                Utub_Members(
                    utub_id=new_utub.id,
                    user_id=creator_id,
                    member_role=Member_Role.CREATOR,
                ),
                Utub_Members(
                    utub_id=new_utub.id,
                    user_id=other_id,
                    member_role=Member_Role.CO_CREATOR,
                ),
            ]
        )
        db.session.commit()
        return new_utub.id


def _seed_refresh_token(app: Flask, user_id: int) -> int:
    with app.app_context():
        user: Users = Users.query.get(user_id)
        issue_refresh_token(user=user)
        token_row: ApiRefreshTokens = ApiRefreshTokens.query.filter_by(
            user_id=user_id
        ).first()
        return token_row.id


def _initiate_oauth_deactivate(client: FlaskClient, csrf_token: str, user_id: int):
    return client.put(
        url_for(ROUTES.USERS.DEACTIVATE_ACCOUNT, user_id=user_id),
        json={},
        headers={"X-CSRFToken": csrf_token},
    )


def _initiate_oauth_delete(
    client: FlaskClient, csrf_token: str, user_id: int, username: str
):
    return client.delete(
        url_for(ROUTES.USERS.DELETE_ACCOUNT, user_id=user_id),
        json={"confirmUsername": username},
        headers={"X-CSRFToken": csrf_token},
    )


def _drive_google_proof_callback(client: FlaskClient, *, subject: str, email: str):
    """Runs the ``GET /oauth/google/link`` → ``GET /oauth/google/callback`` legs
    of the round-trip with Authlib mocked, returning the callback response."""
    with mock.patch(_LINKING_GOOGLE_AUTHORIZE_REDIRECT_TARGET) as mock_redirect:
        mock_redirect.return_value = redirect(_MOCK_GOOGLE_CONSENT_URL)
        client.get(url_for(OAUTH_ROUTES.LINK, provider="google"))

    with mock.patch(_GOOGLE_AUTHORIZE_ACCESS_TOKEN_TARGET) as mock_token:
        mock_token.return_value = _build_mocked_google_token(
            subject=subject, email=email
        )
        return client.get(
            url_for(OAUTH_ROUTES.GOOGLE_CALLBACK, code=_FAKE_CODE, state=_FAKE_STATE)
        )


# --------------------------------------------------------------------------- #
# Initiator — OAuth-only accounts get a 200 redirect + a stashed removal intent.
# --------------------------------------------------------------------------- #


def test_oauth_only_deactivate_returns_redirect_and_stashes_intent(
    oauth_only_google_user_logged_in: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """An OAuth-only account's deactivate returns 200 with the provider-link
    ``redirectUrl`` and stashes a ``deactivate`` removal intent (no state
    mutation yet — the callback performs it)."""
    client, csrf_token, user, app = oauth_only_google_user_logged_in
    user_id = user.id

    response = _initiate_oauth_deactivate(client, csrf_token, user_id)

    assert response.status_code == 200
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[STD_JSON.MESSAGE] == OAUTH_PROOF_REDIRECT_PENDING
    assert response_json[REDIRECT_URL] == url_for(OAUTH_ROUTES.LINK, provider="google")

    with client.session_transaction() as flask_session:
        intent = flask_session[OAUTH_LINK_INTENT_SESSION_KEY]
        assert intent["action"] == REMOVAL_INTENT_ACTION_DEACTIVATE
        assert intent["proof_provider"] == "google"
        assert intent["user_id"] == user_id
        assert "target_provider" not in intent

    with app.app_context():
        refreshed: Users = Users.query.get(user_id)
        assert refreshed.is_suspended is False
        assert refreshed.self_deactivated_at is None


def test_oauth_only_delete_returns_redirect_and_stashes_intent(
    oauth_only_google_user_logged_in: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """An OAuth-only account's delete returns 200 with the provider-link
    ``redirectUrl`` and stashes a ``delete`` removal intent; nothing is erased
    until the callback fires."""
    client, csrf_token, user, app = oauth_only_google_user_logged_in
    user_id = user.id
    username = user.username

    response = _initiate_oauth_delete(client, csrf_token, user_id, username)

    assert response.status_code == 200
    response_json = response.get_json()
    assert response_json[STD_JSON.MESSAGE] == OAUTH_PROOF_REDIRECT_PENDING
    assert response_json[REDIRECT_URL] == url_for(OAUTH_ROUTES.LINK, provider="google")

    with client.session_transaction() as flask_session:
        intent = flask_session[OAUTH_LINK_INTENT_SESSION_KEY]
        assert intent["action"] == REMOVAL_INTENT_ACTION_DELETE
        assert intent["proof_provider"] == "google"

    with app.app_context():
        assert not is_tombstoned(user=Users.query.get(user_id))


def test_oauth_only_delete_confirmation_mismatch_still_gated(
    oauth_only_google_user_logged_in: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """The typed-username confirmation guard runs BEFORE the OAuth-only branch,
    so a mismatched ``confirmUsername`` on an OAuth-only account is rejected 400
    and no removal intent is stashed."""
    client, csrf_token, user, _ = oauth_only_google_user_logged_in

    response = _initiate_oauth_delete(client, csrf_token, user.id, "not-my-username")

    assert response.status_code == 400
    with client.session_transaction() as flask_session:
        assert OAUTH_LINK_INTENT_SESSION_KEY not in flask_session


# --------------------------------------------------------------------------- #
# Callback — the OAuth-proof round-trip executes the stashed removal.
# --------------------------------------------------------------------------- #


def test_oauth_only_deactivate_callback_pauses_and_logs_out(
    oauth_only_google_user_logged_in: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """The full round-trip: initiate deactivate → proof callback with the user's
    own google subject → the account is paused, its refresh token revoked, the
    session logged out, and the response redirects to splash."""
    client, csrf_token, user, app = oauth_only_google_user_logged_in
    user_id = user.id
    refresh_token_id = _seed_refresh_token(app, user_id)

    assert _initiate_oauth_deactivate(client, csrf_token, user_id).status_code == 200

    callback_response = _drive_google_proof_callback(
        client, subject=_OAUTH_ONLY_GOOGLE_SUBJECT, email=_OAUTH_ONLY_EMAIL
    )

    assert callback_response.status_code == 302
    assert callback_response.location == url_for(ROUTES.SPLASH.SPLASH_PAGE)

    with app.app_context():
        paused: Users = Users.query.get(user_id)
        assert paused.is_suspended is True
        assert paused.self_deactivated_at is not None
        assert paused.sessions_invalidated_at is not None
        revoked_token: ApiRefreshTokens = ApiRefreshTokens.query.get(refresh_token_id)
        assert revoked_token.revoked_at is not None

    # The removal intent was consumed (not replayable).
    with client.session_transaction() as flask_session:
        assert OAUTH_LINK_INTENT_SESSION_KEY not in flask_session


def test_oauth_only_deactivate_callback_then_oauth_login_reactivates(
    oauth_only_google_user_logged_in: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """After an OAuth-proof deactivation, a subsequent Google sign-in with the
    same subject reactivates the account (reactivate-on-login lifts the
    self-pause) and lands authenticated."""
    client, csrf_token, user, app = oauth_only_google_user_logged_in
    user_id = user.id

    assert _initiate_oauth_deactivate(client, csrf_token, user_id).status_code == 200
    deactivate_callback = _drive_google_proof_callback(
        client, subject=_OAUTH_ONLY_GOOGLE_SUBJECT, email=_OAUTH_ONLY_EMAIL
    )
    assert deactivate_callback.status_code == 302

    with app.app_context():
        assert Users.query.get(user_id).is_suspended is True

    # A fresh (now-unauthenticated) Google sign-in with the same subject
    # reactivates the account.
    with mock.patch(_GOOGLE_AUTHORIZE_ACCESS_TOKEN_TARGET) as mock_token:
        mock_token.return_value = _build_mocked_google_token(
            subject=_OAUTH_ONLY_GOOGLE_SUBJECT, email=_OAUTH_ONLY_EMAIL
        )
        relogin_response = client.get(
            url_for(OAUTH_ROUTES.GOOGLE_CALLBACK, code=_FAKE_CODE, state=_FAKE_STATE)
        )

    assert relogin_response.status_code == 302

    with app.app_context():
        reactivated: Users = Users.query.get(user_id)
        assert reactivated.is_suspended is False
        assert reactivated.self_deactivated_at is None


def test_oauth_only_delete_callback_erases_membership_matrix(
    oauth_only_google_user_logged_in: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """The full round-trip: initiate delete → proof callback with the user's own
    google subject → the account is tombstoned, its solo UTub deleted, a
    created-with-others UTub transferred, the self-actor audit row written, and
    the response redirects to splash."""
    client, csrf_token, user, app = oauth_only_google_user_logged_in
    user_id = user.id
    username = user.username

    other_id = _seed_user(app, username="oauthtransferee", email="oauthxfer@test.com")
    solo_utub_id = _seed_solo_utub(app, creator_id=user_id, name="OAuthSoloUTub")
    shared_utub_id = _seed_shared_utub(
        app, creator_id=user_id, other_id=other_id, name="OAuthSharedUTub"
    )

    assert (
        _initiate_oauth_delete(client, csrf_token, user_id, username).status_code == 200
    )

    callback_response = _drive_google_proof_callback(
        client, subject=_OAUTH_ONLY_GOOGLE_SUBJECT, email=_OAUTH_ONLY_EMAIL
    )

    assert callback_response.status_code == 302
    assert callback_response.location == url_for(ROUTES.SPLASH.SPLASH_PAGE)

    with app.app_context():
        erased: Users = Users.query.get(user_id)
        assert is_tombstoned(user=erased)
        assert erased.email_validated is False
        # Solo UTub deleted; shared UTub transferred to the other member.
        assert Utubs.query.get(solo_utub_id) is None
        transferred: Utubs = Utubs.query.get(shared_utub_id)
        assert transferred is not None
        assert transferred.utub_creator == other_id
        # Self-actor GDPR audit trail (DD-4) written via the callback path.
        audit_row: AuditLog | None = AuditLog.query.filter_by(
            action=ACCOUNT_AUDIT_ACTIONS.SELF_ACCOUNT_ERASE
        ).first()
        assert audit_row is not None
        assert audit_row.actor_id == user_id
        assert audit_row.log_metadata.get("utubs_deleted") == 1
        assert audit_row.log_metadata.get("ownerships_transferred") == 1


def test_oauth_only_deactivate_callback_subject_mismatch_no_removal(
    oauth_only_google_user_logged_in: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A proof callback resolving a DIFFERENT google subject than the account's
    linked identity performs no removal — it redirects to Settings with a
    proof-mismatch error and leaves the account active."""
    client, csrf_token, user, app = oauth_only_google_user_logged_in
    user_id = user.id

    assert _initiate_oauth_deactivate(client, csrf_token, user_id).status_code == 200

    callback_response = _drive_google_proof_callback(
        client, subject=_MISMATCHED_GOOGLE_SUBJECT, email=_OAUTH_ONLY_EMAIL
    )

    assert callback_response.status_code == 302
    assert callback_response.location == url_for(
        ROUTES.USERS.SETTINGS, link_error="proof_mismatch"
    )

    with app.app_context():
        untouched: Users = Users.query.get(user_id)
        assert untouched.is_suspended is False
        assert untouched.self_deactivated_at is None


def test_oauth_only_delete_callback_expired_intent_no_removal(
    oauth_only_google_user_logged_in: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """An expired removal intent is rejected generically (the shared
    pop/peek validity check drops it), so the callback performs no erasure."""
    client, csrf_token, user, app = oauth_only_google_user_logged_in
    user_id = user.id

    # Stash a removal intent whose issued_at is far in the past (well beyond the
    # 600s OAUTH_LINK_MAX_AGE_SECONDS window).
    with client.session_transaction() as flask_session:
        flask_session[OAUTH_LINK_INTENT_SESSION_KEY] = {
            "action": REMOVAL_INTENT_ACTION_DELETE,
            "user_id": user_id,
            "proof_provider": "google",
            "issued_at": utc_now().timestamp() - 10_000,
        }

    with mock.patch(_GOOGLE_AUTHORIZE_ACCESS_TOKEN_TARGET) as mock_token:
        mock_token.return_value = _build_mocked_google_token(
            subject=_OAUTH_ONLY_GOOGLE_SUBJECT, email=_OAUTH_ONLY_EMAIL
        )
        callback_response = client.get(
            url_for(OAUTH_ROUTES.GOOGLE_CALLBACK, code=_FAKE_CODE, state=_FAKE_STATE)
        )

    assert callback_response.status_code == 302
    with app.app_context():
        assert not is_tombstoned(user=Users.query.get(user_id))


def test_oauth_only_deactivate_callback_sole_admin_rechecked_at_execution(
    oauth_only_google_user_logged_in: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """DD-17: the sole-admin guard is re-checked at callback (execution) time,
    not just at initiation. Promoting the user to sole active admin AFTER the
    redirect but BEFORE the callback makes the callback reject the removal with
    403 SOLE_ADMIN_CANNOT_LEAVE instead of completing it."""
    client, csrf_token, user, app = oauth_only_google_user_logged_in
    user_id = user.id

    # Initiate while still a non-admin (guard 2 passes, intent is stashed).
    assert _initiate_oauth_deactivate(client, csrf_token, user_id).status_code == 200

    # State changes mid-flight: the user becomes the only active admin.
    with app.app_context():
        promoted: Users = Users.query.get(user_id)
        promoted.role = User_Role.ADMIN
        db.session.commit()

    callback_response = _drive_google_proof_callback(
        client, subject=_OAUTH_ONLY_GOOGLE_SUBJECT, email=_OAUTH_ONLY_EMAIL
    )

    assert callback_response.status_code == 403
    assert (
        callback_response.get_json()[STD_JSON.MESSAGE]
        == USER_FAILURE.SOLE_ADMIN_CANNOT_LEAVE
    )

    with app.app_context():
        untouched: Users = Users.query.get(user_id)
        assert untouched.is_suspended is False
        assert untouched.self_deactivated_at is None


# --------------------------------------------------------------------------- #
# DD-15: a PASSWORD account never takes the OAuth-only branch (never stashes a
# removal intent) — the precise proxy for "did not take the OAuth-only path".
# --------------------------------------------------------------------------- #


def _password_login_payload() -> dict[str, str]:
    return {"currentPassword": valid_user_1[model_strs.PASSWORD]}


def test_password_deactivate_never_stashes_removal_intent(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A password account's deactivate completes inline and never writes the
    removal-intent session key (DD-15)."""
    client, csrf_token, user, _ = login_first_user_with_register

    response = client.put(
        url_for(ROUTES.USERS.DEACTIVATE_ACCOUNT, user_id=user.id),
        json=_password_login_payload(),
        headers={"X-CSRFToken": csrf_token},
    )
    assert response.status_code == 200

    with client.session_transaction() as flask_session:
        assert OAUTH_LINK_INTENT_SESSION_KEY not in flask_session


def test_password_delete_never_stashes_removal_intent(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A password account's delete completes inline and never writes the
    removal-intent session key (DD-15)."""
    client, csrf_token, user, _ = login_first_user_with_register

    response = client.delete(
        url_for(ROUTES.USERS.DELETE_ACCOUNT, user_id=user.id),
        json={
            "currentPassword": valid_user_1[model_strs.PASSWORD],
            "confirmUsername": valid_user_1[LOGIN_FORM.USERNAME],
        },
        headers={"X-CSRFToken": csrf_token},
    )
    assert response.status_code == 200

    with client.session_transaction() as flask_session:
        assert OAUTH_LINK_INTENT_SESSION_KEY not in flask_session
