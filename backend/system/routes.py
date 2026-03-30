from flask import Blueprint

from backend import limiter
from backend.api_common.parse_request import api_route
from backend.api_common.responses import APIResponse, FlaskResponse

system = Blueprint("system", __name__)


@system.route("/health", methods=["GET"])
@limiter.exempt
@api_route()
def health() -> FlaskResponse:
    return APIResponse(status_code=200).to_response()
