"""Integration tests for admin account-lifecycle POST endpoints.

Covered endpoints:
    POST /admin/users/<int:target_user_id>/suspend
    POST /admin/users/<int:target_user_id>/unsuspend
    POST /admin/users/<int:target_user_id>/force-reset
    POST /admin/users/<int:target_user_id>/kill-sessions
"""

from __future__ import annotations

from datetime import timedelta
from typing import Tuple

import pytest
from flask import Flask, g, url_for
from flask.testing import FlaskClient
from requests import Response

from backend import db
from backend.admin.account_service import suspend_user
from backend.admin.constants import AdminActionErrorCodes
from backend.api_v1.services.tokens import issue_refresh_token
from backend.extensions.email_sender.email_sender import EmailSender
from backend.models.api_refresh_tokens import ApiRefreshTokens
from backend.models.audit_log import AuditLog
from backend.models.forgot_passwords import Forgot_Passwords
from backend.models.users import User_Role, Users
from backend.utils import constants as U4I_CONSTANTS
from backend.utils.all_routes import ROUTES
from backend.utils.datetime_utils import utc_now
from backend.utils.strings.admin_portal_strs import (
    ADMIN_ACTION_STRINGS,
    ADMIN_AUDIT_ACTIONS,
)
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from tests.conftest import AjaxFlaskLoginClient
from tests.utils_for_test import get_csrf_token

pytestmark = pytest.mark.admin

USER_CONSTANTS = U4I_CONSTANTS.USER_CONSTANTS

# ---------------------------------------------------------------------------
# Account endpoint URL templates
# ---------------------------------------------------------------------------

_ACCOUNT_SUSPEND_URL: str = "/admin/users/{target_user_id}/suspend"
_ACCOUNT_UNSUSPEND_URL: str = "/admin/users/{target_user_id}/unsuspend"
_ACCOUNT_FORCE_RESET_URL: str = "/admin/users/{target_user_id}/force-reset"
_ACCOUNT_KILL_SESSIONS_URL: str = "/admin/users/{target_user_id}/kill-sessions"

_MOCK_REASON: str = "integration test account lifecycle"
_OVERLONG_REASON: str = "x" * 501
_WHITESPACE_ONLY_REASON: str = "   "

