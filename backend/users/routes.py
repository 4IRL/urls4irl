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

from backend import limiter, login_manager
from backend.api_common.auth_decorators import (
    email_validation_required,
    session_required,
)
from backend.api_common.parse_request import api_route
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.api_v1.services.tokens import decode_access_token
from backend.app_logger import warning_log
from backend.extensions.metrics.writer import record_event
from backend.metrics.events import EventName
from backend.models.users import Users
from backend.schemas.base import StatusMessageResponseSchema
from backend.schemas.errors import ErrorResponse, build_message_error_response
from backend.schemas.exports import UserDataExportResponseSchema
from backend.schemas.requests.users import (
    ChangeEmailRequest,
    ChangePasswordRequest,
    ChangeUsernameRequest,
    DeleteAccountRequest,
    ProviderLinkRequest,
)
from backend.schemas.users import (
    AccountRemovalResponseSchema,
    ChangeEmailResponseSchema,
    ChangePasswordResponseSchema,
    ChangeUsernameResponseSchema,
    LoginRedirectResponseSchema,
)
from backend.splash.constants import OAuthLinkErrorCodes
from backend.splash.services.oauth.linking_service import (
    build_connected_accounts_context,
    initiate_settings_link,
    unlink_provider,
)
from backend.users.constants import (
    DATA_EXPORT_RATE_LIMIT,
    ChangeEmailErrorCodes,
    ChangePasswordErrorCodes,
    ChangeUsernameErrorCodes,
    DataExportErrorCodes,
    DeleteAccountErrorCodes,
    LogoutEverywhereErrorCodes,
)
from backend.users.services.account_service import (
    apply_account_deletion,
    apply_email_change,
    apply_logout_everywhere,
    apply_password_change,
    apply_username_change,
    build_account_info_context,
)
from backend.users.services.data_export_service import build_user_data_export_core
from backend.users.services.stats_service import build_user_stats_context
from backend.utils.all_routes import ROUTES
from backend.utils.constants import provide_config_for_constants
from backend.utils.datetime_utils import utc_now
from backend.utils.strings.api_auth_strs import API_AUTH
from backend.utils.strings.email_validation_strs import EMAILS
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.oauth_strs import LINK_INVALID_PASSWORD_MESSAGE
from backend.utils.strings.openapi_strs import OPEN_API
from backend.utils.strings.user_strs import (
    DATA_EXPORT_SUCCESS,
    SESSION_ISSUED_AT_KEY,
    USER_FAILURE,
)

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
    return render_template(
        "pages/settings.html",
        is_settings=True,
        **build_connected_accounts_context(),
        **build_user_stats_context(),
        **build_account_info_context(),
    )


@users.route("/users/<int:user_id>/username", methods=["PUT"])
@email_validation_required
@api_route(
    request_schema=ChangeUsernameRequest,
    response_schema=ChangeUsernameResponseSchema,
    error_message=USER_FAILURE.INVALID_INPUT,
    error_code=ChangeUsernameErrorCodes.INVALID_FORM_INPUT,
    tags=[OPEN_API.AUTH],
    description="Change the authenticated user's username. Requires no password re-authentication (Decision #1), so OAuth-only accounts can rename. Rate-limited to a few changes per rolling 24h per user via a Redis-only counter; the cap returns HTTP 429.",
    status_codes={
        200: ChangeUsernameResponseSchema,
        400: ErrorResponse,
        403: ErrorResponse,
        429: ErrorResponse,
    },
)
def change_username(
    user_id: int, change_username_request: ChangeUsernameRequest
) -> FlaskResponse:
    """Applies the authenticated change-username flow (self-service only; the
    self-ownership/uniqueness/rate-limit policy is enforced in the service)."""
    return apply_username_change(
        user_id=user_id, new_username=change_username_request.username
    )


