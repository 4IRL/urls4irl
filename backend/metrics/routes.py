from __future__ import annotations

from typing import Literal

from flask import Blueprint, request
from pydantic import BaseModel, ValidationError

from backend import csrf, db, limiter, metrics_writer
from backend.api_common.auth_decorators import admin_required
from backend.api_common.parse_request import api_route, parse_query_args
from backend.api_common.request_errors import pydantic_errors_to_dict
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.extensions.metrics.buckets import previous_window, resolve_query_window
from backend.extensions.metrics.ua_classifier import classify_user_agent
from backend.extensions.metrics.writer import record_event
from backend.metrics import query_service
from backend.metrics.constants import MetricsErrorCodes, MetricsFailureMessages
from backend.metrics.dimension_models import validate_dimensions
from backend.metrics.events import DEVICE_TYPE_DIM_KEY, EventCategory, EventName
from backend.metrics.flow_counting import FlowCountError, count_flow
from backend.metrics.flow_invalid import first_invalid_detail, flow_invalid_response
from backend.metrics.flow_validation import validate_flow_payload
from backend.metrics.flows import (
    ALL_FLOW_IDS,
    FLOWS,
    FlowDefinition,
    FlowId,
    parse_custom_flow_id,
)
from backend.metrics.latency import LatencyMetricName
from backend.metrics.resources import Resource
from backend.models.metric_flows import Metric_Flows
from backend.schemas.errors import (
    ErrorResponse,
    build_field_error_response,
    build_message_error_response,
)
from backend.schemas.metrics import (
    FlowInvalidDetailSchema,
    FlowInvalidResponseSchema,
    FlowResponseSchema,
    GaugesTimeseriesResponseSchema,
    GroupedTimeseriesResponseSchema,
    LatencyPercentilesResponseSchema,
    LatencyTimeseriesResponseSchema,
    MetricsIngestResponseSchema,
    SummaryResponseSchema,
    TimeseriesResponseSchema,
    TopEventsResponseSchema,
)
from backend.schemas.requests.metrics import (
    FlowQuerySchema,
    GaugesTimeseriesQuerySchema,
    GroupedTimeseriesQuerySchema,
    LatencyQuerySchema,
    LatencyTimeseriesQuerySchema,
    MetricsIngestRequest,
    SummaryQuerySchema,
    TimeseriesQuerySchema,
    TopEventsQuerySchema,
    TransportQuerySchema,
)
from backend.utils.datetime_utils import utc_now
from backend.utils.strings.openapi_strs import OPEN_API

metrics = Blueprint("metrics", __name__)

# Rate limit values are conservative — Phase 4 batches with debounce, so
# 120/min/IP is generous; tighten once frontend telemetry lands if needed.
_METRICS_RATE_LIMIT = "120 per minute, 3000 per hour"


def bucket_batch_size(event_count: int) -> Literal["1", "2-5", "6-25", "26-100"]:
    """Maps a batch event_count to its closed-set bucket label.

    Examples:
        >>> bucket_batch_size(1)
        '1'
        >>> bucket_batch_size(5)
        '2-5'
        >>> bucket_batch_size(100)
        '26-100'
    """
    if event_count <= 1:
        return "1"
    if event_count <= 5:
        return "2-5"
    if event_count <= 25:
        return "6-25"
    return "26-100"


