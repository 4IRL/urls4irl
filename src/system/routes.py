from flask import Blueprint

from src import limiter
from src.api_common.responses import APIResponse, FlaskResponse

system = Blueprint("system", __name__)


@system.route("/health", methods=["GET"])
@limiter.exempt
def health() -> FlaskResponse:
    return APIResponse(status_code=200).to_response()
