from flask import (
    Blueprint,
    Request,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, logout_user

from backend import login_manager
from backend.api_common.auth_decorators import email_validation_required
from backend.api_v1.services.tokens import decode_access_token
from backend.app_logger import warning_log
from backend.models.users import Users
from backend.utils.all_routes import ROUTES
from backend.utils.constants import provide_config_for_constants
from backend.utils.strings.api_auth_strs import API_AUTH
from backend.utils.strings.email_validation_strs import EMAILS

users = Blueprint("users", __name__)


@login_manager.user_loader
def load_user(user_id) -> Users:
    return Users.query.get(int(user_id))


@login_manager.request_loader
def load_user_from_request(incoming_request: Request) -> Users | None:
    """Authenticate `Authorization: Bearer <access JWT>` requests.

    Deliberately scoped to the /api/v1 surface: bearer tokens are never
    honored on web routes, so the session-cookie web app's auth behavior is
    provably untouched. Returns None (unauthenticated) on any failure —
    Flask-Login then falls back to the session cookie, if present.
    """
    if not incoming_request.path.startswith(API_AUTH.API_V1_URL_PREFIX):
        return None

    authorization_header: str = incoming_request.headers.get(
        API_AUTH.AUTHORIZATION_HEADER, ""
    )
    if not authorization_header.startswith(API_AUTH.BEARER_PREFIX):
        return None

    bearer_token = authorization_header[len(API_AUTH.BEARER_PREFIX) :]
    return decode_access_token(token=bearer_token)


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
