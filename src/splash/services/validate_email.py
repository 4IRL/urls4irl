from flask import abort, current_app, redirect, session, url_for
from flask_login import current_user, login_user
import requests
from werkzeug import Response as WerkzeugResponse

from src import db
from src.api_common.responses import APIResponse, FlaskResponse
from src.app_logger import critical_log, error_log, safe_add_log, warning_log
from src.extensions.extension_utils import safe_get_email_sender, safe_get_notif_sender
from src.models.email_validations import Email_Validations
from src.models.users import Users
from src.splash.constants import EmailValidationErrorCodes
from src.splash.utils import verify_token
from src.utils.all_routes import ROUTES
from src.utils.constants import EMAIL_CONSTANTS
from src.utils.mailjet_utils import handle_mailjet_failure
from src.utils.strings.email_validation_strs import EMAILS, EMAILS_FAILURE


def send_validation_email_to_user() -> WerkzeugResponse | FlaskResponse:
    """
    Handles sending a validation email to the User to verify their email.

    If the user is already email validated, their email validation would have been deleted.

    Users can only send so many email in the span of one hour.

    Returns:
        (WerkzeugResponse): A URL redirect
        (FlaskResponse): Contains JSON and HTTP status code
    """
    current_email_validation: Email_Validations = Email_Validations.query.filter(
        Email_Validations.user_id == current_user.id
    ).first_or_404()

    if current_user.email_validated:
        warning_log(f"User {current_user.id} email already validated")
        db.session.delete(current_email_validation)
        db.session.commit()

        return redirect(url_for(ROUTES.UTUBS.HOME))

    if current_email_validation.has_too_many_email_attempts():
        return _build_response_for_max_email_attempts_sent()

    has_more_attempts = current_email_validation.increment_attempt()
    db.session.commit()

    if not has_more_attempts:
        return _build_response_for_email_attempts_rate_limited(current_email_validation)

    email_sender = safe_get_email_sender(current_app)
    if not email_sender.is_production() and not email_sender.is_testing():
        _log_email_send_if_in_development(current_email_validation)

    url_for_confirmation = url_for(
        ROUTES.SPLASH.VALIDATE_EMAIL,
        token=current_email_validation.validation_token,
        _external=True,
    )

    email_send_result = email_sender.send_account_email_confirmation(
        current_user.email, current_user.username, url_for_confirmation
    )

    return _handle_email_sending_result(email_send_result)


def _build_response_for_max_email_attempts_sent() -> FlaskResponse:
    """
    Builds a response when the User has sent too many email attempts.
    The attempts reset after a given amount of time - this is told to the user.

    Response:
        (FlaskResponse): JSON data and HTTP status code
    """
    warning_log(
        f"User {current_user.id} hit max attempts on email validation, wait 1 hr"
    )
    return APIResponse(
        status_code=429,
        message=EMAILS_FAILURE.TOO_MANY_ATTEMPTS_MAX,
        error_code=EmailValidationErrorCodes.MAX_TOTAL_EMAIL_VALIDATION_ATTEMPTS,
    ).to_response()


def _build_response_for_email_attempts_rate_limited(
    email_validation: Email_Validations,
) -> FlaskResponse:
    """
    Builds a response when the User sends too many email attempts within given time limits.

    Response:
        (FlaskResponse): JSON data and HTTP status code
    """
    warning_log(f"User {current_user.id} rate limited on email validation within 1 hr")
    leftover_attempts = str(
        EMAIL_CONSTANTS.MAX_EMAIL_ATTEMPTS_IN_HOUR - email_validation.attempts
    )

    return APIResponse(
        status_code=429,
        error_code=EmailValidationErrorCodes.MAX_TIME_EMAIL_VALIDATION_ATTEMPTS,
        message=f"{leftover_attempts}{EMAILS_FAILURE.TOO_MANY_ATTEMPTS}",
    ).to_response()


def _log_email_send_if_in_development(email_validation: Email_Validations):
    print(
        f"Sending this to the user's email:\n{url_for(ROUTES.SPLASH.VALIDATE_EMAIL, token=email_validation.validation_token, _external=True)}",
        flush=True,
    )


