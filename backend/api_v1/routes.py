from flask import Blueprint
from flask_login import current_user

from backend import limiter
from backend.api_common.auth_decorators import api_authentication_required
from backend.api_common.parse_request import api_route
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.api_v1.constants import API_AUTH_RATE_LIMIT, ApiAuthErrorCodes
from backend.api_v1.services.auth import (
    google_auth_for_api,
    login_user_for_api,
    logout_api_device,
    logout_api_everywhere,
    refresh_api_tokens,
    resend_validation_email_for_api,
)
from backend.schemas.api_v1 import ApiTokenPairResponseSchema, ApiUserProfileSchema
from backend.schemas.base import StatusMessageResponseSchema
from backend.schemas.errors import ErrorResponse, build_message_error_response
from backend.schemas.requests.api_auth import (
    ApiGoogleAuthRequest,
    ApiLoginRequest,
    ApiLogoutRequest,
    ApiRefreshRequest,
)
from backend.utils.strings.api_auth_strs import API_AUTH_FAILURE, API_V1_URL_PREFIX
from backend.utils.strings.json_strs import FAILURE_GENERAL
from backend.utils.strings.openapi_strs import OPEN_API
from backend.utils.strings.user_strs import USER_FAILURE

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


@api_v1.route("/auth/login", methods=["POST"])
@api_route(
    request_schema=ApiLoginRequest,
    response_schema=ApiTokenPairResponseSchema,
    error_message=USER_FAILURE.UNABLE_TO_LOGIN,
    error_code=ApiAuthErrorCodes.INVALID_FORM_INPUT,
    ajax_required=False,
    tags=[OPEN_API.MOBILE_API],
    description="Log in with username and password, receiving an access + refresh token pair",
    status_codes={
        200: ApiTokenPairResponseSchema,
        400: ErrorResponse,
        429: ErrorResponse,
    },
)
@limiter.limit(API_AUTH_RATE_LIMIT, methods=["POST"])
def api_v1_auth_login(api_login_request: ApiLoginRequest) -> FlaskResponse:
    return login_user_for_api(
        username=api_login_request.username,
        password=api_login_request.password,
    )


@api_v1.route("/auth/refresh", methods=["POST"])
@api_route(
    request_schema=ApiRefreshRequest,
    response_schema=ApiTokenPairResponseSchema,
    error_message=API_AUTH_FAILURE.INVALID_REFRESH_TOKEN,
    error_code=ApiAuthErrorCodes.INVALID_FORM_INPUT,
    ajax_required=False,
    tags=[OPEN_API.MOBILE_API],
    description="Rotate a refresh token for a new access + refresh token pair",
    status_codes={
        200: ApiTokenPairResponseSchema,
        400: ErrorResponse,
        401: ErrorResponse,
        429: ErrorResponse,
    },
)
@limiter.limit(API_AUTH_RATE_LIMIT, methods=["POST"])
def api_v1_auth_refresh(api_refresh_request: ApiRefreshRequest) -> FlaskResponse:
    return refresh_api_tokens(refresh_token=api_refresh_request.refresh_token)


@api_v1.route("/auth/logout", methods=["POST"])
@api_route(
    request_schema=ApiLogoutRequest,
    response_schema=StatusMessageResponseSchema,
    error_message=API_AUTH_FAILURE.INVALID_REFRESH_TOKEN,
    error_code=ApiAuthErrorCodes.INVALID_FORM_INPUT,
    ajax_required=False,
    tags=[OPEN_API.MOBILE_API],
    description="Log out this device by revoking the presented refresh token's rotation family",
    status_codes={
        200: StatusMessageResponseSchema,
        400: ErrorResponse,
        401: ErrorResponse,
        429: ErrorResponse,
    },
)
@limiter.limit(API_AUTH_RATE_LIMIT, methods=["POST"])
def api_v1_auth_logout(api_logout_request: ApiLogoutRequest) -> FlaskResponse:
    return logout_api_device(refresh_token=api_logout_request.refresh_token)


@api_v1.route("/auth/logout-all", methods=["POST"])
@api_authentication_required
@api_route(
    response_schema=StatusMessageResponseSchema,
    ajax_required=False,
    tags=[OPEN_API.MOBILE_API],
    description="Log out everywhere by revoking every refresh token for the authenticated user",
    status_codes={
        200: StatusMessageResponseSchema,
        401: ErrorResponse,
        429: ErrorResponse,
    },
)
@limiter.limit(API_AUTH_RATE_LIMIT, methods=["POST"])
def api_v1_auth_logout_all() -> FlaskResponse:
    return logout_api_everywhere()


@api_v1.route("/auth/resend-validation", methods=["POST"])
@api_authentication_required
@api_route(
    response_schema=StatusMessageResponseSchema,
    ajax_required=False,
    tags=[OPEN_API.MOBILE_API],
    description="Re-send the email-validation email for the authenticated (unvalidated) user",
    status_codes={
        200: StatusMessageResponseSchema,
        400: ErrorResponse,
        401: ErrorResponse,
        404: ErrorResponse,
        429: ErrorResponse,
    },
)
@limiter.limit(API_AUTH_RATE_LIMIT, methods=["POST"])
def api_v1_auth_resend_validation() -> FlaskResponse:
    return resend_validation_email_for_api()


@api_v1.route("/auth/google", methods=["POST"])
@api_route(
    request_schema=ApiGoogleAuthRequest,
    response_schema=ApiTokenPairResponseSchema,
    error_message=API_AUTH_FAILURE.UNABLE_TO_VERIFY_GOOGLE_TOKEN,
    error_code=ApiAuthErrorCodes.INVALID_FORM_INPUT,
    ajax_required=False,
    tags=[OPEN_API.MOBILE_API],
    description="Exchange a native Google Sign-In id_token for an access + refresh token pair",
    status_codes={
        200: ApiTokenPairResponseSchema,
        400: ErrorResponse,
        401: ErrorResponse,
        403: ErrorResponse,
        409: ErrorResponse,
        429: ErrorResponse,
    },
)
@limiter.limit(API_AUTH_RATE_LIMIT, methods=["POST"])
def api_v1_auth_google(api_google_auth_request: ApiGoogleAuthRequest) -> FlaskResponse:
    return google_auth_for_api(id_token=api_google_auth_request.id_token)


# Register UTub, Member, URL, tag, and search routes on this blueprint. The
# imports must appear after the blueprint object is defined above; this is the
# standard Flask pattern for splitting a blueprint across multiple modules.
from backend.api_v1 import utub_member_routes  # noqa: E402,F401
from backend.api_v1 import tag_search_routes, url_routes  # noqa: E402,F401
