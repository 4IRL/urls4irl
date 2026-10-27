"""Admin custom metric flow routes: list, create, update and delete saved funnels.

Defines routes on the existing ``admin`` blueprint. Registered by importing this
module inside ``create_app()`` before the blueprint is registered.
"""

from __future__ import annotations

from flask import request
from flask_login import current_user
from pydantic import BaseModel

from backend.admin.constants import AdminActionErrorCodes
from backend.admin.metric_flow_service import (
    create_metric_flow,
    delete_metric_flow,
    list_metric_flows,
    preview_metric_flow,
    update_metric_flow,
)
from backend.admin.routes import admin
from backend.api_common.auth_decorators import admin_required
from backend.api_common.parse_request import api_route, parse_query_args
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.extensions.metrics.buckets import resolve_query_window
from backend.metrics.constants import MetricsErrorCodes, MetricsFailureMessages
from backend.metrics.flow_catalog import build_flow_catalog
from backend.metrics.flow_limits import FLOW_LIMITS
from backend.metrics.flow_validation import LenientFlowDefinition
from backend.schemas.admin_actions import AdminActionResponseSchema
from backend.schemas.errors import ErrorResponse, build_field_error_response
from backend.schemas.metrics import (
    FlowCatalogResponseSchema,
    FlowResponseSchema,
    MetricFlowEntrySchema,
    MetricFlowListResponseSchema,
)
from backend.schemas.requests.metrics import FlowPreviewQuerySchema
from backend.utils.datetime_utils import utc_now
from backend.utils.strings.openapi_strs import OPEN_API


@admin.route("/admin/metrics/flows", methods=["GET"], endpoint="list_metric_flows")
@admin_required
@api_route(
    ajax_required=True,
    response_schema=MetricFlowListResponseSchema,
    tags=[OPEN_API.ADMIN],
    description=(
        "List every metric funnel for the flow builder: built-ins first, then "
        "saved custom flows with their validation problems."
    ),
    status_codes={
        200: MetricFlowListResponseSchema,
        401: ErrorResponse,
        404: ErrorResponse,
    },
)
def admin_list_metric_flows() -> FlaskResponse:
    """Return all built-in and custom funnels."""
    return list_metric_flows()


@admin.route("/admin/metrics/flows", methods=["POST"], endpoint="create_metric_flow")
@admin_required
@api_route(
    ajax_required=True,
    body_schema=LenientFlowDefinition,
    response_schema=MetricFlowEntrySchema,
    error_code=AdminActionErrorCodes.INVALID_FORM_INPUT,
    tags=[OPEN_API.ADMIN],
    description=(
        "Save a new custom funnel. The body is validated against the live "
        "event and endpoint registries; at most "
        f"{FLOW_LIMITS.MAX_CUSTOM} custom flows may exist."
    ),
    status_codes={
        201: MetricFlowEntrySchema,
        400: ErrorResponse,
        401: ErrorResponse,
        404: ErrorResponse,
    },
)
def admin_create_metric_flow() -> FlaskResponse:
    """Validate the posted draft and save it as a custom funnel."""
    return create_metric_flow(
        actor_id=current_user.id, payload=request.get_json(silent=True)
    )


@admin.route(
    "/admin/metrics/flows/catalog",
    methods=["GET"],
    endpoint="get_metric_flow_catalog",
)
@admin_required
@api_route(
    ajax_required=True,
    response_schema=FlowCatalogResponseSchema,
    tags=[OPEN_API.ADMIN],
    description=(
        "List every event, dimension filter rule and API endpoint the flow "
        "builder may offer, derived from the same sources save-time validation uses."
    ),
    status_codes={
        200: FlowCatalogResponseSchema,
        401: ErrorResponse,
        404: ErrorResponse,
    },
)
def admin_get_metric_flow_catalog() -> FlaskResponse:
    """Return the flow builder catalog."""
    return APIResponse(data=build_flow_catalog(), status_code=200).to_response()


@admin.route(
    "/admin/metrics/flows/preview",
    methods=["POST"],
    endpoint="preview_metric_flow",
)
@admin_required
@api_route(
    ajax_required=True,
    query_schema=FlowPreviewQuerySchema,
    body_schema=LenientFlowDefinition,
    response_schema=FlowResponseSchema,
    error_code=AdminActionErrorCodes.INVALID_FORM_INPUT,
    tags=[OPEN_API.ADMIN],
    description=(
        "Validate an unsaved funnel draft and count it for an admin time window "
        "with the same code as the dashboard. Writes nothing."
    ),
    status_codes={
        200: FlowResponseSchema,
        400: ErrorResponse,
        401: ErrorResponse,
        404: ErrorResponse,
    },
)
def admin_preview_metric_flow() -> FlaskResponse:
    """Preview a draft: query, then window, then body."""
    parsed = parse_query_args(
        FlowPreviewQuerySchema,
        message=MetricsFailureMessages.INVALID_QUERY,
        error_code=MetricsErrorCodes.INVALID_QUERY_PARAM,
    )
    if not isinstance(parsed, BaseModel):
        return parsed

    try:
        window_start, window_end = resolve_query_window(
            window=parsed.window,
            start=parsed.start,
            end=parsed.end,
            now=utc_now(),
        )
    except ValueError as validation_error:
        return build_field_error_response(
            message=MetricsFailureMessages.INVALID_WINDOW,
            errors={"window": [str(validation_error)]},
            error_code=MetricsErrorCodes.INVALID_QUERY_PARAM,
            status_code=400,
        )

    return preview_metric_flow(
        payload=request.get_json(silent=True),
        window_start=window_start,
        window_end=window_end,
    )


@admin.route(
    "/admin/metrics/flows/<flow_id>", methods=["PUT"], endpoint="update_metric_flow"
)
@admin_required
@api_route(
    ajax_required=True,
    body_schema=LenientFlowDefinition,
    response_schema=MetricFlowEntrySchema,
    error_code=AdminActionErrorCodes.INVALID_FORM_INPUT,
    tags=[OPEN_API.ADMIN],
    description=(
        "Replace a saved custom funnel by its custom_<n> id (last write wins). "
        "The body is validated against the live event and endpoint registries."
    ),
    status_codes={
        200: MetricFlowEntrySchema,
        400: ErrorResponse,
        401: ErrorResponse,
        404: ErrorResponse,
    },
)
def admin_update_metric_flow(flow_id: str) -> FlaskResponse:
    """Validate the posted draft and overwrite the addressed custom funnel."""
    return update_metric_flow(
        actor_id=current_user.id,
        flow_id=flow_id,
        payload=request.get_json(silent=True),
    )


@admin.route(
    "/admin/metrics/flows/<flow_id>", methods=["DELETE"], endpoint="delete_metric_flow"
)
@admin_required
@api_route(
    ajax_required=True,
    response_schema=AdminActionResponseSchema,
    error_code=AdminActionErrorCodes.INVALID_FORM_INPUT,
    tags=[OPEN_API.ADMIN],
    description="Permanently delete a saved custom funnel by its custom_<n> id.",
    status_codes={
        200: AdminActionResponseSchema,
        400: ErrorResponse,
        401: ErrorResponse,
        404: ErrorResponse,
    },
)
def admin_delete_metric_flow(flow_id: str) -> FlaskResponse:
    """Hard-delete the addressed custom funnel."""
    return delete_metric_flow(actor_id=current_user.id, flow_id=flow_id)
