from flask import (
    Blueprint,
    redirect,
    url_for,
    session,
)
from flask_login import current_user, logout_user

from src import login_manager
from src.models import User
from src.utils import strings as U4I_STRINGS

users = Blueprint("users", __name__)

# Standard response for JSON messages
STD_JSON = U4I_STRINGS.STD_JSON_RESPONSE
USER_FAILURE = U4I_STRINGS.USER_FAILURE
USER_SUCCESS = U4I_STRINGS.USER_SUCCESS
EMAILS = U4I_STRINGS.EMAILS
EMAILS_FAILURE = U4I_STRINGS.EMAILS_FAILURE
RESET_PASSWORD = U4I_STRINGS.RESET_PASSWORD
FORGOT_PASSWORD = U4I_STRINGS.FORGOT_PASSWORD


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
