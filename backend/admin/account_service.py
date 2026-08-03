"""Admin account-lifecycle service: suspend, unsuspend, kill sessions, force reset.

Each function:
  - accepts keyword-only args, carries full typehints, returns FlaskResponse
  - enforces reject_self_action before any other guard or DB access
  - returns 404 via build_message_error_response when the target user is missing
  - audits exactly once per successful state-changing action
  - lands all mutations and the audit row in a single db.session.commit()
  - no-ops idempotent state actions with a clear 200 message and no audit row
"""

from __future__ import annotations

from flask import current_app, url_for

from backend import db
from backend.admin.constants import AdminActionErrorCodes
from backend.admin.guards import reject_leaving_zero_active_admins, reject_self_action
from backend.api_common.responses import FlaskResponse
from backend.api_v1.services.tokens import mark_all_refresh_tokens_revoked_for_user
from backend.extensions import audit
from backend.extensions.extension_utils import safe_get_email_sender
from backend.models.forgot_passwords import Forgot_Passwords
from backend.models.users import Users
from backend.schemas.admin_actions import AdminActionResponseSchema
from backend.schemas.errors import build_message_error_response
from backend.utils.all_routes import ROUTES
from backend.utils.datetime_utils import utc_now
from backend.utils.strings.admin_portal_strs import (
    ADMIN_ACTION_STRINGS,
    ADMIN_AUDIT_ACTIONS,
)
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON


def suspend_user(*, actor_id: int, target_user_id: int, reason: str) -> FlaskResponse:
    """Suspend a user account, invalidating their web sessions and revoking API tokens.

    Enforces self-action guard and last-admin guard before acting. Idempotent:
    if the user is already suspended, returns a clear no-op 200 with no audit row.
    On a real state change, sets ``is_suspended=True``, stamps
    ``sessions_invalidated_at``, revokes all refresh tokens, audits, and commits.

    Args:
        actor_id:       ID of the admin performing the action.
        target_user_id: Primary key of the user to suspend.
        reason:         Required human-readable reason recorded in the audit log.

    Returns:
        200 JSON envelope on success or no-op.
        403 when actor targets themselves, or when no other active admin exists.
        404 when the target user does not exist.
    """
    self_action_error: FlaskResponse | None = reject_self_action(
        actor_id=actor_id, target_user_id=target_user_id
    )
    if self_action_error is not None:
        return self_action_error

    target_user: Users | None = Users.query.get(target_user_id)
    if target_user is None:
        return build_message_error_response(
            message=ADMIN_ACTION_STRINGS.MOD_TARGET_NOT_FOUND,
            error_code=AdminActionErrorCodes.TARGET_NOT_FOUND,
            status_code=404,
        )

    last_admin_error: FlaskResponse | None = reject_leaving_zero_active_admins(
        target_user=target_user
    )
    if last_admin_error is not None:
        return last_admin_error

    if target_user.is_suspended:
        return AdminActionResponseSchema(
            status=STD_JSON.SUCCESS,
            message=ADMIN_ACTION_STRINGS.ACCOUNT_SUSPEND_NOOP,
        ).to_response()

    target_user.is_suspended = True
    target_user.sessions_invalidated_at = utc_now()
    revoked_count: int = mark_all_refresh_tokens_revoked_for_user(
        user_id=target_user_id
    )
    audit.record(
        actor_id=actor_id,
        action=ADMIN_AUDIT_ACTIONS.USER_SUSPEND,
        target_type="User",
        target_id=str(target_user_id),
        metadata={"reason": reason, "api_tokens_revoked": revoked_count},
    )
    db.session.commit()
    return AdminActionResponseSchema(
        status=STD_JSON.SUCCESS,
        message=ADMIN_ACTION_STRINGS.ACCOUNT_SUSPEND_SUCCESS,
    ).to_response()


