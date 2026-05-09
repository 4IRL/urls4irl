from __future__ import annotations

from flask import Blueprint, request
from flask_wtf.csrf import CSRFError, validate_csrf
from pydantic import ValidationError
from wtforms import ValidationError as WTFormsValidationError

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
    build_message_error_response,
)
from backend.schemas.metrics import MetricsIngestResponseSchema
from backend.schemas.requests.metrics import MetricsIngestRequest
from backend.utils.strings.openapi_strs import OPEN_API

metrics = Blueprint("metrics", __name__)

# Rate limit values are conservative — Phase 4 batches with debounce, so
# 120/min/IP is generous; tighten once frontend telemetry lands if needed.
_METRICS_RATE_LIMIT = "120 per minute, 3000 per hour"


def _pick_csrf_token(*, header_token: str | None, body_token: str | None) -> str | None:
    """Pick a CSRF token from the X-CSRFToken header (preferred) or the JSON
    body's `csrf_token` field (sendBeacon fallback).

    Empty strings count as missing so callers can safely funnel both
    "header absent" and "header present but blank" into the body fallback.
    """
    if header_token:
        return header_token
    if body_token:
        return body_token
    return None


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
    submitted_token = _pick_csrf_token(
        header_token=request.headers.get("X-CSRFToken"),
        body_token=metrics_ingest_request.csrf_token,
    )

    try:
        validate_csrf(submitted_token)
    except WTFormsValidationError as csrf_validation_error:
        if submitted_token:
            # A real token was submitted but is invalid/expired/mismatched —
            # raise CSRFError manually so the global handler returns 403.
            raise CSRFError(str(csrf_validation_error))
        return build_message_error_response(
            message=MetricsFailureMessages.MISSING_CSRF,
            error_code=MetricsErrorCodes.INVALID_FORM_INPUT,
            status_code=400,
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
