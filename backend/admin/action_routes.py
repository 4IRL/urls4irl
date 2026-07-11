"""Admin action routes: ops and content-moderation audited POST endpoints.

Defines routes on the existing ``admin`` blueprint imported from
``backend.admin.routes``. Registered by importing this module inside
``create_app()`` after ``admin`` is imported — the import side-effect
registers the route decorators on the already-created blueprint object.
"""

from __future__ import annotations

from flask_login import current_user

from backend.admin.account_data_service import (
    erase_user,
    mark_email_verified,
    resend_verification_email,
    unlink_oauth_identity,
)
from backend.admin.account_service import (
    force_password_reset,
    kill_user_sessions,
    suspend_user,
    unsuspend_user,
)
from backend.admin.constants import AdminActionErrorCodes
from backend.admin.moderation_service import (
    delete_url_in_utub_admin,
    delete_utub_admin,
    lock_utub,
    purge_url_globally,
    remove_member_admin,
    unlock_utub,
)
from backend.admin.ops_service import (
    trigger_audit_purge,
    trigger_backup,
    trigger_gauge_sample,
    trigger_metrics_flush,
    trigger_short_urls_sync,
    trigger_verify_tables,
)
from backend.admin.routes import admin
from backend.api_common.auth_decorators import admin_required
from backend.api_common.parse_request import api_route
from backend.api_common.responses import FlaskResponse
from backend.schemas.admin_actions import AdminActionResponseSchema
from backend.schemas.errors import ErrorResponse
from backend.schemas.requests.admin_actions import AdminReasonRequiredRequest
from backend.utils.strings.admin_portal_strs import ADMIN_ACTION_STRINGS
from backend.utils.strings.openapi_strs import OPEN_API

_OPS_STATUS_CODES = {
    200: AdminActionResponseSchema,
    400: ErrorResponse,
    401: ErrorResponse,
    404: ErrorResponse,
    500: ErrorResponse,
    503: ErrorResponse,
}


@admin.route("/admin/ops/metrics-flush", methods=["POST"])
@admin_required
@api_route(
    request_schema=AdminReasonRequiredRequest,
    response_schema=AdminActionResponseSchema,
    error_message=ADMIN_ACTION_STRINGS.GENERIC_ERROR,
    error_code=AdminActionErrorCodes.INVALID_FORM_INPUT,
    tags=[OPEN_API.ADMIN],
    description="Trigger an immediate Redis-to-Postgres metrics counter flush",
    status_codes=_OPS_STATUS_CODES,
)
def admin_ops_metrics_flush(
    admin_reason_required_request: AdminReasonRequiredRequest,
) -> FlaskResponse:
    """Trigger an immediate metrics flush and return the row count."""
    return trigger_metrics_flush(
        actor_id=current_user.id,
        reason=admin_reason_required_request.reason,
    )


@admin.route("/admin/ops/gauge-sample", methods=["POST"])
@admin_required
@api_route(
    request_schema=AdminReasonRequiredRequest,
    response_schema=AdminActionResponseSchema,
    error_message=ADMIN_ACTION_STRINGS.GENERIC_ERROR,
    error_code=AdminActionErrorCodes.INVALID_FORM_INPUT,
    tags=[OPEN_API.ADMIN],
    description="Trigger an immediate gauge sample run for all registered gauges",
    status_codes=_OPS_STATUS_CODES,
)
def admin_ops_gauge_sample(
    admin_reason_required_request: AdminReasonRequiredRequest,
) -> FlaskResponse:
    """Trigger an immediate gauge sample and return the gauge count."""
    return trigger_gauge_sample(
        actor_id=current_user.id,
        reason=admin_reason_required_request.reason,
    )


