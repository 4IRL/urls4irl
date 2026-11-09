from flask import (
    Blueprint,
    abort,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user
from werkzeug import Response as WerkzeugResponse

from backend import csrf, db, limiter
from backend.api_common.auth_decorators import (
    email_validation_required,
    no_authenticated_users_allowed,
)
from backend.api_common.parse_request import api_route
from backend.api_common.responses import FlaskResponse
from backend.app_logger import (
    safe_add_log,
    warning_log,
)
from backend.invite_links.next_target import (
    invite_next_redirect_path,
    parse_invite_next,
)
from backend.models.email_validations import Email_Validations
from backend.models.users import Users
from backend.schemas.base import (
    EmptyRedirectSchema,
    HtmlErrorPageSchema,
    StatusMessageResponseSchema,
)
from backend.schemas.errors import (
    ErrorResponse,
    LoginEmailNotValidatedErrorResponse,
    build_message_error_response,
)
from backend.schemas.requests.splash import (
    ConfirmLinkRequest,
    ForgotPasswordRequest,
    GitHubOAuthCallbackQuerySchema,
    GoogleOAuthCallbackQuerySchema,
    LoginRequest,
    RegisterRequest,
    ResendRegistrationEmailRequest,
    ResetPasswordRequest,
)
from backend.schemas.users import (
    ForgotPasswordResponseSchema,
    LoginRedirectResponseSchema,
    RegisterResponseSchema,
    ResetPasswordResponseSchema,
)
from backend.splash.constants import (
    SPLASH_AUTH_RATE_LIMIT,
    ForgotPasswordErrorCodes,
    LoginErrorCodes,
    OAuthLinkErrorCodes,
    RegisterErrorCodes,
    ResetPasswordErrorCodes,
)
from backend.splash.services.change_email import (
    EMAIL_CHANGE_STATUS_QUERY_PARAM,
    build_email_change_banner,
    confirm_email_change_for_user,
)
from backend.splash.services.forgot_password import (
    send_forgot_password_email_to_user,
)
from backend.splash.services.oauth.github_service import (
    handle_github_callback,
    initiate_github_login,
)
from backend.splash.services.oauth.google_service import (
    handle_google_callback,
    initiate_google_login,
)
from backend.splash.services.oauth.linking_service import (
    confirm_link_with_password,
    initiate_link_oauth_redirect,
    render_confirm_link_page,
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
    send_resend_registration_email,
    send_resend_validation_email_for_token,
    validate_email_for_user,
)
from backend.utils.all_routes import ROUTES
from backend.utils.constants import provide_config_for_constants
from backend.utils.strings.email_validation_strs import EMAILS
from backend.utils.strings.oauth_strs import CONFIRM_LINK_INVALID_MESSAGE
from backend.utils.strings.openapi_strs import OPEN_API
from backend.utils.strings.reset_password_strs import FORGOT_PASSWORD, RESET_PASSWORD
from backend.utils.strings.user_strs import USER_FAILURE

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
    # DD-9: an already-logged-in browser is redirected to HOME before any banner
    # renders here, so forward the confirm-outcome code so HOME can surface it.
    email_change_status = request.args.get(EMAIL_CHANGE_STATUS_QUERY_PARAM, "")
    # Only exactly one `next` key with exactly one value counts, matching the client
    # `size === 1 && get("next") !== null` gate; format-only, never checks liveness.
    invite_target = (
        parse_invite_next(request.args.get("next"))
        if len(request.args) == 1 and len(request.args.getlist("next")) == 1
        else None
    )
    if current_user.is_authenticated:
        safe_add_log(f"User={current_user} already logged in")
        if invite_target and current_user.email_validated:
            return redirect(invite_next_redirect_path(invite_target))
        return redirect(
            url_for(
                ROUTES.UTUBS.HOME,
                **(
                    {EMAIL_CHANGE_STATUS_QUERY_PARAM: email_change_status}
                    if email_change_status
                    else {}
                ),
            )
        )
    # DD-1/DD-15: this call site is reached only by anonymous requesters (an
    # authenticated user was redirected above), so the splash-path banner keeps
    # the "log in as usual" clause (authenticated=False).
    email_change_banner = build_email_change_banner(
        email_change_status, authenticated=False
    )
    return render_template(
        "pages/splash.html",
        email_change_banner=email_change_banner,
        auth_modal_hint=invite_target.hint if invite_target else None,
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
    status_codes={
        200: RegisterResponseSchema,
        400: ErrorResponse,
        429: ErrorResponse,
    },
)
@limiter.limit(SPLASH_AUTH_RATE_LIMIT, methods=["POST"])
def register_user(register_request: RegisterRequest) -> FlaskResponse:
    """Handles registration form submission."""
    return register_new_user(
        register_request.username,
        register_request.email,
        register_request.password,
        register_request.invite_next,
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
        401: LoginEmailNotValidatedErrorResponse,
        429: ErrorResponse,
    },
)
@limiter.limit(SPLASH_AUTH_RATE_LIMIT, methods=["POST"])
def login(login_request: LoginRequest) -> FlaskResponse:
    """Handles login form submission."""
    return login_user_to_u4i(login_request.username, login_request.password)


