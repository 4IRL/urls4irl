from flask import (
    Blueprint,
    redirect,
    url_for,
    session,
)
from flask_login import current_user, logout_user

from src import login_manager
from src.models import User
from src.utils.strings.email_validation_strs import EMAILS, EMAILS_FAILURE
from src.utils.strings.json_strs import STD_JSON_RESPONSE
from src.utils.strings.reset_password_strs import FORGOT_PASSWORD, RESET_PASSWORD
from src.utils.strings.user_strs import USER_SUCCESS, USER_FAILURE

users = Blueprint("users", __name__)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@login_manager.unauthorized_handler
def unauthorized():
    if not current_user.is_authenticated:
        return redirect(url_for("splash.splash_page"))
    if current_user.is_authenticated and not current_user.email_confirm.is_validated:
        return redirect(url_for("splash.confirm_email_after_register"))


@users.route("/logout")
def logout():
    """Logs user out by clearing session details. Returns to login page."""
    logout_user()
    if EMAILS.EMAIL_VALIDATED_SESS_KEY in session.keys():
        session.pop(EMAILS.EMAIL_VALIDATED_SESS_KEY)
    return redirect(url_for("splash.splash_page"))