@admin.route("/admin/ops/audit-purge", methods=["POST"])
@admin_required
@api_route(
    request_schema=AdminReasonRequiredRequest,
    response_schema=AdminActionResponseSchema,
    error_message=ADMIN_ACTION_STRINGS.GENERIC_ERROR,
    error_code=AdminActionErrorCodes.INVALID_FORM_INPUT,
    tags=[OPEN_API.ADMIN],
    description=(
        "Run the audit-log retention purge (window-only, never purge-all). "
        "The purge trigger itself is always recorded in the audit log first."
    ),
    status_codes=_OPS_STATUS_CODES,
)
def admin_ops_audit_purge(
    admin_reason_required_request: AdminReasonRequiredRequest,
) -> FlaskResponse:
    """Run the 90-day audit-log retention purge and return the deleted row count."""
    return trigger_audit_purge(
        actor_id=current_user.id,
        reason=admin_reason_required_request.reason,
    )


@admin.route("/admin/ops/verify-tables", methods=["POST"])
@admin_required
@api_route(
    request_schema=AdminReasonRequiredRequest,
    response_schema=AdminActionResponseSchema,
    error_message=ADMIN_ACTION_STRINGS.GENERIC_ERROR,
    error_code=AdminActionErrorCodes.INVALID_FORM_INPUT,
    tags=[OPEN_API.ADMIN],
    description=(
        "Check for missing database tables (read-only). "
        "Never triggers the DROP SCHEMA auto-repair path."
    ),
    status_codes=_OPS_STATUS_CODES,
)
def admin_ops_verify_tables(
    admin_reason_required_request: AdminReasonRequiredRequest,
) -> FlaskResponse:
    """Check for missing tables and return the missing-table count."""
    return trigger_verify_tables(
        actor_id=current_user.id,
        reason=admin_reason_required_request.reason,
    )


@admin.route("/admin/ops/backup-trigger", methods=["POST"])
@admin_required
@api_route(
    request_schema=AdminReasonRequiredRequest,
    response_schema=AdminActionResponseSchema,
    error_message=ADMIN_ACTION_STRINGS.GENERIC_ERROR,
    error_code=AdminActionErrorCodes.INVALID_FORM_INPUT,
    tags=[OPEN_API.ADMIN],
    description=(
        "Request an on-demand backup run. Sets a short-TTL Redis flag the "
        "workflow container's per-minute poller consumes to start the "
        "backup pipeline. Idempotent while a request is pending."
    ),
    status_codes=_OPS_STATUS_CODES,
)
def admin_ops_backup_trigger(
    admin_reason_required_request: AdminReasonRequiredRequest,
) -> FlaskResponse:
    """Request an on-demand backup pipeline run via the cross-container flag."""
    return trigger_backup(
        actor_id=current_user.id,
        reason=admin_reason_required_request.reason,
    )


@admin.route("/admin/ops/short-urls-sync", methods=["POST"])
@admin_required
@api_route(
    request_schema=AdminReasonRequiredRequest,
    response_schema=AdminActionResponseSchema,
    error_message=ADMIN_ACTION_STRINGS.GENERIC_ERROR,
    error_code=AdminActionErrorCodes.INVALID_FORM_INPUT,
    tags=[OPEN_API.ADMIN],
    description="Regenerate the short-URL domain Redis set from the canonical GitHub list",
    status_codes=_OPS_STATUS_CODES,
)
def admin_ops_short_urls_sync(
    admin_reason_required_request: AdminReasonRequiredRequest,
) -> FlaskResponse:
    """Sync short-URL domains to Redis and return the count of newly added domains."""
    return trigger_short_urls_sync(
        actor_id=current_user.id,
        reason=admin_reason_required_request.reason,
    )


_MOD_STATUS_CODES = {
    200: AdminActionResponseSchema,
    400: ErrorResponse,
    401: ErrorResponse,
    404: ErrorResponse,
}