def _handle_email_sending_result(email_result: requests.Response) -> FlaskResponse:
    """
    Handles using the Mailjet service to send an email to the User.

    The Mailjet service may succeed or fail, which is handled.

    Args:
        email_result (requests.Response): The Mailjet Response after sending an email

    Response:
        (FlaskResponse): JSON data and HTTP status code
    """
    status_code: int = email_result.status_code
    json_response: dict = email_result.json()

    if status_code == 200:
        safe_add_log("Successfully sent email through Mailjet")
        return APIResponse(message=EMAILS.EMAIL_SENT).to_response()

    elif status_code < 500:
        message = json_response.get(EMAILS.MESSAGES, EMAILS.ERROR_WITH_MAILJET)
        if message == EMAILS.ERROR_WITH_MAILJET or type(message) is not list:
            errors = message
        else:
            errors = message[0].get(EMAILS.MAILJET_ERRORS, EMAILS.ERROR_WITH_MAILJET)

        error_log(f"(3) Email failed to send: {errors}")

        return APIResponse(
            status_code=400,
            message=f"{EMAILS.EMAIL_FAILED} | {errors}",
            error_code=EmailValidationErrorCodes.EMAIL_SEND_FAILURE,
        ).to_response()

    return handle_mailjet_failure(
        email_result, error_code=EmailValidationErrorCodes.MAILJET_SERVER_FAILURE
    )


def validate_email_for_user(token: str) -> WerkzeugResponse:
    """
    Handles validating a user's email based on the JWT provided in the URL.

    On success, logs the user in and redirects them to their home page.

    Args:
        token (str): The JWT included in the URL

    Response:
        (WerkzeugResponse): Next destination based on success/failure of token validation
    """

    verify_token_response = verify_token(token, EMAILS.VALIDATE_EMAIL)

    if verify_token_response.is_expired:
        return redirect(url_for("splash.validate_email_expired", token=token))

    if not verify_token_response.user or verify_token_response.failed_due_to_exception:
        # Link is invalid, so remove any users and email validation rows associated with this token
        _handle_invalid_verification_token(token)
        abort(404)

    user_to_validate = verify_token_response.user
    email_validation: Email_Validations = user_to_validate.email_confirm

    if not email_validation.validation_token == token:
        critical_log(f"Token did not match with user for User={user_to_validate.id}")
        abort(404)

    return _welcome_validated_email_new_user(user_to_validate, email_validation)


def _handle_invalid_verification_token(token: str):
    """
    Handles an invalid token, or an exception during token validation.

    Deletes all associated users and their associated Email Validation objects.

    Args:
        token (str): The JWT in the URL to validate their email
    """
    warning_log("Invalid user derived from token")
    invalid_emails = Email_Validations.query.filter(
        Email_Validations.validation_token == token
    ).all()
    if invalid_emails is not None:
        for invalid_email in invalid_emails:
            user_of_invalid_email = invalid_email.user
            db.session.delete(user_of_invalid_email)
            db.session.delete(invalid_email)
        db.session.commit()


def _welcome_validated_email_new_user(
    user: Users, email_validation: Email_Validations
) -> WerkzeugResponse:
    """
    Handles a user with a newly validated email, their final step in registering for U4I.

    Redirects the user to their home page.

    Args:
        user (Users): The newly validated User
        email_validation (Email_Validations): The Email_Validations object associated with the User

    Returns:
        (WerkzeugResponse): The redirect to their home page

    """
    user.validate_email()
    db.session.delete(email_validation)
    db.session.commit()

    login_user(user)
    session[EMAILS.EMAIL_VALIDATED_SESS_KEY] = True

    safe_add_log(f"User={user.id} email has been validated")

    notification_sender = safe_get_notif_sender(current_app)
    notification_sender.send_notification(f"Welcome! New user: {user.username}")
    return redirect(url_for(ROUTES.UTUBS.HOME))
