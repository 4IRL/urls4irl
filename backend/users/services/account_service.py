from __future__ import annotations

from typing import Any

from flask import current_app, url_for
from flask_login import current_user
from redis import Redis
from sqlalchemy.exc import IntegrityError

from backend import db
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.extensions.extension_utils import safe_get_email_sender
from backend.extensions.metrics.writer import record_event
from backend.metrics.events import EventName
from backend.models.users import Users
from backend.schemas.errors import (
    build_field_error_response,
    build_message_error_response,
)
from backend.schemas.users import (
    ChangeEmailResponseSchema,
    ChangePasswordResponseSchema,
    ChangeUsernameResponseSchema,
)
from backend.splash.constants import LOGIN_FAILURE_REASON_BAD_PASSWORD
from backend.users.constants import (
    ChangeEmailErrorCodes,
    ChangePasswordErrorCodes,
    ChangeUsernameErrorCodes,
)
from backend.utils.all_routes import ROUTES
from backend.utils.constants import USER_CONSTANTS
from backend.utils.datetime_utils import utc_now
from backend.utils.mailjet_utils import handle_mailjet_failure
from backend.utils.reauth_throttle import (
    clear_reauth_failures,
    is_reauth_locked_out,
    record_reauth_failure,
)
from backend.utils.session_utils import restamp_current_session
from backend.utils.strings.config_strs import CONFIG_ENVS
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.user_strs import (
    EMAIL_CHANGE_CONFIRMATION_SENT,
    EMAIL_CHANGE_NO_CHANGE,
    PASSWORD_CHANGE_SUCCESS,
    USER_FAILURE,
    USERNAME_CHANGE_NO_CHANGE,
    USERNAME_CHANGE_SUCCESS,
)

_MEMORY_URI: str = "memory://"


def build_account_info_context() -> dict[str, Any]:
    """Build the Settings page Account-info block template context for the
    authenticated user.

    Mirrors ``build_user_stats_context()`` — no parameters, reads
    ``current_user``, returns a flat dict of read-only account details. Keys are
    namespaced ``account_*`` so they never collide with the connected-accounts
    or stats context keys. Member-since is intentionally omitted here: the
    ``settings()`` route already splats ``build_user_stats_context()``, whose
    ``stats_member_since_iso`` / ``stats_member_since_exact`` values the
    account-info block reuses (no duplicate date formatting).
    """
    return {
        "account_username": current_user.username,
        "account_email": current_user.email,
        "account_email_validated": current_user.email_validated,
        # None when no change is in flight; the staged (lowercased) address
        # otherwise. Gates both the account-info pending indicator and the
        # in-form change-email warning (DD-16/DD-18) at initial page load.
        "account_pending_email": current_user.pending_email,
    }


def _build_rate_limit_redis() -> Redis | None:
    """Build a client on the shared enforcement Redis (``REDIS_URI``), or return
    ``None`` when Redis is unavailable.

    Mirrors ``backend/admin/ops_service.py:_build_metrics_redis`` but reads the
    shared ``REDIS_URI`` (enforcement) rather than the best-effort metrics Redis.
    Returns ``None`` when the URI is absent or the in-memory stub, so callers
    fail open (the username-change cap is anti-spam, not a security boundary).
    """
    redis_uri: str | None = current_app.config.get(CONFIG_ENVS.REDIS_URI)
    if not redis_uri or redis_uri == _MEMORY_URI:
        return None
    return Redis.from_url(redis_uri)


