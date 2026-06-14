from __future__ import annotations

from datetime import datetime
from typing import Literal

from flask import Blueprint, request
from pydantic import BaseModel, ValidationError

from backend import csrf, limiter, metrics_writer
from backend.api_common.auth_decorators import admin_required
from backend.api_common.parse_request import api_route
from backend.api_common.request_errors import pydantic_errors_to_dict
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.extensions.metrics.buckets import previous_window, resolve_query_window
from backend.extensions.metrics.ua_classifier import classify_user_agent
from backend.extensions.metrics.writer import record_event
from backend.metrics import query_service
from backend.metrics.constants import MetricsErrorCodes, MetricsFailureMessages
from backend.metrics.dimension_models import validate_dimensions
from backend.metrics.events import DEVICE_TYPE_DIM_KEY, EventCategory, EventName
from backend.metrics.flow_ids import FlowId
from backend.metrics.flows import FLOWS, FlowStep
from backend.metrics.query_service import grouped_counts
from backend.metrics.resources import Resource
from backend.schemas.errors import (
    ErrorResponse,
    build_field_error_response,
)
from backend.schemas.metrics import (
    FlowBreakdownRow,
    FlowResponseSchema,
    FlowStepSchema,
    GroupedTimeseriesResponseSchema,
    MetricsIngestResponseSchema,
    SummaryResponseSchema,
    TimeseriesResponseSchema,
    TopEventsResponseSchema,
)
from backend.schemas.requests.metrics import (
    FlowQuerySchema,
    GroupedTimeseriesQuerySchema,
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


def _bucket_batch_size(event_count: int) -> Literal["1", "2-5", "6-25", "26-100"]:
    """Maps a batch event_count to its closed-set bucket label.

    Examples:
        >>> _bucket_batch_size(1)
        '1'
        >>> _bucket_batch_size(5)
        '2-5'
        >>> _bucket_batch_size(100)
        '26-100'
    """
    if event_count <= 1:
        return "1"
    if event_count <= 5:
        return "2-5"
    if event_count <= 25:
        return "6-25"
    return "26-100"


def _parse_query_args(
    schema_cls: type[BaseModel],
    multi_value_keys: frozenset[str] | None = None,
) -> BaseModel | FlaskResponse:
    """Validate `request.args` against a Pydantic query schema.

    Returns the validated model on success or a 400 field-error response on
    `ValidationError`. Callers check `isinstance(result, BaseModel)` to
    short-circuit on the error branch.

    Why a module-private helper: every query route runs the same
    args-to-dict + model_validate + error-envelope dance; centralizing it
    keeps the route bodies focused on parse_window + service call + envelope.

    `multi_value_keys` names query-string keys that should be promoted from a
    single flat string to a list (via `request.args.getlist(key)`) before
    Pydantic validation. Callers that pass `None` get the default empty
    frozenset and the original flat behaviour. The `None` default mirrors
    the project's non-mutable-default-arg convention even though `frozenset`
    is immutable.
    """
    multi_value_keys = multi_value_keys or frozenset()
    args_dict = request.args.to_dict(flat=True)
    for multi_value_key in multi_value_keys:
        args_dict[multi_value_key] = request.args.getlist(multi_value_key)
    try:
        return schema_cls.model_validate(args_dict)
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
    parsed_query = _parse_query_args(TransportQuerySchema)
    if not isinstance(parsed_query, BaseModel):
        return parsed_query

    record_event(
        EventName.API_METRICS_INGEST_BATCH,
        dimensions={
            "batch_size_bucket": _bucket_batch_size(len(metrics_ingest_request.events)),
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
    parsed = _parse_query_args(TopEventsQuerySchema)
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
    parsed = _parse_query_args(TimeseriesQuerySchema)
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
    parsed = _parse_query_args(SummaryQuerySchema)
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
    parsed = _parse_query_args(
        GroupedTimeseriesQuerySchema,
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


def _count_flow_step(
    step: FlowStep, window_start: datetime, window_end: datetime
) -> int:
    """Compute the scalar count for one funnel step over the window.

    UI/DOMAIN steps count `step.event_name`; API steps match `API_HIT`'s flat
    `endpoint`/`method` columns (plus any per-step filter). Both call
    `grouped_counts(group_by=None)`, which returns a scalar `int`.
    """
    if step.event_name is not None:
        count = grouped_counts(
            event_name=step.event_name,
            window_start=window_start,
            window_end=window_end,
            dim_filter=step.filter,
            group_by=None,
        )
    else:
        api_filter: list[tuple[str, str]] = [
            ("endpoint", step.api_endpoint or ""),
            ("method", step.api_method or ""),
        ] + (step.filter or [])
        count = grouped_counts(
            event_name=EventName.API_HIT,
            window_start=window_start,
            window_end=window_end,
            dim_filter=api_filter,
            group_by=None,
        )
    assert isinstance(count, int)
    return count


def _build_step_breakdown(
    step: FlowStep, window_start: datetime, window_end: datetime
) -> list[FlowBreakdownRow] | None:
    """Build a step's per-cause breakdown rows, or `None` when empty (DD-6).

    Returns `None` both when the step has no `drop_breakdown` configured and
    when the breakdown event has no rows in the window, so the renderer can
    skip the per-cause pill block uniformly.
    """
    if step.drop_breakdown is None:
        return None
    raw_rows = grouped_counts(
        event_name=step.drop_breakdown.event_name,
        window_start=window_start,
        window_end=window_end,
        dim_filter=step.drop_breakdown.filter,
        group_by=step.drop_breakdown.group_by,
    )
    assert isinstance(raw_rows, list)
    if not raw_rows:
        return None
    breakdown_total = sum(count for _, count in raw_rows)
    return [
        FlowBreakdownRow(
            label=group_value,
            count=count,
            pct_of_step=0.0 if breakdown_total == 0 else count / breakdown_total,
        )
        for group_value, count in raw_rows
    ]


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
        "per-cause drop-off breakdowns from the server-side FLOWS registry."
    ),
    status_codes={
        200: FlowResponseSchema,
        400: ErrorResponse,
        401: ErrorResponse,
        404: ErrorResponse,
    },
)
def query_flow() -> FlaskResponse:
    # No `multi_value_keys` here: `FlowQuerySchema` carries only `flow_id` +
    # window. Per-step `filter`/`group_by` slicing is configured server-side in
    # the FLOWS registry, never sent by the caller, so promoting a `filter`
    # query key would inject an empty list that `extra="forbid"` rejects.
    parsed = _parse_query_args(FlowQuerySchema)
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

    flow = FLOWS[FlowId(parsed.flow_id)]

    try:
        step_counts = [
            _count_flow_step(step, window_start, window_end) for step in flow.steps
        ]
        step_breakdowns = [
            _build_step_breakdown(step, window_start, window_end) for step in flow.steps
        ]
    except ValueError as validation_error:
        return build_field_error_response(
            message=MetricsFailureMessages.INVALID_QUERY,
            errors={"filter": [str(validation_error)]},
            error_code=MetricsErrorCodes.INVALID_QUERY_PARAM,
            status_code=400,
        )

    top_count = step_counts[0]
    response_steps: list[FlowStepSchema] = []
    for step, count, breakdown in zip(flow.steps, step_counts, step_breakdowns):
        pct_of_top = None if top_count == 0 else min(count, top_count) / top_count
        event_name = step.label if step.event_name is None else step.event_name.value
        response_steps.append(
            FlowStepSchema(
                stream=step.stream,
                label=step.label,
                event_name=event_name,
                count=count,
                pct_of_top=pct_of_top,
                breakdown=breakdown,
            )
        )

    response_schema = FlowResponseSchema(steps=response_steps)
    return APIResponse(data=response_schema, status_code=200).to_response()