@users.route("/users/<int:user_id>/password", methods=["PUT"])
@email_validation_required
@api_route(
    request_schema=ChangePasswordRequest,
    response_schema=ChangePasswordResponseSchema,
    error_message=USER_FAILURE.INVALID_INPUT,
    error_code=ChangePasswordErrorCodes.INVALID_FORM_INPUT,
    tags=[OPEN_API.AUTH],
    description="Change the authenticated user's password. Requires the current password for re-authentication (Decision #9), and invalidates every OTHER session on success while the acting session survives (Decision #2). Not available for OAuth-only (password-less) accounts. A per-user brute-force lockout shared with the settings OAuth-link gate returns 429 after too many wrong-password attempts (DD-1).",
    status_codes={
        200: ChangePasswordResponseSchema,
        400: ErrorResponse,
        403: ErrorResponse,
        429: ErrorResponse,
    },
)
def change_password(
    user_id: int, change_password_request: ChangePasswordRequest
) -> FlaskResponse:
    """Applies the authenticated change-password flow (self-service only; the
    self-ownership / OAuth-only / re-auth policy is enforced in the service)."""
    return apply_password_change(
        user_id=user_id,
        current_password=change_password_request.password,
        new_password=change_password_request.new_password,
    )


@users.route("/users/<int:user_id>/email", methods=["PUT"])
@email_validation_required
@api_route(
    request_schema=ChangeEmailRequest,
    response_schema=ChangeEmailResponseSchema,
    error_message=USER_FAILURE.INVALID_INPUT,
    error_code=ChangeEmailErrorCodes.INVALID_FORM_INPUT,
    tags=[OPEN_API.AUTH],
    description="Start a change of the authenticated user's email (re-verification round-trip). Requires the current password for re-authentication and a matching confirm-email field. Stages the new address in pendingEmail and mails a confirmation link there; the live email is swapped only when that link is opened (GET /confirm-email-change/<token>). Not available for OAuth-only (password-less) accounts. Per-day send cap and a shared per-user brute-force lockout both return HTTP 429.",
    status_codes={
        200: ChangeEmailResponseSchema,
        400: ErrorResponse,
        403: ErrorResponse,
        429: ErrorResponse,
    },
)
def change_email(
    user_id: int, change_email_request: ChangeEmailRequest
) -> FlaskResponse:
    """Applies the authenticated change-email START flow (self-service only; the
    self-ownership / OAuth-only / re-auth / uniqueness / rate-limit policy is
    enforced in the service). The confirm step is the anonymous splash route."""
    return apply_email_change(
        user_id=user_id,
        new_email=change_email_request.new_email,
        current_password=change_email_request.password,
    )


@users.route("/users/<int:user_id>", methods=["DELETE"])
@email_validation_required
@api_route(
    request_schema=DeleteAccountRequest,
    response_schema=AccountRemovalResponseSchema,
    error_message=USER_FAILURE.INVALID_INPUT,
    error_code=DeleteAccountErrorCodes.INVALID_FORM_INPUT,
    tags=[OPEN_API.AUTH],
    description="Irreversibly delete (GDPR-erase) the authenticated account. Requires a typed-username confirmation matching the account username, plus the current password for re-authentication (password accounts). The Users row is tombstoned in place, PII child rows dropped, UTub memberships resolved (solo UTubs deleted, created-with-others transferred, non-creator memberships removed), and every session/refresh token revoked; the session is logged out and the splash redirect URL returned. OAuth-only (password-less) accounts re-prove identity via an OAuth-proof round-trip through an already-linked provider — the 200 response returns the provider redirect URL, and the authenticated callback completes the erasure. The last active admin is blocked (403). A per-user brute-force lockout shared with the change-password gate returns 429 after too many wrong-password attempts.",
    status_codes={
        200: AccountRemovalResponseSchema,
        400: ErrorResponse,
        403: ErrorResponse,
        429: ErrorResponse,
    },
)
def delete_account(
    user_id: int, delete_account_request: DeleteAccountRequest
) -> FlaskResponse:
    """Applies the irreversible self-delete flow (self-service only; the
    self-ownership / sole-admin / typed-confirmation / OAuth-only / re-auth policy
    is enforced in the service)."""
    return apply_account_deletion(
        user_id=user_id,
        current_password=delete_account_request.password,
        confirm_username=delete_account_request.confirm_username,
    )