def apply_username_change(*, user_id: int, new_username: str) -> FlaskResponse:
    """Change the authenticated user's username (no password re-auth per
    Decision #1), rate-limited to ``MAX_USERNAME_CHANGES_PER_DAY`` per rolling
    24h per user via a Redis-only counter (Decision #4).

    Named ``apply_username_change`` to avoid a bare-name collision with the
    ``change_username`` route/view function on the ``users`` blueprint.

    Guard order (so a rejected/no-op attempt never burns a rate-limit slot):
    self-ownership → no-op → rate-limit precheck (fail-open) → uniqueness →
    commit (IntegrityError guard) → INCR (EXPIRE only on the first) → success.
    """
    # (1) Self-ownership: the URL user_id must be the acting user.
    if user_id != current_user.id:
        return build_message_error_response(
            message=USER_FAILURE.NOT_AUTHORIZED,
            error_code=ChangeUsernameErrorCodes.INVALID_FORM_INPUT,
            status_code=403,
        )

    # (2) No-op short-circuit: resubmitting the current username never burns a
    # slot and never touches Redis.
    if new_username == current_user.username:
        return APIResponse(
            status_code=200,
            data=ChangeUsernameResponseSchema(
                username=current_user.username,
                status=STD_JSON.NO_CHANGE,
                message=USERNAME_CHANGE_NO_CHANGE,
            ),
        ).to_response()

    rate_limit_key = f"username-change:{user_id}"
    redis_client = _build_rate_limit_redis()

    # (3) Rate-limit pre-check (fail-open): read the counter before committing so
    # the 4th change in the window is rejected without a DB write or an INCR.
    if redis_client is not None:
        try:
            current_count = int(redis_client.get(rate_limit_key) or 0)
            if current_count >= USER_CONSTANTS.MAX_USERNAME_CHANGES_PER_DAY:
                return build_message_error_response(
                    message=USER_FAILURE.USERNAME_CHANGE_RATE_LIMITED,
                    error_code=ChangeUsernameErrorCodes.RATE_LIMITED,
                    status_code=429,
                )
        except Exception as redis_error:
            current_app.logger.exception(
                "username-change rate-limit precheck failed (failing open): "
                f"{redis_error}"
            )

    # (4) Uniqueness (excluding the current user, so a no-op already returned
    # above cannot false-positive here).
    existing_user: Users | None = Users.query.filter(
        Users.username == new_username, Users.id != current_user.id
    ).first()
    if existing_user is not None:
        return build_field_error_response(
            message=USER_FAILURE.USERNAME_TAKEN,
            errors={"username": [USER_FAILURE.USERNAME_TAKEN]},
            error_code=ChangeUsernameErrorCodes.USERNAME_TAKEN,
            status_code=400,
        )

    # (5) Commit, guarding the UNIQUE-constraint race with an IntegrityError
    # rollback that surfaces the same taken-username field error.
    current_user.username = new_username
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return build_field_error_response(
            message=USER_FAILURE.USERNAME_TAKEN,
            errors={"username": [USER_FAILURE.USERNAME_TAKEN]},
            error_code=ChangeUsernameErrorCodes.USERNAME_TAKEN,
            status_code=400,
        )

    # (6) Only after a committed success, increment the counter (fail-open). The
    # EXPIRE is set only on the first INCR → fixed 24h window anchored at the
    # first change (Decision #4).
    if redis_client is not None:
        try:
            new_count = redis_client.incr(rate_limit_key)
            if new_count == 1:
                redis_client.expire(
                    rate_limit_key, USER_CONSTANTS.USERNAME_CHANGE_WINDOW_SECONDS
                )
        except Exception as redis_error:
            current_app.logger.exception(
                "username-change rate-limit increment failed (failing open): "
                f"{redis_error}"
            )

    # (7) Success.
    return APIResponse(
        status_code=200,
        data=ChangeUsernameResponseSchema(
            username=current_user.username,
            status=STD_JSON.SUCCESS,
            message=USERNAME_CHANGE_SUCCESS,
        ),
    ).to_response()