@splash.route("/resend-registration-email", methods=["POST"])
@no_authenticated_users_allowed
@api_route(
    request_schema=ResendRegistrationEmailRequest,
    response_schema=StatusMessageResponseSchema,
    error_message=USER_FAILURE.UNABLE_TO_REGISTER,
    error_code=RegisterErrorCodes.INVALID_FORM_INPUT,
    ajax_required=False,
    tags=[OPEN_API.AUTH],
    description="Resend the account-confirmation email for a pending registration (opaque). Body takes exactly one of email or resendToken (from a login on an unconfirmed account)",
    status_codes={
        200: StatusMessageResponseSchema,
        400: ErrorResponse,
        429: ErrorResponse,
    },
)
@limiter.limit(SPLASH_AUTH_RATE_LIMIT, methods=["POST"])
def resend_registration_email(
    resend_registration_email_request: ResendRegistrationEmailRequest,
) -> FlaskResponse:
    if resend_registration_email_request.resend_token is not None:
        return send_resend_validation_email_for_token(
            resend_registration_email_request.resend_token
        )
    if resend_registration_email_request.email is None:
        # Unreachable past the schema validator; fail closed.
        return build_message_error_response(
            message=USER_FAILURE.UNABLE_TO_REGISTER,
            error_code=RegisterErrorCodes.INVALID_FORM_INPUT,
        )
    return send_resend_registration_email(resend_registration_email_request.email)


@splash.route("/validate/expired", methods=["GET"])
def validate_email_expired():
    # The resend route and splash.ts are anonymous-only, so an authenticated
    # visitor would get a dead shell (and a pointless re-mint).
    if current_user.is_authenticated:
        return redirect(url_for(ROUTES.UTUBS.HOME))

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

    safe_add_log(f"User={user_with_expired_token.id} email validation token reset")
    return (
        render_template(
            "pages/splash.html",
            email_token_is_expired=True,
            expired_token_message=EMAILS.TOKEN_EXPIRED,
            expired_resend_token=user_with_expired_token.get_resend_validation_token(),
        ),
        200,
        # The page embeds a resend token; keep it out of shared caches.
        {"Cache-Control": "no-store"},
    )


@splash.route("/validate/<string:token>", methods=["GET"])
def validate_email(token: str) -> WerkzeugResponse:
    return validate_email_for_user(token)


@splash.route("/confirm-email-change/<string:token>", methods=["GET"])
def confirm_email_change(token: str) -> WerkzeugResponse:
    """Anonymous confirm step of the Settings change-email flow: swaps the
    pending email into the live email column, then redirects to splash with a
    single outcome code. No decorators — the link is opened from the new inbox,
    possibly on another device, and never auto-logs the user in."""
    return confirm_email_change_for_user(token)


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
    status_codes={
        200: ForgotPasswordResponseSchema,
        400: ErrorResponse,
        429: ErrorResponse,
    },
)
@limiter.limit(SPLASH_AUTH_RATE_LIMIT, methods=["POST"])
def forgot_password(forgot_password_request: ForgotPasswordRequest) -> FlaskResponse:
    return send_forgot_password_email_to_user(forgot_password_request.email)


@splash.route("/oauth/google/login", methods=["GET"])
@no_authenticated_users_allowed
@api_route(
    ajax_required=False,
    tags=[OPEN_API.AUTH],
    description="Redirect to Google's OAuth consent screen. Dual-purpose: signs in a returning user or auto-registers a first-time user on successful callback.",
    status_codes={302: EmptyRedirectSchema},
)
def google_login() -> WerkzeugResponse:
    """Kicks off Google OAuth. Dual-purpose: sign-in for returning users, auto-registration for first-time users (see docstring on the callback)."""
    return initiate_google_login()


