from __future__ import annotations

from flask import Blueprint, request
from pydantic import BaseModel, ValidationError

from backend import csrf, limiter, metrics_writer
from backend.api_common.parse_request import api_route
from backend.api_common.request_errors import pydantic_errors_to_dict
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.extensions.metrics.admin_auth import metrics_admin_required
from backend.extensions.metrics.buckets import parse_window, previous_window
from backend.extensions.metrics.writer import record_event
from backend.metrics import query_service
from backend.metrics.constants import MetricsErrorCodes, MetricsFailureMessages
from backend.metrics.dimension_models import validate_dimensions
from backend.metrics.events import EventCategory, EventName
from backend.schemas.errors import (
    ErrorResponse,
    build_field_error_response,
)
from backend.schemas.metrics import (
    MetricsIngestResponseSchema,
    SummaryResponseSchema,
    TimeseriesResponseSchema,
    TopEventsResponseSchema,
)
from backend.schemas.requests.metrics import (
    MetricsIngestRequest,
    SummaryQuerySchema,
    TimeseriesQuerySchema,
    TopEventsQuerySchema,
)
from backend.utils.datetime_utils import utc_now
from backend.utils.strings.openapi_strs import OPEN_API

metrics = Blueprint("metrics", __name__)

# Rate limit values are conservative — Phase 4 batches with debounce, so
# 120/min/IP is generous; tighten once frontend telemetry lands if needed.
_METRICS_RATE_LIMIT = "120 per minute, 3000 per hour"


def _parse_query_args(schema_cls: type[BaseModel]) -> BaseModel | FlaskResponse:
    """Validate `request.args` against a Pydantic query schema.

    Returns the validated model on success or a 400 field-error response on
    `ValidationError`. Callers check `isinstance(result, BaseModel)` to
    short-circuit on the error branch.

    Why a module-private helper: every query route runs the same
    args-to-dict + model_validate + error-envelope dance; centralizing it
    keeps the route bodies focused on parse_window + service call + envelope.
    """
    try:
        return schema_cls.model_validate(request.args.to_dict(flat=True))
    except ValidationError as validation_error:
        return build_field_error_response(
            message=MetricsFailureMessages.INVALID_QUERY,
            errors=pydantic_errors_to_dict(validation_error),
            error_code=MetricsErrorCodes.INVALID_QUERY_PARAM,
            status_code=400,
        )


@metrics.route("/api/metrics", methods=["POST"])
@csrf.exempt
@api_route(
    request_schema=MetricsIngestRequest,
    response_schema=MetricsIngestResponseSchema,
    error_message=MetricsFailureMessages.UNABLE_TO_RECORD_METRICS,
    error_code=MetricsErrorCodes.INVALID_FORM_INPUT,
    ajax_required=False,
    tags=[OPEN_API.METRICS],
    description="Ingest a batch of UI-category metrics events from the browser",
    status_codes={200: MetricsIngestResponseSchema, 400: ErrorResponse},
)
@limiter.limit(_METRICS_RATE_LIMIT, methods=["POST"])
def ingest(metrics_ingest_request: MetricsIngestRequest) -> FlaskResponse:
    if metrics_ingest_request.batch_id is not None:
        newly_reserved = metrics_writer.reserve_batch(metrics_ingest_request.batch_id)
        if not newly_reserved:
            return APIResponse(
                message=MetricsFailureMessages.METRICS_RECORDED,
                data={"accepted": len(metrics_ingest_request.events)},
            ).to_response()

    for event_item in metrics_ingest_request.events:
        try:
            validate_dimensions(EventName(event_item.event_name), event_item.dimensions)
        except ValidationError as validation_error:
            return build_field_error_response(
                message=MetricsFailureMessages.UNABLE_TO_RECORD_METRICS,
                errors=pydantic_errors_to_dict(validation_error),
                error_code=MetricsErrorCodes.INVALID_FORM_INPUT,
                status_code=400,
            )

    for event_item in metrics_ingest_request.events:
        record_event(
            EventName(event_item.event_name),
            dimensions=event_item.dimensions,
        )

    return APIResponse(
        message=MetricsFailureMessages.METRICS_RECORDED,
        data={"accepted": len(metrics_ingest_request.events)},
    ).to_response()