@admin.route("/admin/utubs/<int:utub_id>/lock", methods=["POST"])
@admin_required
@api_route(
    request_schema=AdminReasonRequiredRequest,
    response_schema=AdminActionResponseSchema,
    error_message=ADMIN_ACTION_STRINGS.GENERIC_ERROR,
    error_code=AdminActionErrorCodes.INVALID_FORM_INPUT,
    tags=[OPEN_API.ADMIN],
    description=(
        "Lock a UTub, preventing new content (URLs, tags, members) from being added. "
        "Idempotent: already-locked UTubs return a no-op 200 with no audit row."
    ),
    status_codes=_MOD_STATUS_CODES,
)
def admin_utub_lock(
    utub_id: int,
    admin_reason_required_request: AdminReasonRequiredRequest,
) -> FlaskResponse:
    """Lock a UTub so that no new content can be added."""
    return lock_utub(
        actor_id=current_user.id,
        utub_id=utub_id,
        reason=admin_reason_required_request.reason,
    )


@admin.route("/admin/utubs/<int:utub_id>/unlock", methods=["POST"])
@admin_required
@api_route(
    request_schema=AdminReasonRequiredRequest,
    response_schema=AdminActionResponseSchema,
    error_message=ADMIN_ACTION_STRINGS.GENERIC_ERROR,
    error_code=AdminActionErrorCodes.INVALID_FORM_INPUT,
    tags=[OPEN_API.ADMIN],
    description=(
        "Unlock a previously locked UTub, re-enabling content writes. "
        "Idempotent: already-unlocked UTubs return a no-op 200 with no audit row."
    ),
    status_codes=_MOD_STATUS_CODES,
)
def admin_utub_unlock(
    utub_id: int,
    admin_reason_required_request: AdminReasonRequiredRequest,
) -> FlaskResponse:
    """Unlock a UTub so that new content can be added again."""
    return unlock_utub(
        actor_id=current_user.id,
        utub_id=utub_id,
        reason=admin_reason_required_request.reason,
    )


@admin.route("/admin/utubs/<int:utub_id>/delete", methods=["POST"])
@admin_required
@api_route(
    request_schema=AdminReasonRequiredRequest,
    response_schema=AdminActionResponseSchema,
    error_message=ADMIN_ACTION_STRINGS.GENERIC_ERROR,
    error_code=AdminActionErrorCodes.INVALID_FORM_INPUT,
    tags=[OPEN_API.ADMIN],
    description="Permanently delete a UTub and all its members, URLs, and tags via ORM cascade.",
    status_codes=_MOD_STATUS_CODES,
)
def admin_utub_delete(
    utub_id: int,
    admin_reason_required_request: AdminReasonRequiredRequest,
) -> FlaskResponse:
    """Permanently delete a UTub and all its associated content."""
    return delete_utub_admin(
        actor_id=current_user.id,
        utub_id=utub_id,
        reason=admin_reason_required_request.reason,
    )


@admin.route(
    "/admin/utubs/<int:utub_id>/members/<int:target_user_id>/remove", methods=["POST"]
)
@admin_required
@api_route(
    request_schema=AdminReasonRequiredRequest,
    response_schema=AdminActionResponseSchema,
    error_message=ADMIN_ACTION_STRINGS.GENERIC_ERROR,
    error_code=AdminActionErrorCodes.INVALID_FORM_INPUT,
    tags=[OPEN_API.ADMIN],
    description=(
        "Remove a member from a UTub. If the target is the creator and other members "
        "exist, ownership is transferred to the lowest-user-id CO_CREATOR (or MEMBER). "
        "If the target is the sole member and creator, the UTub is deleted."
    ),
    status_codes=_MOD_STATUS_CODES,
)
def admin_member_remove(
    utub_id: int,
    target_user_id: int,
    admin_reason_required_request: AdminReasonRequiredRequest,
) -> FlaskResponse:
    """Remove a member from a UTub with creator-transfer logic."""
    return remove_member_admin(
        actor_id=current_user.id,
        utub_id=utub_id,
        target_user_id=target_user_id,
        reason=admin_reason_required_request.reason,
    )