@users.route("/users/<int:user_id>/logout-everywhere", methods=["POST"])
@session_required
@api_route(
    response_schema=AccountRemovalResponseSchema,
    error_code=LogoutEverywhereErrorCodes.NOT_AUTHORIZED,
    tags=[OPEN_API.AUTH],
    description="Sign the authenticated user out on every device (non-destructive). Bumps the per-user session kill-switch and revokes every refresh token, then logs the acting session out too (the current device is signed out along with the rest) and returns the splash redirect URL. Requires no re-authentication — logging back in restores access. Uses session auth only (no validated-email requirement), so a user with an unvalidated email can still sign out everywhere. Takes no request body.",
    status_codes={
        200: AccountRemovalResponseSchema,
        403: ErrorResponse,
    },
)
def logout_everywhere(user_id: int) -> FlaskResponse:
    """Signs the authenticated user out on all devices (self-service only; the
    self-ownership policy is enforced in the service). No request body, no
    re-auth (D-1); the acting session dies too (D-4)."""
    return apply_logout_everywhere(user_id=user_id)


@users.route("/users/<int:user_id>/data-export", methods=["GET"])
@session_required
@api_route(
    response_schema=UserDataExportResponseSchema,
    tags=[OPEN_API.AUTH],
    description="Export the authenticated user's own data (non-mutating read). Serializes every UTub the user belongs to — created and joined — with its URLs, applied tags, tag vocabulary, and members, plus the user's own account identity fields (never a password, session, or pending-email field). Returns the export nested under an `export` key so the client can save a clean JSON file. Gated by session auth only (no validated-email requirement), and self-scoped: a mismatched path user_id is rejected 403. Rate-limited to 5/minute, 15/hour per IP (the app's most expensive read), returning HTTP 429 when the cap is hit.",
    status_codes={
        200: UserDataExportResponseSchema,
        403: ErrorResponse,
        429: ErrorResponse,
    },
)
@limiter.limit(DATA_EXPORT_RATE_LIMIT, methods=["GET"])
def data_export(user_id: int) -> FlaskResponse:
    """Serialize and return the authenticated user's own data export
    (self-service only). The self-ownership guard rejects a mismatched path
    user_id with 403; on success the guard-free core walks every UTub the user
    belongs to and the ``DATA_EXPORTED`` domain metric is recorded before the
    envelope is returned."""
    if user_id != current_user.id:
        return build_message_error_response(
            message=USER_FAILURE.NOT_AUTHORIZED,
            error_code=DataExportErrorCodes.NOT_AUTHORIZED,
            status_code=403,
        )

    payload = build_user_data_export_core(user=current_user, generated_at=utc_now())
    record_event(EventName.DATA_EXPORTED)
    return APIResponse(
        status_code=200,
        data=UserDataExportResponseSchema(
            status=STD_JSON.SUCCESS,
            message=DATA_EXPORT_SUCCESS,
            export=payload,
        ),
    ).to_response()


@users.route("/users/<int:user_id>/oauth/link/<string:provider>", methods=["POST"])
@email_validation_required
@api_route(
    request_schema=ProviderLinkRequest,
    response_schema=LoginRedirectResponseSchema,
    error_message=LINK_INVALID_PASSWORD_MESSAGE,
    error_code=OAuthLinkErrorCodes.INVALID_FORM_INPUT,
    tags=[OPEN_API.AUTH],
    description="Start linking an OAuth provider to the authenticated user's account. Password accounts must re-authenticate with their password; password-less accounts are routed through an OAuth proof round-trip with an already-linked provider. Returns the redirect URL for the provider consent dance. A per-user brute-force lockout shared with the change-password gate returns 429 after too many wrong-password attempts (DD-1).",
    status_codes={
        200: LoginRedirectResponseSchema,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
        429: ErrorResponse,
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
