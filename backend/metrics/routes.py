from __future__ import annotations

from flask import Blueprint
from pydantic import ValidationError

from backend import csrf, limiter, metrics_writer
from backend.api_common.parse_request import api_route
from backend.api_common.request_errors import pydantic_errors_to_dict
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.extensions.metrics.writer import record_event
from backend.metrics.constants import MetricsErrorCodes, MetricsFailureMessages
from backend.metrics.dimension_models import validate_dimensions
from backend.metrics.events import EventName
from backend.schemas.errors import (
    ErrorResponse,
    build_field_error_response,
)
from backend.schemas.metrics import MetricsIngestResponseSchema
from backend.schemas.requests.metrics import MetricsIngestRequest
from backend.utils.strings.openapi_strs import OPEN_API

metrics = Blueprint("metrics", __name__)

# Rate limit values are conservative — Phase 4 batches with debounce, so
# 120/min/IP is generous; tighten once frontend telemetry lands if needed.
_METRICS_RATE_LIMIT = "120 per minute, 3000 per hour"


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