@admin.route(
    "/admin/utubs/<int:utub_id>/urls/<int:utub_url_id>/delete", methods=["POST"]
)
@admin_required
@api_route(
    request_schema=AdminReasonRequiredRequest,
    response_schema=AdminActionResponseSchema,
    error_message=ADMIN_ACTION_STRINGS.GENERIC_ERROR,
    error_code=AdminActionErrorCodes.INVALID_FORM_INPUT,
    tags=[OPEN_API.ADMIN],
    description=(
        "Delete a specific URL association from a UTub. "
        "Removes the Utub_Url_Tags rows for that association atomically. "
        "The Urls table row is preserved."
    ),
    status_codes=_MOD_STATUS_CODES,
)
def admin_url_delete(
    utub_id: int,
    utub_url_id: int,
    admin_reason_required_request: AdminReasonRequiredRequest,
) -> FlaskResponse:
    """Delete a URL from a specific UTub."""
    return delete_url_in_utub_admin(
        actor_id=current_user.id,
        utub_id=utub_id,
        utub_url_id=utub_url_id,
        reason=admin_reason_required_request.reason,
    )


@admin.route("/admin/urls/<int:url_id>/purge", methods=["POST"])
@admin_required
@api_route(
    request_schema=AdminReasonRequiredRequest,
    response_schema=AdminActionResponseSchema,
    error_message=ADMIN_ACTION_STRINGS.GENERIC_ERROR,
    error_code=AdminActionErrorCodes.INVALID_FORM_INPUT,
    tags=[OPEN_API.ADMIN],
    description=(
        "Remove a URL from every UTub it appears in. "
        "The Urls row is preserved; only Utub_Urls associations and their tags are removed. "
        "Returns count=number of UTubs affected (may be 0)."
    ),
    status_codes=_MOD_STATUS_CODES,
)
def admin_url_purge(
    url_id: int,
    admin_reason_required_request: AdminReasonRequiredRequest,
) -> FlaskResponse:
    """Purge a URL globally — remove it from every UTub that contains it."""
    return purge_url_globally(
        actor_id=current_user.id,
        url_id=url_id,
        reason=admin_reason_required_request.reason,
    )


_ACCOUNT_STATUS_CODES = {
    200: AdminActionResponseSchema,
    400: ErrorResponse,
    401: ErrorResponse,
    403: ErrorResponse,
    404: ErrorResponse,
}

_ACCOUNT_FORCE_RESET_STATUS_CODES = {
    200: AdminActionResponseSchema,
    400: ErrorResponse,
    401: ErrorResponse,
    403: ErrorResponse,
    404: ErrorResponse,
    502: ErrorResponse,
}


@admin.route("/admin/users/<int:target_user_id>/suspend", methods=["POST"])
@admin_required
@api_route(
    request_schema=AdminReasonRequiredRequest,
    response_schema=AdminActionResponseSchema,
    error_message=ADMIN_ACTION_STRINGS.GENERIC_ERROR,
    error_code=AdminActionErrorCodes.INVALID_FORM_INPUT,
    tags=[OPEN_API.ADMIN],
    description=(
        "Suspend a user account, invalidating all web sessions and revoking API tokens. "
        "Idempotent: already-suspended users return a no-op 200 with no audit row. "
        "Guards: self-action 403; last-admin 403 when no other unsuspended admin exists."
    ),
    status_codes=_ACCOUNT_STATUS_CODES,
)
def admin_user_suspend(
    target_user_id: int,
    admin_reason_required_request: AdminReasonRequiredRequest,
) -> FlaskResponse:
    """Suspend a user account and kill all their sessions."""
    return suspend_user(
        actor_id=current_user.id,
        target_user_id=target_user_id,
        reason=admin_reason_required_request.reason,
    )