def apply_password_change(
    *, user_id: int, current_password: str, new_password: str
) -> FlaskResponse:
    """Change the authenticated user's password after current-password re-auth,
    then invalidate every OTHER session (Decision #2).

    Named ``apply_password_change`` to avoid a bare-name collision with the
    ``change_password`` route/view function on the ``users`` blueprint.

    Guard order: self-ownership (403) → OAuth-only (400, defense-in-depth) →
    brute-force lockout (429, shared per-user re-auth counter, DD-1) → re-auth
    (400 on wrong current password, recording the existing ``LOGIN_FAILURE``
    metric and a re-auth failure) → success: clear the failure counter, change
    password, bump ``sessions_invalidated_at`` and re-stamp the acting session
    so it survives, then commit.
    """
    # (1) Self-ownership: the URL user_id must be the acting user.
    if user_id != current_user.id:
        return build_message_error_response(
            message=USER_FAILURE.NOT_AUTHORIZED,
            error_code=ChangePasswordErrorCodes.INVALID_FORM_INPUT,
            status_code=403,
        )

    # (2) OAuth-only guard (defense-in-depth): the template hides the form for
    # password-less accounts. Predicate replicated locally per DD-19 (no import
    # from backend.splash.* for this check).
    if current_user.password is None:
        return build_message_error_response(
            message=USER_FAILURE.PASSWORD_CHANGE_OAUTH_ONLY,
            error_code=ChangePasswordErrorCodes.OAUTH_ONLY_NO_PASSWORD,
            status_code=400,
        )

    # (3) Brute-force lockout (DD-1): a per-user Redis counter shared with the
    # settings OAuth-link re-auth gate. Fail-open; checked before the password
    # compare so a locked-out session cannot keep guessing.
    if is_reauth_locked_out(user_id):
        return build_message_error_response(
            message=USER_FAILURE.TOO_MANY_PASSWORD_ATTEMPTS,
            error_code=ChangePasswordErrorCodes.TOO_MANY_ATTEMPTS,
            status_code=429,
        )

    # (4) Re-auth: verify the supplied current password (mirrors
    # initiate_settings_link). On failure, record a re-auth failure toward the
    # lockout + the existing LOGIN_FAILURE metric, then surface a dedicated field
    # error on `currentPassword`.
    if not current_user.is_password_correct(current_password):
        record_reauth_failure(user_id)
        record_event(
            EventName.LOGIN_FAILURE,
            dimensions={"reason": LOGIN_FAILURE_REASON_BAD_PASSWORD},
        )
        return build_field_error_response(
            message=USER_FAILURE.CURRENT_PASSWORD_INCORRECT,
            errors={"currentPassword": [USER_FAILURE.CURRENT_PASSWORD_INCORRECT]},
            error_code=ChangePasswordErrorCodes.INVALID_PASSWORD,
            status_code=400,
        )

    # (5) Success: clear the failure counter, then change the password,
    # invalidate every OTHER session by bumping sessions_invalidated_at, then
    # re-stamp the acting session so the current device survives its own
    # invalidation bump.
    clear_reauth_failures(user_id)
    current_user.change_password(new_password)
    current_user.sessions_invalidated_at = utc_now()
    restamp_current_session()
    db.session.commit()

    return APIResponse(
        status_code=200,
        data=ChangePasswordResponseSchema(
            status=STD_JSON.SUCCESS,
            message=PASSWORD_CHANGE_SUCCESS,
        ),
    ).to_response()


