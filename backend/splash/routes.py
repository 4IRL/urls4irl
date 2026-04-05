from flask import (
    Blueprint,
    redirect,
    url_for,
    render_template,
    request,
    abort,
)
from flask_login import current_user, login_user
from werkzeug import Response as WerkzeugResponse

from backend import db
from backend.api_common.auth_decorators import (
    no_authenticated_users_allowed,
)
from backend.api_common.parse_request import api_route
from backend.api_common.responses import FlaskResponse
from backend.app_logger import (
    safe_add_log,
    warning_log,
)
from backend.models.email_validations import Email_Validations
from backend.models.users import Users
from backend.schemas.errors import ErrorResponse
from backend.schemas.requests.splash import (
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
)
from backend.schemas.users import (
    EmailValidationResponseSchema,
    ForgotPasswordResponseSchema,
    LoginRedirectResponseSchema,
    RegisterResponseSchema,
    ResetPasswordResponseSchema,
)
from backend.splash.constants import (
    ForgotPasswordErrorCodes,
    LoginErrorCodes,
    RegisterErrorCodes,
    ResetPasswordErrorCodes,
)
from backend.splash.services.forgot_password import (
    send_forgot_password_email_to_user,
)
from backend.splash.services.reset_password import (
    get_reset_password_page,
    reset_password_for_user,
)
from backend.splash.services.user_login import login_user_to_u4i
from backend.splash.services.user_registration import (
    register_new_user,
)
from backend.splash.services.validate_email import (
    send_validation_email_to_user,
    validate_email_for_user,
)
from backend.utils.strings.email_validation_strs import EMAILS
from backend.utils.strings.openapi_strs import OPEN_API
from backend.utils.strings.reset_password_strs import FORGOT_PASSWORD, RESET_PASSWORD
from backend.utils.strings.user_strs import USER_FAILURE
from backend.utils.all_routes import ROUTES
from backend.utils.constants import provide_config_for_constants

splash = Blueprint("splash", __name__)


# TODO: Separate splash context processor from home page context processor
@splash.context_processor
def provide_constants():
    return provide_config_for_constants()


@splash.route("/invalid")
def error_page():
    abort(404)


@splash.route("/", methods=["GET"])
def splash_page() -> WerkzeugResponse | str:
    """Splash page for an unlogged in user."""
    if current_user.is_authenticated and current_user.email_validated:
        safe_add_log(f"User={current_user} already logged in")
        return redirect(url_for(ROUTES.UTUBS.HOME))
    show_email_validation = (
        current_user.is_authenticated and not current_user.email_validated
    )
    return render_template(
        "pages/splash.html", show_email_validation=show_email_validation
    )


@splash.route("/register", methods=["POST"])
@no_authenticated_users_allowed
@api_route(
    request_schema=RegisterRequest,
    response_schema=RegisterResponseSchema,
    error_message=USER_FAILURE.UNABLE_TO_REGISTER,
    error_code=RegisterErrorCodes.INVALID_FORM_INPUT,
    ajax_required=False,
    tags=[OPEN_API.AUTH],
    description="Register a new user account",
    status_codes={201: RegisterResponseSchema, 400: ErrorResponse, 401: ErrorResponse},
)
def register_user(register_request: RegisterRequest) -> FlaskResponse:
    """Handles registration form submission."""
    return register_new_user(
        register_request.username,
        register_request.email,
        register_request.password,
    )


@splash.route("/login", methods=["POST"])
@no_authenticated_users_allowed
@api_route(
    request_schema=LoginRequest,
    response_schema=LoginRedirectResponseSchema,
    error_message=USER_FAILURE.UNABLE_TO_LOGIN,
    error_code=LoginErrorCodes.INVALID_FORM_INPUT,
    ajax_required=False,
    tags=[OPEN_API.AUTH],
    description="Log in to an existing account",
    status_codes={
        200: LoginRedirectResponseSchema,
        400: ErrorResponse,
        401: ErrorResponse,
    },
)
def login(login_request: LoginRequest) -> FlaskResponse:
    """Handles login form submission."""
    return login_user_to_u4i(login_request.username, login_request.password)