def unsuspend_user(*, actor_id: int, target_user_id: int, reason: str) -> FlaskResponse:
    """Lift a user's suspension, allowing them to log in and use the app again.

    Idempotent: if the user is not suspended, returns a clear no-op 200 with
    no audit row. On a real state change, sets ``is_suspended=False``, audits,
    and commits. ``sessions_invalidated_at`` is intentionally left untouched
    because there are no live sessions to invalidate for a suspended user.

    Args:
        actor_id:       ID of the admin performing the action.
        target_user_id: Primary key of the user to unsuspend.
        reason:         Required human-readable reason recorded in the audit log.

    Returns:
        200 JSON envelope on success or no-op.
        403 when actor targets themselves.
        404 when the target user does not exist.
    """
    self_action_error: FlaskResponse | None = reject_self_action(
        actor_id=actor_id, target_user_id=target_user_id
    )
    if self_action_error is not None:
        return self_action_error

    target_user: Users | None = Users.query.get(target_user_id)
    if target_user is None:
        return build_message_error_response(
            message=ADMIN_ACTION_STRINGS.MOD_TARGET_NOT_FOUND,
            error_code=AdminActionErrorCodes.TARGET_NOT_FOUND,
            status_code=404,
        )

    if not target_user.is_suspended:
        return AdminActionResponseSchema(
            status=STD_JSON.SUCCESS,
            message=ADMIN_ACTION_STRINGS.ACCOUNT_UNSUSPEND_NOOP,
        ).to_response()

    target_user.is_suspended = False
    audit.record(
        actor_id=actor_id,
        action=ADMIN_AUDIT_ACTIONS.USER_UNSUSPEND,
        target_type="User",
        target_id=str(target_user_id),
        metadata={"reason": reason},
    )
    db.session.commit()
    return AdminActionResponseSchema(
        status=STD_JSON.SUCCESS,
        message=ADMIN_ACTION_STRINGS.ACCOUNT_UNSUSPEND_SUCCESS,
    ).to_response()


def kill_user_sessions(
    *, actor_id: int, target_user_id: int, reason: str
) -> FlaskResponse:
    """Invalidate all web sessions and revoke all API refresh tokens for a user.

    Not state-gated — always acts, so calling this twice produces two audit rows.
    Stamps ``sessions_invalidated_at`` with the current UTC time and revokes all
    unrevoked ``ApiRefreshTokens`` rows for the user.

    Args:
        actor_id:       ID of the admin performing the action.
        target_user_id: Primary key of the target user.
        reason:         Required human-readable reason recorded in the audit log.

    Returns:
        200 JSON envelope with count=number of API tokens revoked.
        403 when actor targets themselves.
        404 when the target user does not exist.
    """
    self_action_error: FlaskResponse | None = reject_self_action(
        actor_id=actor_id, target_user_id=target_user_id
    )
    if self_action_error is not None:
        return self_action_error

    target_user: Users | None = Users.query.get(target_user_id)
    if target_user is None:
        return build_message_error_response(
            message=ADMIN_ACTION_STRINGS.MOD_TARGET_NOT_FOUND,
            error_code=AdminActionErrorCodes.TARGET_NOT_FOUND,
            status_code=404,
        )

    target_user.sessions_invalidated_at = utc_now()
    revoked_count: int = mark_all_refresh_tokens_revoked_for_user(
        user_id=target_user_id
    )
    audit.record(
        actor_id=actor_id,
        action=ADMIN_AUDIT_ACTIONS.USER_KILL_SESSIONS,
        target_type="User",
        target_id=str(target_user_id),
        metadata={"reason": reason, "api_tokens_revoked": revoked_count},
    )
    db.session.commit()
    return AdminActionResponseSchema(
        status=STD_JSON.SUCCESS,
        message=ADMIN_ACTION_STRINGS.ACCOUNT_KILL_SESSIONS_SUCCESS.format(
            count=revoked_count
        ),
        count=revoked_count,
    ).to_response()