@admin.route("/admin/users/<int:target_user_id>/unsuspend", methods=["POST"])
@admin_required
@api_route(
    request_schema=AdminReasonRequiredRequest,
    response_schema=AdminActionResponseSchema,
    error_message=ADMIN_ACTION_STRINGS.GENERIC_ERROR,
    error_code=AdminActionErrorCodes.INVALID_FORM_INPUT,
    tags=[OPEN_API.ADMIN],
    description=(
        "Lift a user's suspension, restoring their ability to log in. "
        "Idempotent: users who are not suspended return a no-op 200 with no audit row. "
        "Guard: self-action 403."
    ),
    status_codes=_ACCOUNT_STATUS_CODES,
)
def admin_user_unsuspend(
    target_user_id: int,
    admin_reason_required_request: AdminReasonRequiredRequest,
) -> FlaskResponse:
    """Unsuspend a user account so they can log in again."""
    return unsuspend_user(
        actor_id=current_user.id,
        target_user_id=target_user_id,
        reason=admin_reason_required_request.reason,
    )


@admin.route("/admin/users/<int:target_user_id>/force-reset", methods=["POST"])
@admin_required
@api_route(
    request_schema=AdminReasonRequiredRequest,
    response_schema=AdminActionResponseSchema,
    error_message=ADMIN_ACTION_STRINGS.GENERIC_ERROR,
    error_code=AdminActionErrorCodes.INVALID_FORM_INPUT,
    tags=[OPEN_API.ADMIN],
    description=(
        "Force a password-reset email for a user and invalidate all their sessions. "
        "Bypasses rate limits entirely. "
        "Returns 400 for OAuth-only accounts (no local password). "
        "Returns 502 if the email send fails (no DB changes are committed). "
        "Guard: self-action 403."
    ),
    status_codes=_ACCOUNT_FORCE_RESET_STATUS_CODES,
)
def admin_user_force_reset(
    target_user_id: int,
    admin_reason_required_request: AdminReasonRequiredRequest,
) -> FlaskResponse:
    """Force-send a password-reset email and kill all user sessions."""
    return force_password_reset(
        actor_id=current_user.id,
        target_user_id=target_user_id,
        reason=admin_reason_required_request.reason,
    )


@admin.route("/admin/users/<int:target_user_id>/kill-sessions", methods=["POST"])
@admin_required
@api_route(
    request_schema=AdminReasonRequiredRequest,
    response_schema=AdminActionResponseSchema,
    error_message=ADMIN_ACTION_STRINGS.GENERIC_ERROR,
    error_code=AdminActionErrorCodes.INVALID_FORM_INPUT,
    tags=[OPEN_API.ADMIN],
    description=(
        "Invalidate all web sessions and revoke all API refresh tokens for a user. "
        "Not idempotent — always acts and always records an audit row. "
        "Guard: self-action 403."
    ),
    status_codes=_ACCOUNT_STATUS_CODES,
)
def admin_user_kill_sessions(
    target_user_id: int,
    admin_reason_required_request: AdminReasonRequiredRequest,
) -> FlaskResponse:
    """Kill all sessions and revoke all API tokens for a user."""
    return kill_user_sessions(
        actor_id=current_user.id,
        target_user_id=target_user_id,
        reason=admin_reason_required_request.reason,
    )


@admin.route("/admin/users/<int:target_user_id>/erase", methods=["POST"])
@admin_required
@api_route(
    request_schema=AdminReasonRequiredRequest,
    response_schema=AdminActionResponseSchema,
    error_message=ADMIN_ACTION_STRINGS.GENERIC_ERROR,
    error_code=AdminActionErrorCodes.INVALID_FORM_INPUT,
    tags=[OPEN_API.ADMIN],
    description=(
        "Erase a user account (anonymize-in-place): scrub username/email/"
        "password to a tombstone identity, delete OAuth/email-validation/"
        "forgot-password/contact-form child rows, kill all sessions, and "
        "resolve UTub memberships (solo UTubs deleted, created UTubs "
        "transferred, other memberships removed). Idempotent for an "
        "already-erased user. Guards: self-action 403, last-admin 403."
    ),
    status_codes=_ACCOUNT_STATUS_CODES,
)
def admin_user_erase(
    target_user_id: int,
    admin_reason_required_request: AdminReasonRequiredRequest,
) -> FlaskResponse:
    """Erase a user account: anonymize-in-place with membership resolution."""
    return erase_user(
        actor_id=current_user.id,
        target_user_id=target_user_id,
        reason=admin_reason_required_request.reason,
    )


