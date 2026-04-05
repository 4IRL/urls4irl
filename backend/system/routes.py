from flask import Blueprint

from backend import limiter
from backend.api_common.parse_request import api_route
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.schemas.system import HealthResponseSchema
from backend.utils.strings.openapi_strs import OPEN_API

system = Blueprint("system", __name__)


@system.route("/health", methods=["GET"])
@limiter.exempt
@api_route(
    response_schema=HealthResponseSchema,
    ajax_required=False,
    tags=[OPEN_API.SYSTEM],
    description="Health check endpoint",
    status_codes={200: HealthResponseSchema},
)
def health() -> FlaskResponse:
    return APIResponse(status_code=200).to_response()