@metrics.route("/api/metrics", methods=["POST"])
@csrf.exempt
@api_route(
    request_schema=MetricsIngestRequest,
    response_schema=MetricsIngestResponseSchema,
    query_schema=TransportQuerySchema,
    error_message=MetricsFailureMessages.UNABLE_TO_RECORD_METRICS,
    error_code=MetricsErrorCodes.INVALID_FORM_INPUT,
    ajax_required=False,
    tags=[OPEN_API.METRICS],
    description="Ingest a batch of UI-category metrics events from the browser",
    status_codes={200: MetricsIngestResponseSchema, 400: ErrorResponse},
)
@limiter.limit(_METRICS_RATE_LIMIT, methods=["POST"])
def ingest(metrics_ingest_request: MetricsIngestRequest) -> FlaskResponse:
    parsed_query = parse_query_args(
        TransportQuerySchema,
        message=MetricsFailureMessages.INVALID_QUERY,
        error_code=MetricsErrorCodes.INVALID_QUERY_PARAM,
    )
    if not isinstance(parsed_query, BaseModel):
        return parsed_query

    record_event(
        EventName.API_METRICS_INGEST_BATCH,
        dimensions={
            "batch_size_bucket": bucket_batch_size(len(metrics_ingest_request.events)),
            "transport": parsed_query.transport or "fetch",
            DEVICE_TYPE_DIM_KEY: classify_user_agent(request.headers.get("User-Agent")),
        },
    )

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
@admin_required
@api_route(
    query_schema=TopEventsQuerySchema,
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
    parsed = parse_query_args(
        TopEventsQuerySchema,
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

    # `TopEventsQuerySchema.category` defaults to None; calling
    # `EventCategory(None)` directly raises ValueError, so guard explicitly.
    category_enum: EventCategory | None = (
        EventCategory(parsed.category) if parsed.category is not None else None
    )
    resource_enum: Resource | None = (
        Resource(parsed.resource) if parsed.resource is not None else None
    )
    previous_window_start, previous_window_end = previous_window(
        window_start, window_end
    )
    rows = query_service.top_events(
        window_start=window_start,
        window_end=window_end,
        previous_window_start=previous_window_start,
        previous_window_end=previous_window_end,
        category=category_enum,
        resource=resource_enum,
        device_type=parsed.device_type,
        limit=parsed.limit,
    )
    response_schema = TopEventsResponseSchema(
        window=parsed.window,
        window_start=window_start,
        window_end=window_end,
        category=parsed.category,
        resource=parsed.resource,
        events=rows,
    )
    return APIResponse(data=response_schema, status_code=200).to_response()


@metrics.route("/api/metrics/query/timeseries", methods=["GET"])
@admin_required
@api_route(
    query_schema=TimeseriesQuerySchema,
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
    parsed = parse_query_args(
        TimeseriesQuerySchema,
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

    buckets = query_service.timeseries(
        event_name=EventName(parsed.event_name),
        window_start=window_start,
        window_end=window_end,
        resolution=parsed.resolution,
        endpoint=parsed.endpoint,
        method=parsed.method,
        device_type=parsed.device_type,
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
@admin_required
@api_route(
    query_schema=SummaryQuerySchema,
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
    parsed = parse_query_args(
        SummaryQuerySchema,
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

    previous_window_start, previous_window_end = previous_window(
        window_start, window_end
    )
    summary_result = query_service.summary(
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
        last_flush_at=summary_result.last_flush_at,
        last_event_at=summary_result.last_event_at,
        by_category=summary_result.by_category,
    )
    return APIResponse(data=response_schema, status_code=200).to_response()


@metrics.route("/api/metrics/query/grouped-timeseries", methods=["GET"])
@admin_required
@api_route(
    query_schema=GroupedTimeseriesQuerySchema,
    response_schema=GroupedTimeseriesResponseSchema,
    ajax_required=True,
    tags=[OPEN_API.METRICS],
    description=(
        "Return per-(bucket × dim tuple) counts for a single event over an "
        "admin time window, grouped by 1-3 JSONB dimension keys."
    ),
    status_codes={
        200: GroupedTimeseriesResponseSchema,
        400: ErrorResponse,
        401: ErrorResponse,
        404: ErrorResponse,
    },
)
def query_grouped_timeseries() -> FlaskResponse:
    parsed = parse_query_args(
        GroupedTimeseriesQuerySchema,
        message=MetricsFailureMessages.INVALID_QUERY,
        error_code=MetricsErrorCodes.INVALID_QUERY_PARAM,
        multi_value_keys=frozenset({"group_by"}),
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

    try:
        response_schema = query_service.grouped_timeseries(
            event_name=EventName(parsed.event_name),
            group_by=parsed.group_by,
            window_start=window_start,
            window_end=window_end,
            resolution=parsed.resolution,
            partition_by_bucket=parsed.partition_by_bucket,
        )
    except ValueError as validation_error:
        return build_field_error_response(
            message=MetricsFailureMessages.INVALID_QUERY,
            errors={"group_by": [str(validation_error)]},
            error_code=MetricsErrorCodes.INVALID_QUERY_PARAM,
            status_code=400,
        )

    # Service builds the schema with `window=None`; thread the original query
    # `window` value back into the envelope so the response reflects the
    # client's request shape.
    response_schema = response_schema.model_copy(update={"window": parsed.window})
    return APIResponse(data=response_schema, status_code=200).to_response()


@metrics.route("/api/metrics/query/flow", methods=["GET"])
@admin_required
@api_route(
    query_schema=FlowQuerySchema,
    response_schema=FlowResponseSchema,
    ajax_required=True,
    tags=[OPEN_API.METRICS],
    description=(
        "Assemble one conversion funnel (UI intent → API request → domain "
        "outcome) for an admin time window, fanning out per-step counts plus "
        "per-cause drop-off breakdowns. `flow_id` is a built-in funnel from the "
        "server-side FLOWS registry or `custom_<id>` for a saved funnel (404 if "
        "absent, 422 `flow_invalid` if it no longer validates or a step count "
        "raises a `ValueError`)."
    ),
    status_codes={
        200: FlowResponseSchema,
        400: ErrorResponse,
        401: ErrorResponse,
        404: ErrorResponse,
        422: FlowInvalidResponseSchema,
    },
)
def query_flow() -> FlaskResponse:
    # No `multi_value_keys` here: `FlowQuerySchema` carries only `flow_id` +
    # window. Per-step `filter`/`group_by` slicing is configured server-side in
    # the FLOWS registry, never sent by the caller, so promoting a `filter`
    # query key would inject an empty list that `extra="forbid"` rejects.
    parsed = parse_query_args(
        FlowQuerySchema,
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

    is_built_in = parsed.flow_id in ALL_FLOW_IDS
    flow: FlowDefinition
    if is_built_in:
        # Read at request time and not re-validated: built-ins are trusted code.
        flow = FLOWS[FlowId(parsed.flow_id)]
    else:
        row_id = parse_custom_flow_id(parsed.flow_id)
        if row_id is None:
            # Unreachable while the schema pattern validates `flow_id`; kept as a
            # fail-closed guard so a pattern drift can never reach the lookup.
            return build_field_error_response(
                message=MetricsFailureMessages.INVALID_QUERY,
                errors={"flow_id": [MetricsFailureMessages.INVALID_FLOW_ID]},
                error_code=MetricsErrorCodes.INVALID_QUERY_PARAM,
                status_code=400,
            )
        row = db.session.get(Metric_Flows, row_id)
        if row is None:
            return build_message_error_response(
                message=MetricsFailureMessages.FLOW_NOT_FOUND, status_code=404
            )
        # The column wins over any stray stored `display_name` key.
        validated = validate_flow_payload(
            {**row.definition, "display_name": row.display_name}
        )
        if not isinstance(validated, FlowDefinition):
            return flow_invalid_response(
                first_invalid_detail(validated if isinstance(validated, dict) else {})
            )
        flow = validated

    try:
        response_schema = count_flow(
            definition=flow, window_start=window_start, window_end=window_end
        )
    except FlowCountError as error:
        if not is_built_in:
            return flow_invalid_response(
                FlowInvalidDetailSchema(
                    step_index=error.step_index,
                    field=error.field,
                    reason=error.reason,
                )
            )
        return build_field_error_response(
            message=MetricsFailureMessages.INVALID_QUERY,
            errors={"filter": [str(error)]},
            error_code=MetricsErrorCodes.INVALID_QUERY_PARAM,
            status_code=400,
        )

    return APIResponse(data=response_schema, status_code=200).to_response()


@metrics.route("/api/metrics/query/gauges/timeseries", methods=["GET"])
@admin_required
@api_route(
    query_schema=GaugesTimeseriesQuerySchema,
    response_schema=GaugesTimeseriesResponseSchema,
    ajax_required=True,
    tags=[OPEN_API.METRICS],
    description=(
        "Return every gauge's windowed sample series for an admin time window "
        "in one batched response, each series folding in its kind + description."
    ),
    status_codes={
        200: GaugesTimeseriesResponseSchema,
        400: ErrorResponse,
        401: ErrorResponse,
        404: ErrorResponse,
    },
)
def query_gauges_timeseries() -> FlaskResponse:
    parsed = parse_query_args(
        GaugesTimeseriesQuerySchema,
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

    response_schema = query_service.gauges_timeseries_all(
        window=parsed.window,
        window_start=window_start,
        window_end=window_end,
    )
    return APIResponse(data=response_schema, status_code=200).to_response()


@metrics.route("/api/metrics/query/latency", methods=["GET"])
@admin_required
@api_route(
    query_schema=LatencyQuerySchema,
    response_schema=LatencyPercentilesResponseSchema,
    ajax_required=True,
    tags=[OPEN_API.METRICS],
    description=(
        "Return per-(endpoint, method) p50/p95/p99 request-latency percentiles "
        "for an admin time window."
    ),
    status_codes={
        200: LatencyPercentilesResponseSchema,
        400: ErrorResponse,
        401: ErrorResponse,
        404: ErrorResponse,
    },
)
def query_latency() -> FlaskResponse:
    parsed = parse_query_args(
        LatencyQuerySchema,
        message=MetricsFailureMessages.INVALID_QUERY,
        error_code=MetricsErrorCodes.INVALID_QUERY_PARAM,
    )
    if not isinstance(parsed, BaseModel):
        return parsed

    now = utc_now()
    try:
        window_start, window_end = resolve_query_window(
            window=parsed.window,
            start=parsed.start,
            end=parsed.end,
            now=now,
        )
    except ValueError as validation_error:
        return build_field_error_response(
            message=MetricsFailureMessages.INVALID_WINDOW,
            errors={"window": [str(validation_error)]},
            error_code=MetricsErrorCodes.INVALID_QUERY_PARAM,
            status_code=400,
        )

    result = query_service.latency_percentiles(
        window_start=window_start,
        window_end=window_end,
        now=now,
        metric_name=LatencyMetricName(parsed.metric_name),
        endpoint=parsed.endpoint,
        method=parsed.method,
        device_type=parsed.device_type,
        limit=parsed.limit,
    )
    rows = result.rows
    approximate = result.approximate
    response_schema = LatencyPercentilesResponseSchema(
        window=parsed.window,
        window_start=window_start,
        window_end=window_end,
        rows=rows,
        approximate=approximate,
    )
    return APIResponse(data=response_schema, status_code=200).to_response()


@metrics.route("/api/metrics/query/latency/timeseries", methods=["GET"])
@admin_required
@api_route(
    query_schema=LatencyTimeseriesQuerySchema,
    response_schema=LatencyTimeseriesResponseSchema,
    ajax_required=True,
    tags=[OPEN_API.METRICS],
    description=(
        "Return zero-filled per-bucket p50/p95/p99 request-latency percentiles "
        "for one endpoint over an admin time window."
    ),
    status_codes={
        200: LatencyTimeseriesResponseSchema,
        400: ErrorResponse,
        401: ErrorResponse,
        404: ErrorResponse,
    },
)
def query_latency_timeseries() -> FlaskResponse:
    parsed = parse_query_args(
        LatencyTimeseriesQuerySchema,
        message=MetricsFailureMessages.INVALID_QUERY,
        error_code=MetricsErrorCodes.INVALID_QUERY_PARAM,
    )
    if not isinstance(parsed, BaseModel):
        return parsed

    now = utc_now()
    try:
        window_start, window_end = resolve_query_window(
            window=parsed.window,
            start=parsed.start,
            end=parsed.end,
            now=now,
        )
    except ValueError as validation_error:
        return build_field_error_response(
            message=MetricsFailureMessages.INVALID_WINDOW,
            errors={"window": [str(validation_error)]},
            error_code=MetricsErrorCodes.INVALID_QUERY_PARAM,
            status_code=400,
        )

    buckets = query_service.latency_timeseries(
        metric_name=LatencyMetricName(parsed.metric_name),
        window_start=window_start,
        window_end=window_end,
        now=now,
        resolution=parsed.resolution,
        endpoint=parsed.endpoint,
        method=parsed.method,
        device_type=parsed.device_type,
    )
    response_schema = LatencyTimeseriesResponseSchema(
        window=parsed.window,
        window_start=window_start,
        window_end=window_end,
        endpoint=parsed.endpoint,
        method=parsed.method,
        buckets=buckets,
    )
    return APIResponse(data=response_schema, status_code=200).to_response()