@metrics.route("/api/metrics/query/top", methods=["GET"])
@metrics_admin_required
@api_route(
    response_schema=TopEventsResponseSchema,
    ajax_required=True,
    tags=[OPEN_API.METRICS],
    description="Return the top events by total count for an admin time window.",
    status_codes={
        200: TopEventsResponseSchema,
        400: ErrorResponse,
        401: ErrorResponse,
        404: ErrorResponse,
    },
)
def query_top() -> FlaskResponse:
    parsed = _parse_query_args(TopEventsQuerySchema)
    if not isinstance(parsed, BaseModel):
        return parsed

    try:
        window_start, window_end = parse_window(parsed.window, utc_now())
    except ValueError as validation_error:
        return build_field_error_response(
            message=MetricsFailureMessages.INVALID_WINDOW,
            errors={"window": [str(validation_error)]},
            error_code=MetricsErrorCodes.INVALID_QUERY_PARAM,
            status_code=400,
        )

    # `TopEventsQuerySchema.category` defaults to None; calling
    # `EventCategory(None)` directly raises ValueError, so guard explicitly.
    category_enum: EventCategory | None = (
        EventCategory(parsed.category) if parsed.category is not None else None
    )
    rows = query_service.top_events(
        window_start=window_start,
        window_end=window_end,
        category=category_enum,
        limit=parsed.limit,
    )
    response_schema = TopEventsResponseSchema(
        window=parsed.window,
        window_start=window_start,
        window_end=window_end,
        category=parsed.category,
        events=rows,
    )
    return APIResponse(data=response_schema, status_code=200).to_response()


@metrics.route("/api/metrics/query/timeseries", methods=["GET"])
@metrics_admin_required
@api_route(
    response_schema=TimeseriesResponseSchema,
    ajax_required=True,
    tags=[OPEN_API.METRICS],
    description="Return per-bucket counts for a single event over an admin time window.",
    status_codes={
        200: TimeseriesResponseSchema,
        400: ErrorResponse,
        401: ErrorResponse,
        404: ErrorResponse,
    },
)
def query_timeseries() -> FlaskResponse:
    parsed = _parse_query_args(TimeseriesQuerySchema)
    if not isinstance(parsed, BaseModel):
        return parsed

    try:
        window_start, window_end = parse_window(parsed.window, utc_now())
    except ValueError as validation_error:
        return build_field_error_response(
            message=MetricsFailureMessages.INVALID_WINDOW,
            errors={"window": [str(validation_error)]},
            error_code=MetricsErrorCodes.INVALID_QUERY_PARAM,
            status_code=400,
        )

    buckets = query_service.timeseries(
        event_name=EventName(parsed.event_name),
        window_start=window_start,
        window_end=window_end,
        resolution=parsed.resolution,
    )
    response_schema = TimeseriesResponseSchema(
        event_name=parsed.event_name,
        window=parsed.window,
        resolution=parsed.resolution,
        window_start=window_start,
        window_end=window_end,
        buckets=buckets,
    )
    return APIResponse(data=response_schema, status_code=200).to_response()


@metrics.route("/api/metrics/query/summary", methods=["GET"])
@metrics_admin_required
@api_route(
    response_schema=SummaryResponseSchema,
    ajax_required=True,
    tags=[OPEN_API.METRICS],
    description="Return per-category totals for the current and immediately-preceding window.",
    status_codes={
        200: SummaryResponseSchema,
        400: ErrorResponse,
        401: ErrorResponse,
        404: ErrorResponse,
    },
)
def query_summary() -> FlaskResponse:
    parsed = _parse_query_args(SummaryQuerySchema)
    if not isinstance(parsed, BaseModel):
        return parsed

    now = utc_now()
    try:
        window_start, window_end = parse_window(parsed.window, now)
        previous_window_start, previous_window_end = previous_window(parsed.window, now)
    except ValueError as validation_error:
        return build_field_error_response(
            message=MetricsFailureMessages.INVALID_WINDOW,
            errors={"window": [str(validation_error)]},
            error_code=MetricsErrorCodes.INVALID_QUERY_PARAM,
            status_code=400,
        )

    by_category = query_service.summary(
        window_start=window_start,
        window_end=window_end,
        previous_window_start=previous_window_start,
        previous_window_end=previous_window_end,
    )
    response_schema = SummaryResponseSchema(
        window=parsed.window,
        window_start=window_start,
        window_end=window_end,
        previous_window_start=previous_window_start,
        previous_window_end=previous_window_end,
        by_category=by_category,
    )
    return APIResponse(data=response_schema, status_code=200).to_response()
