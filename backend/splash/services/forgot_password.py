from flask import current_app, url_for
from requests import Response
from backend import db
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.app_logger import safe_add_log, warning_log
from backend.extensions.extension_utils import safe_get_email_sender
from backend.models.forgot_passwords import Forgot_Passwords
from backend.models.users import Users
from backend.splash.constants import ForgotPasswordErrorCodes
from backend.utils.all_routes import ROUTES
from backend.utils.datetime_utils import utc_now
from backend.utils.mailjet_utils import handle_mailjet_failure
from backend.utils.strings.reset_password_strs import FORGOT_PASSWORD


def send_forgot_password_email_to_user(
    email: str,
) -> FlaskResponse:
    """
    Handles sending a forgot password email to the User using Mailjet, but only if all
    requirements are met.

    Regardless of if requirements are met, the response to the User will indicate success. This is to avoid indicating to malicious actors whether or not an email exists in the database.

    Args:
        email (str): Email address from the forgot password request

    Returns:
        (FlaskResponse): JSON and HTTP status code
    """
    user_with_email: Users = Users.query.filter(Users.email == email.lower()).first()

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
            forgot_password_obj, email, user_with_email
        )
        if email_send_result.status_code >= 500:
            return handle_mailjet_failure(
                email_send_result,
                error_code=ForgotPasswordErrorCodes.EMAIL_SEND_FAILURE,
            )

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

    if not forgot_password:
        new_token = user.get_password_reset_token()
        forgot_password = Forgot_Passwords(reset_token=new_token)
        user.forgot_password = forgot_password
        db.session.add(forgot_password)
        db.session.commit()

    return forgot_password


def _send_forgot_password_email(
    forgot_password_obj: Forgot_Passwords,
    email: str,
    user: Users,
) -> Response:
    """
    Handles sending the forgot password email to the User via Mailjet.

    Args:
        forgot_password_obj (Forgot_Passwords): The Forgot_Passwords object associated with the User
        email (str): The email address for the forgot password request
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
        email.lower(),
        user.username,
        url_for_reset,
    )

    return email_send_result