@splash.route("/oauth/google/callback", methods=["GET"])
@csrf.exempt
@api_route(
    query_schema=GoogleOAuthCallbackQuerySchema,
    ajax_required=False,
    tags=[OPEN_API.AUTH],
    description="Google's OAuth redirect target. Establishes a session for a returning user or creates a new account for a first-time user; for an authenticated session with a pending settings-link intent it completes account linking instead (providers share one callback URL between sign-in and linking). CSRF is not applicable here; Authlib's own state-parameter round-trip provides equivalent protection on this cross-origin GET.",
    status_codes={
        200: HtmlErrorPageSchema,
        302: EmptyRedirectSchema,
        400: ErrorResponse,
    },
)
def google_callback() -> WerkzeugResponse | str | FlaskResponse:
    """Dual-context callback: anonymous sessions sign in (or auto-register);
    authenticated sessions with a valid link intent link the provider (the
    service bounces authenticated sessions without one home, mirroring the
    removed `@no_authenticated_users_allowed` gate)."""
    return handle_google_callback()


@splash.route("/oauth/github/login", methods=["GET"])
@no_authenticated_users_allowed
@api_route(
    ajax_required=False,
    tags=[OPEN_API.AUTH],
    description="Redirect to GitHub's OAuth consent screen. Dual-purpose: signs in a returning user or auto-registers a first-time user on successful callback.",
    status_codes={302: EmptyRedirectSchema},
)
def github_login() -> WerkzeugResponse:
    """Kicks off GitHub OAuth. Dual-purpose: sign-in for returning users, auto-registration for first-time users (see docstring on the callback)."""
    return initiate_github_login()


@splash.route("/oauth/github/callback", methods=["GET"])
@csrf.exempt
@api_route(
    query_schema=GitHubOAuthCallbackQuerySchema,
    ajax_required=False,
    tags=[OPEN_API.AUTH],
    description="GitHub's OAuth redirect target. Establishes a session for a returning user or creates a new account for a first-time user; for an authenticated session with a pending settings-link intent it completes account linking instead (GitHub OAuth apps allow exactly one callback URL, shared between sign-in and linking). CSRF is not applicable here; Authlib's own state-parameter round-trip provides equivalent protection on this cross-origin GET.",
    status_codes={
        200: HtmlErrorPageSchema,
        302: EmptyRedirectSchema,
        400: ErrorResponse,
    },
)
def github_callback() -> WerkzeugResponse | str | FlaskResponse:
    """Dual-context callback: anonymous sessions sign in (or auto-register);
    authenticated sessions with a valid link intent link the provider (the
    service bounces authenticated sessions without one home, mirroring the
    removed `@no_authenticated_users_allowed` gate)."""
    return handle_github_callback()


@splash.route("/oauth/<string:provider>/link", methods=["GET"])
@email_validation_required
@api_route(
    ajax_required=False,
    tags=[OPEN_API.AUTH],
    description="Redirect an authenticated user to a provider's OAuth consent screen to link (or prove ownership for linking) that provider to their account. Requires a pending link intent stashed by POST /users/<id>/oauth/link/<provider>; without one, bounces back to Settings.",
    status_codes={302: EmptyRedirectSchema},
)
def oauth_link(provider: str) -> WerkzeugResponse:
    """Settings-link OAuth dance entry point (link target or proof provider,
    per the stashed intent)."""
    return initiate_link_oauth_redirect(provider)


@splash.route("/oauth/link/confirm", methods=["GET"])
@no_authenticated_users_allowed
def oauth_confirm_link_page() -> WerkzeugResponse | str:
    """Collision confirm-link page: an OAuth sign-in matched an existing
    account's email, so ask for a second proof of account ownership —
    password re-auth for password accounts, or a sign-in with an
    already-linked provider for password-less accounts — before linking."""
    return render_confirm_link_page()


@splash.route("/oauth/link/confirm", methods=["POST"])
@no_authenticated_users_allowed
@api_route(
    request_schema=ConfirmLinkRequest,
    response_schema=LoginRedirectResponseSchema,
    error_message=CONFIRM_LINK_INVALID_MESSAGE,
    error_code=OAuthLinkErrorCodes.INVALID_FORM_INPUT,
    ajax_required=False,
    tags=[OPEN_API.AUTH],
    description="Complete the collision confirm-link flow for a password account: verify the existing account's password, link the pending OAuth identity, and sign the user in.",
    status_codes={
        200: LoginRedirectResponseSchema,
        400: ErrorResponse,
        401: ErrorResponse,
        403: ErrorResponse,
    },
)
def oauth_confirm_link(confirm_link_request: ConfirmLinkRequest) -> FlaskResponse:
    """Password-account branch of the confirm-link flow (the password-less
    branch completes via a normal sign-in with an already-linked provider)."""
    return confirm_link_with_password(confirm_link_request.password)


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