@splash.route("/confirm-email", methods=["GET"])
def confirm_email_after_register() -> WerkzeugResponse:
    if current_user.is_anonymous:
        safe_add_log("No user logged in")
        return redirect(url_for(ROUTES.SPLASH.SPLASH_PAGE))
    if current_user.email_validated:
        warning_log(f"User={current_user.id} already logged in")
        return redirect(url_for(ROUTES.UTUBS.HOME))
    return redirect(url_for(ROUTES.SPLASH.SPLASH_PAGE))


@splash.route("/send-validation-email", methods=["POST"])
@api_route(
    response_schema=EmailValidationResponseSchema,
    ajax_required=False,
    tags=[OPEN_API.AUTH],
    description="Send an email validation link to the current user",
    status_codes={
        200: EmailValidationResponseSchema,
        400: ErrorResponse,
        404: ErrorResponse,
        429: ErrorResponse,
    },
)
def send_validation_email() -> WerkzeugResponse | FlaskResponse:
    return send_validation_email_to_user()


@splash.route("/validate/expired", methods=["GET"])
def validate_email_expired():
    expired_token = request.args.get("token", None)
    if expired_token is None:
        warning_log("No token provided")
        abort(404)

    invalid_email: Email_Validations = Email_Validations.query.filter(
        Email_Validations.validation_token == expired_token
    ).first_or_404()

    user_with_expired_token: Users = invalid_email.user
    new_token = user_with_expired_token.get_email_validation_token()
    invalid_email.validation_token = new_token
    invalid_email.reset_attempts()
    db.session.commit()
    login_user(user_with_expired_token)

    safe_add_log(f"User={user_with_expired_token.id} email validation token reset")
    return (
        render_template(
            "pages/splash.html",
            email_token_is_expired=True,
            expired_token_message=EMAILS.TOKEN_EXPIRED,
        ),
        200,
    )


@splash.route("/validate/<string:token>", methods=["GET"])
def validate_email(token: str) -> WerkzeugResponse:
    return validate_email_for_user(token)


@splash.route("/forgot-password", methods=["POST"])
@no_authenticated_users_allowed
@api_route(
    request_schema=ForgotPasswordRequest,
    response_schema=ForgotPasswordResponseSchema,
    error_message=FORGOT_PASSWORD.INVALID_EMAIL,
    error_code=ForgotPasswordErrorCodes.INVALID_FORM_INPUT,
    ajax_required=False,
    tags=[OPEN_API.AUTH],
    description="Send a password reset email",
    status_codes={200: ForgotPasswordResponseSchema, 400: ErrorResponse},
)
def forgot_password(forgot_password_request: ForgotPasswordRequest) -> FlaskResponse:
    return send_forgot_password_email_to_user(forgot_password_request.email)


@splash.route("/reset-password/<string:token>", methods=["GET"])
def reset_password_page(token: str) -> WerkzeugResponse | str:
    return get_reset_password_page(token)


@splash.route("/reset-password/<string:token>", methods=["POST"])
@api_route(
    request_schema=ResetPasswordRequest,
    response_schema=ResetPasswordResponseSchema,
    error_message=RESET_PASSWORD.RESET_PASSWORD_INVALID,
    error_code=ResetPasswordErrorCodes.INVALID_FORM_INPUT,
    ajax_required=False,
    tags=[OPEN_API.AUTH],
    description="Reset a user password with a valid token",
    status_codes={
        200: ResetPasswordResponseSchema,
        400: ErrorResponse,
        404: ErrorResponse,
    },
)
def reset_password(
    token: str, reset_password_request: ResetPasswordRequest
) -> FlaskResponse:
    return reset_password_for_user(token, reset_password_request.new_password)
