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
        is_email_validated: bool | None = session.get(EMAILS.EMAIL_VALIDATED_SESS_KEY)

        if is_email_validated is None:
            # TODO: Instead of 404'ing, redirect for users who don't validate in case they don't have a row... maybe?

            # This only works assuming Users are created in the same order as EmailValidations,
            # which is currently True, but risky assumption...
            # TODO: Either change EmailValidations PK to be the User's ID, or use a column in
            # the Users table to indicate whether the email is validated or not...
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