def force_password_reset(
    *, actor_id: int, target_user_id: int, reason: str
) -> FlaskResponse:
    """Force a password-reset email for a user and kill their existing sessions.

    Guards:
    - Rejects self-action.
    - Returns 404 when the user does not exist.
    - Returns 400 when the account has no local password (OAuth-only).

    Bypasses all rate limits: creates a fresh ``Forgot_Passwords`` row when
    absent, or resets an existing one (``attempts=0``, fresh token,
    ``initial_attempt=now``). Sends the reset email without incrementing
    attempts. If the email send returns a status >= 500 the session is rolled
    back and a 502 error is returned — no DB changes are committed.

    On email success, kills web sessions (``sessions_invalidated_at``) and
    revokes all API refresh tokens, audits, and commits everything atomically.

    Args:
        actor_id:       ID of the admin performing the action.
        target_user_id: Primary key of the target user.
        reason:         Required human-readable reason recorded in the audit log.

    Returns:
        200 JSON envelope on success.
        400 when the account is OAuth-only (no password).
        403 when actor targets themselves.
        404 when the target user does not exist.
        502 when the password-reset email fails to send (changes rolled back).
    """
    self_action_error: FlaskResponse | None = reject_self_action(
        actor_id=actor_id, target_user_id=target_user_id
    )
    if self_action_error is not None:
        return self_action_error

    target_user: Users | None = Users.query.get(target_user_id)
    if target_user is None:
        return build_message_error_response(
            message=ADMIN_ACTION_STRINGS.MOD_TARGET_NOT_FOUND,
            error_code=AdminActionErrorCodes.TARGET_NOT_FOUND,
            status_code=404,
        )

    if target_user.password is None:
        return build_message_error_response(
            message=ADMIN_ACTION_STRINGS.ACCOUNT_FORCE_RESET_OAUTH_ONLY,
            error_code=AdminActionErrorCodes.OAUTH_ONLY_ACCOUNT,
            status_code=400,
        )

    # Create or reset the Forgot_Passwords row, bypassing all rate limits.
    existing_forgot_password: Forgot_Passwords | None = target_user.forgot_password
    if existing_forgot_password is not None:
        existing_forgot_password.attempts = 0
        existing_forgot_password.reset_token = target_user.get_password_reset_token()
        existing_forgot_password.initial_attempt = utc_now()
        forgot_password_obj: Forgot_Passwords = existing_forgot_password
    else:
        new_token: str = target_user.get_password_reset_token()
        forgot_password_obj = Forgot_Passwords(reset_token=new_token)
        target_user.forgot_password = forgot_password_obj
        db.session.add(forgot_password_obj)

    # Flush so the Forgot_Passwords row gets an ID if new, before building the URL.
    db.session.flush()

    reset_url: str = url_for(
        ROUTES.SPLASH.RESET_PASSWORD,
        token=forgot_password_obj.reset_token,
        _external=True,
    )
    email_sender = safe_get_email_sender(current_app)
    email_send_result = email_sender.send_password_reset_email(
        target_user.email,
        target_user.username,
        reset_url,
    )

    if email_send_result.status_code >= 500:
        db.session.rollback()
        return build_message_error_response(
            message=ADMIN_ACTION_STRINGS.ACCOUNT_FORCE_RESET_EMAIL_FAILURE,
            error_code=AdminActionErrorCodes.EMAIL_SEND_FAILURE,
            status_code=502,
        )

    target_user.sessions_invalidated_at = utc_now()
    revoked_count: int = mark_all_refresh_tokens_revoked_for_user(
        user_id=target_user_id
    )
    audit.record(
        actor_id=actor_id,
        action=ADMIN_AUDIT_ACTIONS.USER_FORCE_RESET,
        target_type="User",
        target_id=str(target_user_id),
        metadata={"reason": reason, "api_tokens_revoked": revoked_count},
    )
    db.session.commit()
    return AdminActionResponseSchema(
        status=STD_JSON.SUCCESS,
        message=ADMIN_ACTION_STRINGS.ACCOUNT_FORCE_RESET_SUCCESS,
    ).to_response()
