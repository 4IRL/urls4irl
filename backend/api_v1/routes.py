from flask import Blueprint
from flask_login import current_user

from backend.api_common.auth_decorators import api_authentication_required
from backend.api_common.parse_request import api_route
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.schemas.api_v1 import ApiUserProfileSchema
from backend.schemas.errors import ErrorResponse, build_message_error_response
from backend.utils.strings.api_auth_strs import API_V1_URL_PREFIX
from backend.utils.strings.json_strs import FAILURE_GENERAL
from backend.utils.strings.openapi_strs import OPEN_API

# Bearer-token surface for native mobile clients. Blueprint-wide conventions:
# - CSRF-exempt (csrf.exempt(api_v1) in create_app) — bearer clients carry no
#   CSRF token.
# - Every @api_route sets ajax_required=False — no X-Requested-With sentinel.
# - Every view function is named with the api_v1_ prefix so OpenAPI
#   operationIds never collide with the web blueprints' view names.
# - Errors are ALWAYS the JSON ErrorResponse envelope, regardless of Accept.
api_v1 = Blueprint("api_v1", __name__, url_prefix=API_V1_URL_PREFIX)


@api_v1.errorhandler(404)
def api_v1_handle_404(_) -> FlaskResponse:
    """JSON 404 for abort(404)/get_or_404 raised inside api_v1 views.

    Routing-level 404s (unmatched /api/v1 paths) never enter the blueprint;
    those are covered by the JSON branch in the app-level 404 handler
    (backend/api_common/error_handler.py).
    """
    return build_message_error_response(
        message=FAILURE_GENERAL.NOT_FOUND, status_code=404
    )


@api_v1.route("/me", methods=["GET"])
@api_authentication_required
@api_route(
    response_schema=ApiUserProfileSchema,
    ajax_required=False,
    tags=[OPEN_API.MOBILE_API],
    description="Retrieve the authenticated user's profile",
    status_codes={200: ApiUserProfileSchema, 401: ErrorResponse},
)
def api_v1_get_me() -> FlaskResponse:
    """Probe/profile endpoint: exercises request_loader -> bearer decorator ->
    JSON response end-to-end. Reachable by unvalidated-email accounts so a
    mobile client can render its "verify your email" screen."""
    return APIResponse(
        status_code=200,
        data=ApiUserProfileSchema.model_validate(current_user),
    ).to_response()