@admin.route(
    "/admin/users/<int:target_user_id>/oauth/<int:identity_id>/unlink",
    methods=["POST"],
)
@admin_required
@api_route(
    request_schema=AdminReasonRequiredRequest,
    response_schema=AdminActionResponseSchema,
    error_message=ADMIN_ACTION_STRINGS.GENERIC_ERROR,
    error_code=AdminActionErrorCodes.INVALID_FORM_INPUT,
    tags=[OPEN_API.ADMIN],
    description=(
        "Unlink a specific OAuth identity from a user account. "
        "Returns 403 when the identity is the account's only login method "
        "(no local password and it is the last OAuth identity). "
        "Returns 404 when the identity does not belong to the target user. "
        "Guard: self-action 403."
    ),
    status_codes=_ACCOUNT_STATUS_CODES,
)
def admin_user_oauth_unlink(
    target_user_id: int,
    identity_id: int,
    admin_reason_required_request: AdminReasonRequiredRequest,
) -> FlaskResponse:
    """Unlink an OAuth identity from a user account."""
    return unlink_oauth_identity(
        actor_id=current_user.id,
        target_user_id=target_user_id,
        identity_id=identity_id,
        reason=admin_reason_required_request.reason,
    )


@admin.route("/admin/users/<int:target_user_id>/email/verify", methods=["POST"])
@admin_required
@api_route(
    request_schema=AdminReasonRequiredRequest,
    response_schema=AdminActionResponseSchema,
    error_message=ADMIN_ACTION_STRINGS.GENERIC_ERROR,
    error_code=AdminActionErrorCodes.INVALID_FORM_INPUT,
    tags=[OPEN_API.ADMIN],
    description=(
        "Mark a user's email address as verified and delete any pending "
        "Email_Validations row. Idempotent: already-verified users return a "
        "no-op 200 with no audit row. Guard: self-action 403."
    ),
    status_codes=_ACCOUNT_STATUS_CODES,
)
def admin_user_email_verify(
    target_user_id: int,
    admin_reason_required_request: AdminReasonRequiredRequest,
) -> FlaskResponse:
    """Mark a user's email as verified and remove the pending validation row."""
    return mark_email_verified(
        actor_id=current_user.id,
        target_user_id=target_user_id,
        reason=admin_reason_required_request.reason,
    )


@admin.route("/admin/users/<int:target_user_id>/email/resend", methods=["POST"])
@admin_required
@api_route(
    request_schema=AdminReasonRequiredRequest,
    response_schema=AdminActionResponseSchema,
    error_message=ADMIN_ACTION_STRINGS.GENERIC_ERROR,
    error_code=AdminActionErrorCodes.INVALID_FORM_INPUT,
    tags=[OPEN_API.ADMIN],
    description=(
        "Resend the email-verification link for an unverified user. Bypasses "
        "all rate limits: creates or refreshes the Email_Validations row "
        "(resets attempt counters, generates a fresh token). Returns 200 no-op "
        "when the user is already verified. Returns 502 if the email send fails "
        "(all DB changes rolled back). Guard: self-action 403."
    ),
    status_codes=_ACCOUNT_FORCE_RESET_STATUS_CODES,
)
def admin_user_email_resend(
    target_user_id: int,
    admin_reason_required_request: AdminReasonRequiredRequest,
) -> FlaskResponse:
    """Resend the email-verification link and reset rate-limit counters."""
    return resend_verification_email(
        actor_id=current_user.id,
        target_user_id=target_user_id,
        reason=admin_reason_required_request.reason,
    )
