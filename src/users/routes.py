from flask import (
    Blueprint,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, logout_user

from src import login_manager
from src.app_logger import warning_log
from src.models.users import Users
from src.utils.all_routes import ROUTES
from src.utils.constants import provide_config_for_constants
from src.utils.strings.email_validation_strs import EMAILS

users = Blueprint("users", __name__)


@login_manager.user_loader
def load_user(user_id) -> Users:
    return Users.query.get(int(user_id))


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
