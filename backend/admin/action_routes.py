"""Admin action routes: ops and content-moderation audited POST endpoints.

Defines routes on the existing ``admin`` blueprint imported from
``backend.admin.routes``. Registered by importing this module inside
``create_app()`` after ``admin`` is imported — the import side-effect
registers the route decorators on the already-created blueprint object.
"""

from __future__ import annotations

from flask_login import current_user

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
from backend.schemas.requests.admin_actions import (
    AdminActionRequest,
    AdminReasonRequiredRequest,
)
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
    request_schema=AdminActionRequest,
    response_schema=AdminActionResponseSchema,
    error_message=ADMIN_ACTION_STRINGS.GENERIC_ERROR,
    error_code=AdminActionErrorCodes.INVALID_FORM_INPUT,
    tags=[OPEN_API.ADMIN],
    description="Trigger an immediate Redis-to-Postgres metrics counter flush",
    status_codes=_OPS_STATUS_CODES,
)
def admin_ops_metrics_flush(
    admin_action_request: AdminActionRequest,
) -> FlaskResponse:
    """Trigger an immediate metrics flush and return the row count."""
    return trigger_metrics_flush(
        actor_id=current_user.id,
        reason=admin_action_request.reason,
    )


@admin.route("/admin/ops/gauge-sample", methods=["POST"])
@admin_required
@api_route(
    request_schema=AdminActionRequest,
    response_schema=AdminActionResponseSchema,
    error_message=ADMIN_ACTION_STRINGS.GENERIC_ERROR,
    error_code=AdminActionErrorCodes.INVALID_FORM_INPUT,
    tags=[OPEN_API.ADMIN],
    description="Trigger an immediate gauge sample run for all registered gauges",
    status_codes=_OPS_STATUS_CODES,
)
def admin_ops_gauge_sample(
    admin_action_request: AdminActionRequest,
) -> FlaskResponse:
    """Trigger an immediate gauge sample and return the gauge count."""
    return trigger_gauge_sample(
        actor_id=current_user.id,
        reason=admin_action_request.reason,
    )


@admin.route("/admin/ops/audit-purge", methods=["POST"])
@admin_required
@api_route(
    request_schema=AdminActionRequest,
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
    admin_action_request: AdminActionRequest,
) -> FlaskResponse:
    """Run the 90-day audit-log retention purge and return the deleted row count."""
    return trigger_audit_purge(
        actor_id=current_user.id,
        reason=admin_action_request.reason,
    )


@admin.route("/admin/ops/verify-tables", methods=["POST"])
@admin_required
@api_route(
    request_schema=AdminActionRequest,
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
    admin_action_request: AdminActionRequest,
) -> FlaskResponse:
    """Check for missing tables and return the missing-table count."""
    return trigger_verify_tables(
        actor_id=current_user.id,
        reason=admin_action_request.reason,
    )


@admin.route("/admin/ops/backup-trigger", methods=["POST"])
@admin_required
@api_route(
    request_schema=AdminActionRequest,
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
    admin_action_request: AdminActionRequest,
) -> FlaskResponse:
    """Request an on-demand backup pipeline run via the cross-container flag."""
    return trigger_backup(
        actor_id=current_user.id,
        reason=admin_action_request.reason,
    )


@admin.route("/admin/ops/short-urls-sync", methods=["POST"])
@admin_required
@api_route(
    request_schema=AdminActionRequest,
    response_schema=AdminActionResponseSchema,
    error_message=ADMIN_ACTION_STRINGS.GENERIC_ERROR,
    error_code=AdminActionErrorCodes.INVALID_FORM_INPUT,
    tags=[OPEN_API.ADMIN],
    description="Regenerate the short-URL domain Redis set from the canonical GitHub list",
    status_codes=_OPS_STATUS_CODES,
)
def admin_ops_short_urls_sync(
    admin_action_request: AdminActionRequest,
) -> FlaskResponse:
    """Sync short-URL domains to Redis and return the count of newly added domains."""
    return trigger_short_urls_sync(
        actor_id=current_user.id,
        reason=admin_action_request.reason,
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