def apply_email_change(
    *, user_id: int, new_email: str, current_password: str
) -> FlaskResponse:
    """Stage a not-yet-confirmed new email after current-password re-auth, then
    mail a confirmation link to the NEW address. The live ``email`` is untouched
    until the user clicks that link (the anonymous confirm route swaps it).

    Named ``apply_email_change`` to avoid a bare-name collision with the
    ``change_email`` route/view function on the ``users`` blueprint.

    DD-19: builds the confirm URL by route NAME via ``url_for`` and sends via the
    neutral ``email_sender`` extension — no ``backend.splash.*`` service import.

    Guard order (so a rejected/no-op attempt never burns a rate-limit slot nor
    sends an email): self-ownership (403) → OAuth-only (400) → re-auth lockout
    (429) → re-auth (400) → no-op (200) → uniqueness (400) → rate-limit precheck
    fail-open (429) → stage + commit → send (rollback the staging on send
    failure) → INCR (EXPIRE only on the first) → success (200).
    """
    # (1) Self-ownership: the URL user_id must be the acting user.
    if user_id != current_user.id:
        return build_message_error_response(
            message=USER_FAILURE.NOT_AUTHORIZED,
            error_code=ChangeEmailErrorCodes.INVALID_FORM_INPUT,
            status_code=403,
        )

    # (2) OAuth-only guard (defense-in-depth): the template hides the form for
    # password-less accounts. Predicate replicated locally per DD-19.
    if current_user.password is None:
        return build_message_error_response(
            message=USER_FAILURE.EMAIL_CHANGE_OAUTH_ONLY,
            error_code=ChangeEmailErrorCodes.OAUTH_ONLY_NO_PASSWORD,
            status_code=400,
        )

    # (3) Brute-force lockout: the per-user Redis counter shared with the
    # change-password / settings OAuth-link re-auth gates. Fail-open; checked
    # before the password compare so a locked-out session cannot keep guessing.
    if is_reauth_locked_out(user_id):
        return build_message_error_response(
            message=USER_FAILURE.TOO_MANY_PASSWORD_ATTEMPTS,
            error_code=ChangeEmailErrorCodes.TOO_MANY_ATTEMPTS,
            status_code=429,
        )

    # (4) Re-auth: verify the supplied current password. On failure, record a
    # re-auth failure toward the lockout + the existing LOGIN_FAILURE metric,
    # then surface a dedicated field error on ``currentPassword``.
    if not current_user.is_password_correct(current_password):
        record_reauth_failure(user_id)
        record_event(
            EventName.LOGIN_FAILURE,
            dimensions={"reason": LOGIN_FAILURE_REASON_BAD_PASSWORD},
        )
        return build_field_error_response(
            message=USER_FAILURE.CURRENT_PASSWORD_INCORRECT,
            errors={"currentPassword": [USER_FAILURE.CURRENT_PASSWORD_INCORRECT]},
            error_code=ChangeEmailErrorCodes.INVALID_PASSWORD,
            status_code=400,
        )

    # (5) No-op short-circuit: resubmitting the current email never sends an
    # email nor touches Redis. ``pending_email`` echoes whatever is currently
    # staged (None if nothing is in flight); guard 5 does not clear or touch it.
    if new_email.lower() == current_user.email:
        return APIResponse(
            status_code=200,
            data=ChangeEmailResponseSchema(
                status=STD_JSON.NO_CHANGE,
                message=EMAIL_CHANGE_NO_CHANGE,
                pending_email=current_user.pending_email,
            ),
        ).to_response()

    # (6) Uniqueness (excluding the current user, so the no-op above cannot
    # false-positive here). The live email is what enforces uniqueness — a
    # different user's pending_email does not reserve the address.
    existing_user: Users | None = Users.query.filter(
        Users.email == new_email.lower(), Users.id != current_user.id
    ).first()
    if existing_user is not None:
        return build_field_error_response(
            message=USER_FAILURE.EMAIL_TAKEN,
            errors={"newEmail": [USER_FAILURE.EMAIL_TAKEN]},
            error_code=ChangeEmailErrorCodes.EMAIL_TAKEN,
            status_code=400,
        )

    rate_limit_key = f"email-change:{user_id}"
    redis_client = _build_rate_limit_redis()

    # (7) Rate-limit pre-check (fail-open): read the counter before staging so a
    # capped attempt is rejected without a DB write, an email send, or an INCR.
    if redis_client is not None:
        try:
            current_count = int(redis_client.get(rate_limit_key) or 0)
            if current_count >= USER_CONSTANTS.MAX_EMAIL_CHANGES_PER_DAY:
                return build_message_error_response(
                    message=USER_FAILURE.EMAIL_CHANGE_RATE_LIMITED,
                    error_code=ChangeEmailErrorCodes.RATE_LIMITED,
                    status_code=429,
                )
        except Exception as redis_error:
            current_app.logger.exception(
                "email-change rate-limit precheck failed (failing open): "
                f"{redis_error}"
            )

    # (8) Clear the re-auth failure counter, stage the pending email, and commit.
    # Staging happens strictly BEFORE minting the token below (DD-5), so
    # get_email_change_token()'s self.pending_email read is always the just-staged
    # value.
    clear_reauth_failures(user_id)
    current_user.stage_email_change(new_email)
    db.session.commit()

    # (9) Send the confirmation link to the NEW address, building the confirm URL
    # by route NAME only (DD-19). On a send failure, roll back the staging so
    # nothing is left half-staged.
    confirmation_url = url_for(
        ROUTES.SPLASH.CONFIRM_EMAIL_CHANGE,
        token=current_user.get_email_change_token(),
        _external=True,
    )
    email_sender = safe_get_email_sender(current_app)
    email_result = email_sender.send_email_change_confirmation(
        new_email.lower(), current_user.username, confirmation_url
    )
    if email_result.status_code >= 500:
        current_user.pending_email = None
        db.session.commit()
        return handle_mailjet_failure(
            email_result, error_code=ChangeEmailErrorCodes.EMAIL_SEND_FAILURE
        )

    # (10) Only after a committed staging + successful send, increment the
    # counter (fail-open). EXPIRE is set only on the first INCR → fixed 24h
    # window anchored at the first change.
    if redis_client is not None:
        try:
            new_count = redis_client.incr(rate_limit_key)
            if new_count == 1:
                redis_client.expire(
                    rate_limit_key, USER_CONSTANTS.EMAIL_CHANGE_WINDOW_SECONDS
                )
        except Exception as redis_error:
            current_app.logger.exception(
                "email-change rate-limit increment failed (failing open): "
                f"{redis_error}"
            )

    # (11) Success — echo the staged pending_email so the client patches the
    # account-info card in place (DD-6).
    return APIResponse(
        status_code=200,
        data=ChangeEmailResponseSchema(
            status=STD_JSON.SUCCESS,
            message=EMAIL_CHANGE_CONFIRMATION_SENT,
            pending_email=current_user.pending_email,
        ),
    ).to_response()
