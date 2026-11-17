import time

from flask import Blueprint, current_app, request

from backend import limiter
from backend.api_common.parse_request import api_route
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.app_logger import info_log, warning_log
from backend.db import get_missing_tables
from backend.schemas.base import StatusMessageResponseSchema
from backend.schemas.system import DeepHealthResponseSchema, HealthResponseSchema
from backend.system.health_checks import (
    HEALTH_DEEP_FAILED_ATTEMPT_RATE_LIMIT,
    MS_PER_SECOND,
    STATUS_UP,
    Budget,
    is_health_token_valid,
    probe_metrics_redis,
    probe_postgres,
    probe_session_redis,
)
from backend.utils.strings.config_strs import CONFIG_ENVS
from backend.utils.strings.health_strs import HEALTH_STRS
from backend.utils.strings.openapi_strs import OPEN_API

system = Blueprint("system", __name__)


@system.route("/health", methods=["GET"])
@limiter.exempt
@api_route(
    response_schema=HealthResponseSchema,
    ajax_required=False,
    tags=[OPEN_API.SYSTEM],
    description="Health check endpoint. Pass ?db=true to verify all database tables exist.",
    status_codes={200: HealthResponseSchema, 503: StatusMessageResponseSchema},
)
def health() -> FlaskResponse:
    if request.args.get("db", "").lower() == "true":
        missing_tables = get_missing_tables()
        if missing_tables:
            return APIResponse(
                status_code=503,
                message=f"Missing tables: {', '.join(missing_tables)}",
            ).to_response()
        return APIResponse(
            status_code=200,
            message="All database tables verified",
        ).to_response()

    return APIResponse(status_code=200).to_response()


def _unauthorized_response(expected: str | None, provided: str | None) -> FlaskResponse:
    if expected is None or not expected.strip():
        warning_log("Deep health check rejected: secret unset")
    elif not provided:
        info_log("Deep health check rejected: header missing")
    else:
        warning_log("Deep health check rejected: token mismatch")
    return APIResponse(status_code=401, message=HEALTH_STRS.UNAUTHORIZED).to_response()


def _has_valid_health_token() -> bool:
    return is_health_token_valid(
        request.headers.get(CONFIG_ENVS.X_HEALTH_TOKEN),
        current_app.config.get(CONFIG_ENVS.HEALTH_CHECK_TOKEN),
    )


def _is_rejected_attempt(response: FlaskResponse) -> bool:
    return response.status_code == 401


# Valid-token calls are exempt; only rejected (401) attempts count per IP.
@system.route("/health/deep", methods=["GET"])
@limiter.limit(
    HEALTH_DEEP_FAILED_ATTEMPT_RATE_LIMIT,
    exempt_when=_has_valid_health_token,
    deduct_when=_is_rejected_attempt,
)
@api_route(
    response_schema=DeepHealthResponseSchema,
    ajax_required=False,
    tags=[OPEN_API.SYSTEM],
    description=(
        "Deep health check of Postgres, the session Redis and the metrics Redis. "
        "Requires the X-Health-Token header; 401 reveals no component detail. "
        "Rejected attempts are rate limited per IP (429)."
    ),
    status_codes={
        200: DeepHealthResponseSchema,
        401: StatusMessageResponseSchema,
        429: StatusMessageResponseSchema,
        503: DeepHealthResponseSchema,
    },
)
def health_deep() -> FlaskResponse:
    expected = current_app.config.get(CONFIG_ENVS.HEALTH_CHECK_TOKEN)
    provided = request.headers.get(CONFIG_ENVS.X_HEALTH_TOKEN)
    if not is_health_token_valid(provided, expected):
        return _unauthorized_response(expected, provided)

    started_at = time.monotonic()
    budget = Budget.start()
    components = {
        HEALTH_STRS.POSTGRES: probe_postgres(budget),
        HEALTH_STRS.SESSION_REDIS: probe_session_redis(budget),
        HEALTH_STRS.METRICS_REDIS: probe_metrics_redis(budget),
    }
    unhealthy = [
        key for key in HEALTH_STRS.COMPONENT_ORDER if components[key] != STATUS_UP
    ]
    summary = ", ".join(f"{key}={value}" for key, value in components.items())
    duration_ms = int((time.monotonic() - started_at) * MS_PER_SECOND)
    info_log(f"Deep health check: {summary} in {duration_ms}ms")

    if unhealthy:
        return APIResponse(
            status_code=503,
            message=HEALTH_STRS.UNHEALTHY_PREFIX + ", ".join(unhealthy),
            data={HEALTH_STRS.COMPONENTS: components},
        ).to_response()
    return APIResponse(
        status_code=200, data={HEALTH_STRS.COMPONENTS: components}
    ).to_response()
