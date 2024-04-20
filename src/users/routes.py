from flask import (
    Blueprint,
    redirect,
    url_for,
    session,
)
from flask_login import current_user, logout_user

from src import login_manager
from src.models import User
from src.utils.all_routes import ROUTES
from src.utils.strings.email_validation_strs import EMAILS

users = Blueprint("users", __name__)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@login_manager.unauthorized_handler
def unauthorized():
    if not current_user.is_authenticated:
        return redirect(url_for(ROUTES.SPLASH.SPLASH_PAGE))
    if current_user.is_authenticated and not current_user.email_confirm.is_validated:
        return redirect(url_for(ROUTES.SPLASH.CONFIRM_EMAIL))


@users.route("/logout")
def logout():
    """Logs user out by clearing session details. Returns to login page."""
    logout_user()
    if EMAILS.EMAIL_VALIDATED_SESS_KEY in session.keys():
        session.pop(EMAILS.EMAIL_VALIDATED_SESS_KEY)
    return redirect(url_for(ROUTES.SPLASH.SPLASH_PAGE))
