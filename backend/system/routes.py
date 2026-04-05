from flask import Blueprint, request

from backend import limiter
from backend.api_common.parse_request import api_route
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.db import get_missing_tables
from backend.schemas.base import StatusMessageResponseSchema
from backend.schemas.system import HealthResponseSchema
from backend.utils.strings.openapi_strs import OPEN_API

system = Blueprint("system", __name__)


@system.route("/health", methods=["GET"])
@limiter.exempt
@api_route(
    response_schema=HealthResponseSchema,
    ajax_required=False,
    tags=[OPEN_API.SYSTEM],
    description="Health check endpoint. Pass ?db=true to verify all database tables exist.",
    status_codes={200: StatusMessageResponseSchema, 503: StatusMessageResponseSchema},
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
