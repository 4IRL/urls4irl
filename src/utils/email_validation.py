from flask import session, url_for, redirect
from flask_login import login_required, current_user
from functools import wraps

from src.utils.all_routes import ROUTES
from src.utils.strings.email_validation_strs import EMAILS


def email_validation_required(func):
    @wraps(func)
    @login_required
    def decorated_view(*args, **kwargs):
        is_email_validated: bool | None = session.get(EMAILS.EMAIL_VALIDATED_SESS_KEY)

        if is_email_validated is None:
            session[EMAILS.EMAIL_VALIDATED_SESS_KEY] = current_user.email_validated
            is_email_validated = session[EMAILS.EMAIL_VALIDATED_SESS_KEY]

        if not is_email_validated:
            return redirect(url_for(ROUTES.SPLASH.SPLASH_PAGE))
        return func(*args, **kwargs)

    return decorated_view