# Representative formatted URLs for parametrized auth and reason guard tests.
_ALL_ACCOUNT_URLS: list[str] = [
    _ACCOUNT_SUSPEND_URL.format(target_user_id=9999),
    _ACCOUNT_UNSUSPEND_URL.format(target_user_id=9999),
    _ACCOUNT_FORCE_RESET_URL.format(target_user_id=9999),
    _ACCOUNT_KILL_SESSIONS_URL.format(target_user_id=9999),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _post_account(
    client: FlaskClient,
    url: str,
    csrf: str,
    reason: str | None = _MOCK_REASON,
) -> object:
    """POST an account-lifecycle endpoint with an optional reason payload."""
    payload: dict = {}
    if reason is not None:
        payload["reason"] = reason
    return client.post(url, json=payload, headers={"X-CSRFToken": csrf})


def _seed_target_user(app: Flask) -> Users:
    """Create a regular (non-admin) email-validated user and return it."""
    with app.app_context():
        target = Users(
            username="acct_target_user",
            email="acct_target@test.com",
            plaintext_password="TestPass1!",
        )
        target.email_validated = True
        db.session.add(target)
        db.session.commit()
        db.session.refresh(target)
        return target


def _seed_unrevoked_token(app: Flask, target_user: Users) -> ApiRefreshTokens:
    """Issue one unrevoked refresh token for target_user and return the row."""
    with app.app_context():
        target_refreshed: Users = Users.query.get(target_user.id)
        issue_refresh_token(user=target_refreshed)
        token_row: ApiRefreshTokens = ApiRefreshTokens.query.filter_by(
            user_id=target_user.id
        ).first()
        db.session.refresh(token_row)
        return token_row


def _clear_flask_login_request_cache() -> None:
    """Drop Flask-Login's per-request user cache (``g._login_user``).

    The test harness keeps one app context alive for the whole test
    (db_transaction fixture), so Flask-Login's per-request ``g`` cache
    persists across sequential test-client requests — something that never
    happens in production. Clearing it forces the next request to consult
    the user_loader again, matching production per-request behavior.
    """
    if hasattr(g, "_login_user"):
        delattr(g, "_login_user")


# ---------------------------------------------------------------------------
# Happy-path: suspend
# ---------------------------------------------------------------------------


def test_admin_account_suspend_happy_path(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in admin and an existing non-suspended user with one active refresh token
    WHEN POST /admin/users/<id>/suspend with a reason
    THEN 200 JSON success; is_suspended=True; sessions_invalidated_at set;
         refresh token revoked; one audit row with action USER_SUSPEND and
         api_tokens_revoked=1 in metadata.
    """
    client, csrf, admin_user, app = login_admin_user_with_register
    target = _seed_target_user(app)
    token_row = _seed_unrevoked_token(app, target)

    with app.app_context():
        target_before: Users = Users.query.get(target.id)
        assert not target_before.is_suspended
        audit_rows_before: int = AuditLog.query.count()
    assert audit_rows_before == 0

    response = _post_account(
        client,
        _ACCOUNT_SUSPEND_URL.format(target_user_id=target.id),
        csrf,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert body[STD_JSON.MESSAGE] == ADMIN_ACTION_STRINGS.ACCOUNT_SUSPEND_SUCCESS

    with app.app_context():
        refreshed: Users = Users.query.get(target.id)
        assert refreshed.is_suspended is True
        assert refreshed.sessions_invalidated_at is not None

        refreshed_token: ApiRefreshTokens = ApiRefreshTokens.query.get(token_row.id)
        assert refreshed_token.revoked_at is not None

        audit_row: AuditLog | None = AuditLog.query.first()
    assert audit_row is not None
    assert audit_row.action == ADMIN_AUDIT_ACTIONS.USER_SUSPEND
    assert audit_row.actor_id == admin_user.id
    assert audit_row.target_id == str(target.id)
    assert audit_row.log_metadata is not None
    assert audit_row.log_metadata.get("reason") == _MOCK_REASON
    assert audit_row.log_metadata.get("api_tokens_revoked") == 1


def test_admin_account_suspend_idempotent_noop(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an already-suspended user
    WHEN POST /admin/users/<id>/suspend
    THEN 200 no-op message; exactly one audit row from the first suspension only;
         is_suspended remains True.
    """
    client, csrf, _, app = login_admin_user_with_register
    target = _seed_target_user(app)

    # First suspension (state-changing).
    first_response = _post_account(
        client,
        _ACCOUNT_SUSPEND_URL.format(target_user_id=target.id),
        csrf,
    )
    assert first_response.status_code == 200

    with app.app_context():
        audit_count_after_first: int = AuditLog.query.count()
    assert audit_count_after_first == 1

    # Second suspension (idempotent no-op).
    second_response = _post_account(
        client,
        _ACCOUNT_SUSPEND_URL.format(target_user_id=target.id),
        csrf,
    )

    assert second_response.status_code == 200
    body = second_response.get_json()
    assert body[STD_JSON.MESSAGE] == ADMIN_ACTION_STRINGS.ACCOUNT_SUSPEND_NOOP

    with app.app_context():
        audit_count_after_second: int = AuditLog.query.count()
        assert audit_count_after_second == 1
        assert Users.query.get(target.id).is_suspended is True


# ---------------------------------------------------------------------------
# Happy-path: unsuspend
# ---------------------------------------------------------------------------


def test_admin_account_unsuspend_happy_path(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a suspended user
    WHEN POST /admin/users/<id>/unsuspend with a reason
    THEN 200 JSON success; is_suspended=False; one audit row USER_UNSUSPEND.
    """
    client, csrf, admin_user, app = login_admin_user_with_register
    target = _seed_target_user(app)

    # Put target into suspended state.
    with app.app_context():
        target_user_to_suspend: Users = Users.query.get(target.id)
        target_user_to_suspend.is_suspended = True
        db.session.commit()

    response = _post_account(
        client,
        _ACCOUNT_UNSUSPEND_URL.format(target_user_id=target.id),
        csrf,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert body[STD_JSON.MESSAGE] == ADMIN_ACTION_STRINGS.ACCOUNT_UNSUSPEND_SUCCESS

    with app.app_context():
        refreshed: Users = Users.query.get(target.id)
        assert refreshed.is_suspended is False

        audit_row: AuditLog | None = AuditLog.query.first()
    assert audit_row is not None
    assert audit_row.action == ADMIN_AUDIT_ACTIONS.USER_UNSUSPEND
    assert audit_row.actor_id == admin_user.id


def test_admin_account_unsuspend_idempotent_noop(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a user who is already not suspended (default state)
    WHEN POST /admin/users/<id>/unsuspend
    THEN 200 no-op message; NO audit row written; is_suspended remains False.
    """
    client, csrf, _, app = login_admin_user_with_register
    target = _seed_target_user(app)

    response = _post_account(
        client,
        _ACCOUNT_UNSUSPEND_URL.format(target_user_id=target.id),
        csrf,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body[STD_JSON.MESSAGE] == ADMIN_ACTION_STRINGS.ACCOUNT_UNSUSPEND_NOOP

    with app.app_context():
        assert AuditLog.query.count() == 0
        assert Users.query.get(target.id).is_suspended is False


# ---------------------------------------------------------------------------
# Happy-path: kill-sessions
# ---------------------------------------------------------------------------


def test_admin_account_kill_sessions_happy_path(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a user with one active refresh token
    WHEN POST /admin/users/<id>/kill-sessions with a reason
    THEN 200 JSON success with count=1; sessions_invalidated_at set;
         refresh token revoked; one audit row USER_KILL_SESSIONS with api_tokens_revoked=1.
    """
    client, csrf, admin_user, app = login_admin_user_with_register
    target = _seed_target_user(app)
    token_row = _seed_unrevoked_token(app, target)

    with app.app_context():
        assert AuditLog.query.count() == 0
        assert Users.query.get(target.id).sessions_invalidated_at is None

    response = _post_account(
        client,
        _ACCOUNT_KILL_SESSIONS_URL.format(target_user_id=target.id),
        csrf,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert body[
        STD_JSON.MESSAGE
    ] == ADMIN_ACTION_STRINGS.ACCOUNT_KILL_SESSIONS_SUCCESS.format(count=1)
    assert body.get("count") == 1

    with app.app_context():
        refreshed: Users = Users.query.get(target.id)
        assert refreshed.sessions_invalidated_at is not None

        refreshed_token: ApiRefreshTokens = ApiRefreshTokens.query.get(token_row.id)
        assert refreshed_token.revoked_at is not None

        audit_row: AuditLog | None = AuditLog.query.first()
    assert audit_row is not None
    assert audit_row.action == ADMIN_AUDIT_ACTIONS.USER_KILL_SESSIONS
    assert audit_row.actor_id == admin_user.id
    assert audit_row.log_metadata is not None
    assert audit_row.log_metadata.get("api_tokens_revoked") == 1


def test_admin_account_kill_sessions_acts_twice_two_audit_rows(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a user with kill-sessions called once successfully
    WHEN POST /admin/users/<id>/kill-sessions a second time
    THEN 200 both times; two audit rows total — kill-sessions is never a no-op.
    """
    client, csrf, _, app = login_admin_user_with_register
    target = _seed_target_user(app)

    first_response = _post_account(
        client,
        _ACCOUNT_KILL_SESSIONS_URL.format(target_user_id=target.id),
        csrf,
    )
    assert first_response.status_code == 200

    second_response = _post_account(
        client,
        _ACCOUNT_KILL_SESSIONS_URL.format(target_user_id=target.id),
        csrf,
    )
    assert second_response.status_code == 200

    with app.app_context():
        audit_count: int = AuditLog.query.filter_by(
            action=ADMIN_AUDIT_ACTIONS.USER_KILL_SESSIONS
        ).count()
    assert audit_count == 2


# ---------------------------------------------------------------------------
# Happy-path: force-reset
# ---------------------------------------------------------------------------


def test_admin_account_force_reset_creates_forgot_passwords_row(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a user with a local password and no existing Forgot_Passwords row
    WHEN POST /admin/users/<id>/force-reset with a reason
    THEN 200 JSON success; Forgot_Passwords row created with attempts=0;
         sessions_invalidated_at set; one audit row USER_FORCE_RESET.
    """
    client, csrf, admin_user, app = login_admin_user_with_register
    target = _seed_target_user(app)

    with app.app_context():
        target_before: Users = Users.query.get(target.id)
        assert target_before.forgot_password is None
        assert target_before.sessions_invalidated_at is None

    response = _post_account(
        client,
        _ACCOUNT_FORCE_RESET_URL.format(target_user_id=target.id),
        csrf,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert body[STD_JSON.MESSAGE] == ADMIN_ACTION_STRINGS.ACCOUNT_FORCE_RESET_SUCCESS

    with app.app_context():
        refreshed: Users = Users.query.get(target.id)
        assert refreshed.sessions_invalidated_at is not None

        fp_row: Forgot_Passwords | None = refreshed.forgot_password
    assert fp_row is not None
    assert fp_row.attempts == 0

    with app.app_context():
        audit_row: AuditLog | None = AuditLog.query.filter_by(
            action=ADMIN_AUDIT_ACTIONS.USER_FORCE_RESET
        ).first()
    assert audit_row is not None
    assert audit_row.actor_id == admin_user.id
    assert audit_row.log_metadata is not None
    assert audit_row.log_metadata.get("reason") == _MOCK_REASON


def test_admin_account_force_reset_replaces_rate_limited_row(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a user with a Forgot_Passwords row at the rate-limit cap (attempts=5)
    WHEN POST /admin/users/<id>/force-reset
    THEN 200 JSON success; existing row has attempts=0 and a fresh reset_token
         (proving rate limits were bypassed).
    """
    client, csrf, _, app = login_admin_user_with_register
    target = _seed_target_user(app)

    with app.app_context():
        target_refreshed: Users = Users.query.get(target.id)
        old_token: str = target_refreshed.get_password_reset_token()
        fp = Forgot_Passwords(reset_token=old_token)
        fp.attempts = USER_CONSTANTS.PASSWORD_RESET_ATTEMPTS
        fp.initial_attempt = utc_now() - timedelta(seconds=10)
        target_refreshed.forgot_password = fp
        db.session.add(fp)
        db.session.commit()

    with app.app_context():
        fp_before: Forgot_Passwords = Users.query.get(target.id).forgot_password
        assert fp_before.attempts == USER_CONSTANTS.PASSWORD_RESET_ATTEMPTS
        token_before: str = fp_before.reset_token

    response = _post_account(
        client,
        _ACCOUNT_FORCE_RESET_URL.format(target_user_id=target.id),
        csrf,
    )

    assert response.status_code == 200

    with app.app_context():
        fp_after: Forgot_Passwords = Users.query.get(target.id).forgot_password
    assert fp_after is not None
    assert fp_after.attempts == 0
    assert fp_after.reset_token != token_before


def test_admin_account_force_reset_email_failure_rollback(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN a target user with no existing Forgot_Passwords row and the email sender
         monkeypatched to return status_code 500
    WHEN POST /admin/users/<id>/force-reset with a reason
    THEN 502 JSON with EMAIL_SEND_FAILURE error code; the Forgot_Passwords row is NOT
         persisted (rollback occurred); sessions_invalidated_at remains None;
         no AuditLog row written.
    """
    client, csrf, _, app = login_admin_user_with_register
    target = _seed_target_user(app)

    with app.app_context():
        target_before: Users = Users.query.get(target.id)
        assert target_before.forgot_password is None
        assert target_before.sessions_invalidated_at is None

    failing_email_response = Response()
    failing_email_response.status_code = 500

    monkeypatch.setattr(
        EmailSender,
        "send_password_reset_email",
        lambda self, *args, **kwargs: failing_email_response,
    )

    response = _post_account(
        client,
        _ACCOUNT_FORCE_RESET_URL.format(target_user_id=target.id),
        csrf,
    )

    assert response.status_code == 502
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        body[STD_JSON.MESSAGE] == ADMIN_ACTION_STRINGS.ACCOUNT_FORCE_RESET_EMAIL_FAILURE
    )
    assert body[STD_JSON.ERROR_CODE] == int(AdminActionErrorCodes.EMAIL_SEND_FAILURE)

    with app.app_context():
        refreshed: Users = Users.query.get(target.id)
        assert refreshed.forgot_password is None
        assert refreshed.sessions_invalidated_at is None
        assert AuditLog.query.count() == 0


def test_admin_account_force_reset_oauth_only_returns_400(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a user whose password column is None (OAuth-only account)
    WHEN POST /admin/users/<id>/force-reset
    THEN 400 JSON with OAUTH_ONLY_ACCOUNT error code; no audit row written;
         no Forgot_Passwords row created.
    """
    client, csrf, _, app = login_admin_user_with_register

    with app.app_context():
        oauth_user = Users(
            username="acct_oauth_user",
            email="acct_oauth@test.com",
            plaintext_password=None,
        )
        oauth_user.email_validated = True
        db.session.add(oauth_user)
        db.session.commit()
        oauth_user_id: int = oauth_user.id

    with app.app_context():
        assert AuditLog.query.count() == 0

    response = _post_account(
        client,
        _ACCOUNT_FORCE_RESET_URL.format(target_user_id=oauth_user_id),
        csrf,
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert body[STD_JSON.MESSAGE] == ADMIN_ACTION_STRINGS.ACCOUNT_FORCE_RESET_OAUTH_ONLY
    assert body[STD_JSON.ERROR_CODE] == int(AdminActionErrorCodes.OAUTH_ONLY_ACCOUNT)

    with app.app_context():
        assert AuditLog.query.count() == 0
        assert Users.query.get(oauth_user_id).forgot_password is None


# ---------------------------------------------------------------------------
# Self-action guard: all four endpoints return 403 and produce no audit row
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url_template",
    [
        _ACCOUNT_SUSPEND_URL,
        _ACCOUNT_UNSUSPEND_URL,
        _ACCOUNT_FORCE_RESET_URL,
        _ACCOUNT_KILL_SESSIONS_URL,
    ],
)
def test_admin_account_self_action_returns_403(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    url_template: str,
) -> None:
    """
    GIVEN a logged-in admin
    WHEN POSTing any account-lifecycle endpoint targeting THEIR OWN user ID
    THEN 403 JSON with SELF_ACTION_FORBIDDEN message; no audit row; no state change.
    """
    client, csrf, admin_user, app = login_admin_user_with_register
    url: str = url_template.format(target_user_id=admin_user.id)

    with app.app_context():
        assert AuditLog.query.count() == 0

    response = _post_account(client, url, csrf)

    assert response.status_code == 403
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert body[STD_JSON.MESSAGE] == ADMIN_ACTION_STRINGS.SELF_ACTION_FORBIDDEN
    assert body[STD_JSON.ERROR_CODE] == int(AdminActionErrorCodes.SELF_ACTION_FORBIDDEN)

    with app.app_context():
        assert AuditLog.query.count() == 0


# ---------------------------------------------------------------------------
# 404 for unknown target user
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("account_url", _ALL_ACCOUNT_URLS)
def test_admin_account_missing_target_returns_404(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    account_url: str,
) -> None:
    """
    GIVEN a logged-in admin and a non-existent target user ID
    WHEN POSTing any account-lifecycle endpoint with that ID
    THEN 404 JSON; no audit row written.
    """
    client, csrf, _, app = login_admin_user_with_register

    response = _post_account(client, account_url, csrf)

    assert response.status_code == 404

    with app.app_context():
        assert AuditLog.query.count() == 0


# ---------------------------------------------------------------------------
# Required-reason schema validation: missing / whitespace / overlong
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("account_url", _ALL_ACCOUNT_URLS)
def test_admin_account_missing_reason_returns_400(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    account_url: str,
) -> None:
    """
    GIVEN a logged-in admin sending no reason field
    WHEN POSTing any account-lifecycle endpoint
    THEN 400 JSON (AdminReasonRequiredRequest rejects missing reason).
    """
    client, csrf, _, _ = login_admin_user_with_register

    response = _post_account(client, account_url, csrf, reason=None)

    assert response.status_code == 400


@pytest.mark.parametrize("account_url", _ALL_ACCOUNT_URLS)
def test_admin_account_whitespace_only_reason_returns_400(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    account_url: str,
) -> None:
    """
    GIVEN a logged-in admin sending a whitespace-only reason
    WHEN POSTing any account-lifecycle endpoint
    THEN 400 JSON (AdminReasonRequiredRequest rejects whitespace-only strings).
    """
    client, csrf, _, _ = login_admin_user_with_register

    response = _post_account(client, account_url, csrf, reason=_WHITESPACE_ONLY_REASON)

    assert response.status_code == 400


@pytest.mark.parametrize("account_url", _ALL_ACCOUNT_URLS)
def test_admin_account_overlong_reason_returns_400(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    account_url: str,
) -> None:
    """
    GIVEN a logged-in admin sending a 501-character reason
    WHEN POSTing any account-lifecycle endpoint
    THEN 400 JSON (field_validator rejects over-length reasons).
    """
    client, csrf, _, _ = login_admin_user_with_register

    response = _post_account(client, account_url, csrf, reason=_OVERLONG_REASON)

    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Auth guard: non-admin returns 404, anonymous returns 401
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("account_url", _ALL_ACCOUNT_URLS)
def test_admin_account_non_admin_returns_404(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    account_url: str,
) -> None:
    """
    GIVEN a logged-in non-admin user
    WHEN POSTing any account-lifecycle endpoint
    THEN 404 JSON (admin_required hides the admin surface from non-admins).
    """
    client, csrf, _, _ = login_first_user_with_register

    response = _post_account(client, account_url, csrf)

    assert response.status_code == 404


@pytest.mark.parametrize("account_url", _ALL_ACCOUNT_URLS)
def test_admin_account_anonymous_returns_401(
    client: FlaskClient,
    account_url: str,
) -> None:
    """
    GIVEN an unauthenticated (anonymous) session
    WHEN POSTing any account-lifecycle endpoint with a valid CSRF token
    THEN 401 JSON.
    """
    splash_response = client.get("/")
    csrf_token = get_csrf_token(splash_response.get_data(), meta_tag=True)

    response = client.post(
        account_url,
        json={"reason": _MOCK_REASON},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Service-level test: reject_leaving_zero_active_admins guard
# ---------------------------------------------------------------------------


def test_service_last_admin_guard_blocks_only_admin(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN one admin who is the only active (non-suspended) admin
    WHEN suspend_user is called directly (bypassing HTTP) with a different actor_id
    THEN service returns 403 with LAST_ADMIN_FORBIDDEN message and error code.

    GIVEN a second active admin is then added
    WHEN suspend_user is called again with the same arguments
    THEN service returns 200 (last-admin guard passes; target is now suspended).
    """
    _, _, admin_user, app = login_admin_user_with_register
    fake_actor_id: int = 99999  # bypasses self-action check; does not need to exist

    # Only one admin — guard must block.
    with app.app_context():
        response_single_admin = suspend_user(
            actor_id=fake_actor_id,
            target_user_id=admin_user.id,
            reason=_MOCK_REASON,
        )

    assert response_single_admin[1] == 403
    blocked_body = response_single_admin[0].get_json()
    assert blocked_body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert blocked_body[STD_JSON.MESSAGE] == ADMIN_ACTION_STRINGS.LAST_ADMIN_FORBIDDEN
    assert blocked_body[STD_JSON.ERROR_CODE] == int(
        AdminActionErrorCodes.LAST_ADMIN_FORBIDDEN
    )

    with app.app_context():
        assert AuditLog.query.count() == 0

    # Add a second unsuspended admin — guard must now pass.
    with app.app_context():
        second_admin = Users(
            username="second_admin_p6",
            email="second_admin_p6@test.com",
            plaintext_password="TestPass1!",
        )
        second_admin.role = User_Role.ADMIN
        second_admin.email_validated = True
        db.session.add(second_admin)
        db.session.commit()

    with app.app_context():
        response_two_admins = suspend_user(
            actor_id=fake_actor_id,
            target_user_id=admin_user.id,
            reason=_MOCK_REASON,
        )

    assert response_two_admins[1] == 200
    passed_body = response_two_admins[0].get_json()
    assert passed_body[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert passed_body[STD_JSON.MESSAGE] == ADMIN_ACTION_STRINGS.ACCOUNT_SUSPEND_SUCCESS


# ---------------------------------------------------------------------------
# Session-invalidation: suspended user's existing web session resolves anonymous
# ---------------------------------------------------------------------------


def test_suspended_user_existing_web_session_resolves_anonymous(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a target user with a live web session
    WHEN an admin suspends the target via POST /admin/users/<id>/suspend
    THEN the target's next request to a login-gated route redirects to login —
         the user_loader rejects the session issued before the suspension.
    """
    admin_client, csrf, _, app = login_admin_user_with_register
    target = _seed_target_user(app)

    with app.test_request_context():
        home_url: str = url_for(ROUTES.UTUBS.HOME)

    with app.app_context():
        target_refreshed: Users = Users.query.get(target.id)

    # Create the target client using FlaskLoginClient's session_transaction() path
    # (which sets the user_id in the session without CSRF) but WITHOUT a "with"
    # block — omitting "with" avoids preserve_context=True, so there is no
    # _cv_request ContextVar conflict with the admin_client fixture's already-
    # active preserved context.
    app.test_client_class = AjaxFlaskLoginClient
    target_client = app.test_client(user=target_refreshed)

    pre_suspend_response = target_client.get(home_url)
    assert pre_suspend_response.status_code == 200

    # After the target client's GET, g._login_user holds the target (non-admin)
    # user.  Clear it so the admin client's next POST resolves the session
    # cookie to the admin user, not the cached target.
    _clear_flask_login_request_cache()

    # Suspend the target via the admin client.
    admin_client.post(
        _ACCOUNT_SUSPEND_URL.format(target_user_id=target.id),
        json={"reason": _MOCK_REASON},
        headers={"X-CSRFToken": csrf},
    )

    # Clear again so the post-suspend GET re-loads the target from DB,
    # picking up the updated is_suspended / sessions_invalidated_at state.
    _clear_flask_login_request_cache()

    post_suspend_response = target_client.get(home_url)
    assert post_suspend_response.status_code == 302
