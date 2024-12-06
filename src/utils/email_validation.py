from flask import session, url_for, redirect
from flask_login import login_required, current_user
from functools import wraps

from src.models.email_validations import Email_Validations
from src.utils.all_routes import ROUTES
from src.utils.strings.email_validation_strs import EMAILS


def email_validation_required(func):
    @wraps(func)
    @login_required
    def decorated_view(*args, **kwargs):
        current_user_id = current_user.get_id()
        is_email_validated: bool = session.get(EMAILS.EMAIL_VALIDATED_SESS_KEY)

        if is_email_validated is None:
            # TODO: Instead of 404'ing, redirect for users who don't validate in case they don't have a row... maybe?
            current_user_email_validation: Email_Validations = (
                Email_Validations.query.get_or_404(current_user_id)
            )
            session[EMAILS.EMAIL_VALIDATED_SESS_KEY] = (
                current_user_email_validation.is_validated
            )
            is_email_validated = session[EMAILS.EMAIL_VALIDATED_SESS_KEY]

        if not is_email_validated:
            return redirect(url_for(ROUTES.SPLASH.SPLASH_PAGE))
        return func(*args, **kwargs)

    return decorated_view
