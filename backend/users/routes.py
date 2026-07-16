from flask import (
    Blueprint,
    Request,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, logout_user

from backend import login_manager
from backend.api_common.auth_decorators import email_validation_required
from backend.api_common.parse_request import api_route
from backend.api_common.responses import FlaskResponse
from backend.api_v1.services.tokens import decode_access_token
from backend.app_logger import warning_log
from backend.models.users import Users
from backend.schemas.base import StatusMessageResponseSchema
from backend.schemas.errors import ErrorResponse
from backend.schemas.requests.users import ProviderLinkRequest
from backend.schemas.users import LoginRedirectResponseSchema
from backend.splash.constants import OAuthLinkErrorCodes
from backend.splash.services.oauth.linking_service import (
    initiate_settings_link,
    unlink_provider,
)
from backend.utils.all_routes import ROUTES
from backend.utils.constants import provide_config_for_constants
from backend.utils.strings.api_auth_strs import API_AUTH
from backend.utils.strings.email_validation_strs import EMAILS
from backend.utils.strings.oauth_strs import LINK_INVALID_PASSWORD_MESSAGE
from backend.utils.strings.openapi_strs import OPEN_API
from backend.utils.strings.user_strs import SESSION_ISSUED_AT_KEY

users = Blueprint("users", __name__)


@login_manager.user_loader
def load_user(user_id) -> Users | None:
    """Resolve the session cookie's user, enforcing account-state gates.

    Returns None (anonymous) when the account is suspended, or when the
    session was issued before ``Users.sessionsInvalidatedAt`` — the admin
    portal's per-user web-session kill switch. A session with no issued-at
    stamp (predating the stamp mechanism) is rejected once any invalidation
    has been requested, which is the safe default.
    """
    user: Users | None = Users.query.get(int(user_id))
    if user is None:
        return None
    if user.is_suspended:
        return None
    if user.sessions_invalidated_at is not None:
        session_issued_at = session.get(SESSION_ISSUED_AT_KEY)
        if (
            session_issued_at is None
            or float(session_issued_at) < user.sessions_invalidated_at.timestamp()
        ):
            return None
    return user


@login_manager.request_loader
def load_user_from_request(incoming_request: Request) -> Users | None:
    """Authenticate `Authorization: Bearer <access JWT>` requests.

    Deliberately scoped to the /api/v1 surface: bearer tokens are never
    honored on web routes, so the session-cookie web app's auth behavior is
    provably untouched. Returns None (unauthenticated) on any failure —
    Flask-Login then falls back to the session cookie, if present.

    On success, stamps `g.api_bearer_authenticated = True` so
    `api_authentication_required` can verify the identity came from a bearer
    token. Flask-Login consults this loader only when session-cookie auth did
    not resolve a user, so a session-authenticated request never carries the
    stamp — keeping the CSRF-exempt /api/v1 surface bearer-only.
    """
    if not incoming_request.path.startswith(API_AUTH.API_V1_URL_PREFIX):
        return None

    authorization_header: str = incoming_request.headers.get(
        API_AUTH.AUTHORIZATION_HEADER, ""
    )
    if not authorization_header.startswith(API_AUTH.BEARER_PREFIX):
        return None

    bearer_token = authorization_header[len(API_AUTH.BEARER_PREFIX) :]
    bearer_user: Users | None = decode_access_token(token=bearer_token)
    if bearer_user is None:
        return None
    if bearer_user.is_suspended:
        # A still-unexpired access token dies immediately on suspension;
        # refresh tokens are bulk-revoked by the suspend action itself.
        return None
    setattr(g, API_AUTH.BEARER_AUTHENTICATED_G_KEY, True)
    return bearer_user


@login_manager.unauthorized_handler
def unauthorized():
    if not current_user.is_authenticated:

        if hasattr(current_user, "id"):
            warning_log(f"User={current_user.id} not authenticated")
        else:
            warning_log("User not authenticated")

        # TODO: Validate the full path here before attaching query param
        return redirect(url_for(ROUTES.SPLASH.SPLASH_PAGE, next=request.full_path))

    if current_user.is_authenticated and not current_user.email_validated:
        warning_log(f"User={current_user.id} authenticated but email not validated")
        return redirect(url_for(ROUTES.SPLASH.CONFIRM_EMAIL))


@users.route("/logout")
def logout():
    """Logs user out by clearing session details. Returns to login page."""
    logout_user()
    if EMAILS.EMAIL_VALIDATED_SESS_KEY in session.keys():
        session.pop(EMAILS.EMAIL_VALIDATED_SESS_KEY)
    return redirect(url_for(ROUTES.SPLASH.SPLASH_PAGE))


# TODO: Separate users context processor from home page context processor
@users.context_processor
def provide_constants():
    return provide_config_for_constants()


@users.route("/privacy-policy")
def privacy_policy():
    return render_template("pages/privacy_policy.html", is_privacy_or_terms=True)


@users.route("/terms")
def terms_and_conditions():
    return render_template("pages/terms_and_conditions.html", is_privacy_or_terms=True)


@users.route("/settings", methods=["GET"])
@email_validation_required
def settings() -> str:
    return render_template("pages/settings.html", is_settings=True)


@users.route("/users/<int:user_id>/oauth/link/<string:provider>", methods=["POST"])
@email_validation_required
@api_route(
    request_schema=ProviderLinkRequest,
    response_schema=LoginRedirectResponseSchema,
    error_message=LINK_INVALID_PASSWORD_MESSAGE,
    error_code=OAuthLinkErrorCodes.INVALID_FORM_INPUT,
    tags=[OPEN_API.AUTH],
    description="Start linking an OAuth provider to the authenticated user's account. Password accounts must re-authenticate with their password; password-less accounts are routed through an OAuth proof round-trip with an already-linked provider. Returns the redirect URL for the provider consent dance.",
    status_codes={
        200: LoginRedirectResponseSchema,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
)
def link_oauth_provider(
    user_id: int, provider: str, provider_link_request: ProviderLinkRequest
) -> FlaskResponse:
    """Initiates the settings-page link flow (self-service only; the DECIDED
    proof-of-ownership policy is enforced in the service)."""
    return initiate_settings_link(
        user_id=user_id,
        provider_key=provider,
        password=provider_link_request.password,
    )


@users.route("/users/<int:user_id>/oauth/link/<string:provider>", methods=["DELETE"])
@email_validation_required
@api_route(
    response_schema=StatusMessageResponseSchema,
    tags=[OPEN_API.AUTH],
    description="Disconnect an OAuth provider from the authenticated user's account. Blocked when it is the account's last remaining sign-in method (no password and a single linked identity).",
    status_codes={
        200: StatusMessageResponseSchema,
        403: ErrorResponse,
        404: ErrorResponse,
    },
)
def unlink_oauth_provider(user_id: int, provider: str) -> FlaskResponse:
    """Removes a linked identity, enforcing the last-sign-in-method guard
    (mirrors the admin portal's unlink guard)."""
    return unlink_provider(user_id=user_id, provider_key=provider)
