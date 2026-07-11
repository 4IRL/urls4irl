"""Admin ops-action routes: five audited, admin-gated one-button POST endpoints.

Defines routes on the existing ``admin`` blueprint imported from
``backend.admin.routes``. Registered by importing this module inside
``create_app()`` after ``admin`` is imported — the import side-effect
registers the route decorators on the already-created blueprint object.
"""

from __future__ import annotations

from flask_login import current_user

from backend.admin.constants import AdminActionErrorCodes
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
from backend.schemas.admin_actions import AdminOpsActionResponseSchema
from backend.schemas.errors import ErrorResponse
from backend.schemas.requests.admin_actions import AdminActionRequest
from backend.utils.strings.admin_portal_strs import ADMIN_ACTION_STRINGS
from backend.utils.strings.openapi_strs import OPEN_API

_OPS_STATUS_CODES = {
    200: AdminOpsActionResponseSchema,
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
    response_schema=AdminOpsActionResponseSchema,
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
    response_schema=AdminOpsActionResponseSchema,
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
    response_schema=AdminOpsActionResponseSchema,
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
    response_schema=AdminOpsActionResponseSchema,
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
    response_schema=AdminOpsActionResponseSchema,
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
    response_schema=AdminOpsActionResponseSchema,
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
