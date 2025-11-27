from flask import current_app, url_for
from flask_login import current_user
from requests import Response
from src import db
from src.api_common.responses import APIResponse, FlaskResponse
from src.app_logger import critical_log, safe_add_log, warning_log
from src.extensions.extension_utils import safe_get_email_sender
from src.models.forgot_passwords import Forgot_Passwords
from src.models.users import Users
from src.splash.forms import ForgotPasswordForm
from src.splash.services.validate_email import handle_mailjet_failure
from src.utils.all_routes import ROUTES
from src.utils.datetime_utils import utc_now
from src.utils.strings.reset_password_strs import FORGOT_PASSWORD
from src.utils.strings.user_strs import USER_FAILURE


def handle_invalid_forgot_password_form_input(
    forgot_password_form: ForgotPasswordForm,
) -> FlaskResponse:
    if forgot_password_form.errors is not None:
        warning_log("Invalid form for forgotten password")
        return APIResponse(
            status_code=401,
            message=FORGOT_PASSWORD.INVALID_EMAIL,
            error_code=1,
            errors=forgot_password_form.errors,
        ).to_response()

    critical_log(f"User={current_user.id} unable to handle forgotten password")
    return APIResponse(
        status_code=404, message=USER_FAILURE.SOMETHING_WENT_WRONG, error_code=2
    ).to_response()


def send_forgot_password_email_to_user(
    forgot_password_form: ForgotPasswordForm,
) -> FlaskResponse:
    """
    Handles sending a forgot password email to the User using Mailjet, but only if all
    requirements are met.

    Regardless of if requirements are met, the response to the User will indicate success. This is to avoid indicating to malicious actors whether or not an email exists in the database.

    Args:
        forgot_password_form (ForgotPasswordForm): Form with forgot password information

    Returns:
        (FlaskResponse): JSON and HTTP status code
    """
    user_with_email: Users = Users.query.filter(
        Users.email == forgot_password_form.get_email().lower()
    ).first()

    if not user_with_email:
        return APIResponse(
            message=FORGOT_PASSWORD.EMAIL_SENT_MESSAGE,
        ).to_response()

    if not user_with_email.email_validated:
        warning_log(
            f"User={user_with_email.id} forgot password but not email validated"
        )
        return APIResponse(
            message=FORGOT_PASSWORD.EMAIL_SENT_MESSAGE,
        ).to_response()

    # Check if user has already tried to reset their password before
    prev_forgot_password: Forgot_Passwords = user_with_email.forgot_password
    forgot_password_obj = _create_or_reset_forgot_password_object_for_user(
        user_with_email, prev_forgot_password
    )

    if forgot_password_obj.is_not_rate_limited():
        email_send_result = _send_forgot_password_email(
            forgot_password_obj, forgot_password_form, user_with_email
        )
        if email_send_result.status_code >= 500:
            return handle_mailjet_failure(email_send_result, error_code=3)

        safe_add_log(f"Sending password reset email for User={user_with_email.id}")

    return APIResponse(
        message=FORGOT_PASSWORD.EMAIL_SENT_MESSAGE,
    ).to_response()


def _create_or_reset_forgot_password_object_for_user(
    user: Users, forgot_password: Forgot_Passwords | None
) -> Forgot_Passwords:
    """
    Creates or resets the ForgotPassword object for the User.
    Resets it only if the User is not rate limited and is passed the time limit.

    Args:
        user (Users): The User with the forgotten password
        forgot_password (Forgot_Passwords): The associated Forgot_Passwords object

    Returns:
        (Forgot_Passwords): The associated Forgot_Passwords object
    """
    if forgot_password and (
        forgot_password.is_not_rate_limited()
        and forgot_password.is_more_than_hour_old()
    ):
        forgot_password.attempts = 0
        forgot_password.reset_token = user.get_password_reset_token()
        forgot_password.initial_attempt = utc_now()
        db.session.commit()

    else:
        new_token = user.get_password_reset_token()
        forgot_password = Forgot_Passwords(reset_token=new_token)
        user.forgot_password = forgot_password
        db.session.add(forgot_password)
        db.session.commit()

    return forgot_password


def _send_forgot_password_email(
    forgot_password_obj: Forgot_Passwords,
    forgot_password_form: ForgotPasswordForm,
    user: Users,
) -> Response:
    """
    Handles sending the forgot password email to the User via Mailjet.

    Args:
        forgot_password_obj (Forgot_Passwords): The Forgot_Passwords object associated with the User
        forgot_password_form (ForgotPasswordForm): The form with associated forgotten password data
        user (Users): The User with forgotten password

    Returns:
        (Response): The response from Mailjet after sending the Forgot Password email
    """

    forgot_password_obj.increment_attempts()
    db.session.commit()

    email_sender = safe_get_email_sender(current_app)
    if not email_sender.is_production() and not email_sender.is_testing():
        print(
            f"Sending this to the user's email:\n{url_for(ROUTES.SPLASH.RESET_PASSWORD, token=forgot_password_obj.reset_token, _external=True)}",
            flush=True,
        )
    url_for_reset = url_for(
        ROUTES.SPLASH.RESET_PASSWORD,
        token=forgot_password_obj.reset_token,
        _external=True,
    )
    email_send_result = email_sender.send_password_reset_email(
        forgot_password_form.get_email(),
        user.username,
        url_for_reset,
    )

    return email_send_result
