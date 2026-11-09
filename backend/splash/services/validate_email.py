from datetime import datetime

import jwt
import requests
from flask import abort, current_app, redirect, session, url_for
from flask_login import current_user, login_user
from jwt import exceptions as JWTExceptions
from werkzeug import Response as WerkzeugResponse

from backend import db
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.app_logger import critical_log, error_log, safe_add_log, warning_log
from backend.extensions.extension_utils import (
    safe_get_email_sender,
    safe_get_notif_sender,
)
from backend.extensions.metrics.writer import record_event
from backend.metrics.events import EventName
from backend.models.email_validations import Email_Validations
from backend.models.users import Users
from backend.schemas.errors import build_message_error_response
from backend.splash.constants import EmailValidationErrorCodes
from backend.splash.utils import decode_resend_validation_token, verify_token
from backend.utils.all_routes import ROUTES
from backend.utils.constants import EMAIL_CONSTANTS
from backend.utils.datetime_utils import utc_now
from backend.utils.mailjet_utils import handle_mailjet_failure
from backend.utils.strings.config_strs import CONFIG_ENVS
from backend.utils.strings.email_validation_strs import EMAILS, EMAILS_FAILURE
from backend.utils.strings.user_strs import MEMBER_SUCCESS


def _send_account_confirmation_email(
    user: Users, email_validation: Email_Validations
) -> requests.Response:
    """Send the account-confirmation email for a given user, session-independently.

    The register and resend paths share this so they can send the same email
    without depending on `current_user`. The caller owns the
    attempt-count/rate-limit guarding; this only builds the link and sends.

    Args:
        user (Users): The account the confirmation email is for
        email_validation (Email_Validations): That account's Email_Validations row

    Returns:
        (requests.Response): The raw Mailjet response
    """
    email_sender = safe_get_email_sender(current_app)
    if not email_sender.is_production() and not email_sender.is_testing():
        _log_email_send_if_in_development(email_validation)

    url_for_confirmation = url_for(
        ROUTES.SPLASH.VALIDATE_EMAIL,
        token=email_validation.validation_token,
        _external=True,
    )

    return email_sender.send_account_email_confirmation(
        user.email, user.username, url_for_confirmation
    )


def _validation_token_needs_refresh(stored_token: str) -> bool:
    """True when the stored validation token is expired, undecodable or within
    the refresh margin of expiry."""
    try:
        payload = jwt.decode(
            jwt=stored_token,
            key=current_app.config[CONFIG_ENVS.SECRET_KEY],
            algorithms=[EMAILS.ALGORITHM],
        )
    except JWTExceptions.PyJWTError:
        return True

    expiration = payload.get(EMAILS.EXPIRATION)
    if not isinstance(expiration, (int, float)):
        return True

    seconds_left = expiration - datetime.timestamp(utc_now())
    return seconds_left < EMAIL_CONSTANTS.VALIDATION_TOKEN_REFRESH_MARGIN_SECONDS


def _guard_and_send_confirmation_email(
    user: Users,
    email_validation: Email_Validations,
    log_context: str,
    refresh_token: bool = False,
) -> None:
    """Gate the confirmation-email send behind the per-account attempt guard,
    then send and log-only on a Mailjet server failure (>= 500).

    Single source of truth for the rate-limited confirmation-email send used by
    register branch 3 (email taken, unvalidated) and the resend endpoint. A
    skipped (rate-limited) send is deliberately indistinguishable from a
    completed one — every caller returns the same uniform opaque success — and a
    >= 500 Mailjet failure is logged rather than surfaced so the taken-vs-new
    enumeration signal never re-leaks.

    Args:
        user (Users): The account the confirmation email is for
        email_validation (Email_Validations): That account's Email_Validations row
        log_context (str): Phrase identifying the caller in the >= 500 error log
        refresh_token (bool): When True, re-mint the stored validation token if
            it is expired or near expiry, after the guard passes and before the send
    """
    if email_validation.has_too_many_email_attempts():
        return

    has_more_attempts = email_validation.increment_attempt()
    db.session.commit()

    if not has_more_attempts:
        return

    if refresh_token and _validation_token_needs_refresh(
        email_validation.validation_token
    ):
        email_validation.validation_token = user.get_email_validation_token()
        db.session.commit()

    _send_confirmation_email_and_log(user, email_validation, log_context)


def _send_confirmation_email_and_log(
    user: Users, email_validation: Email_Validations, log_context: str
) -> None:
    """Send the confirmation email and, on a Mailjet server failure (>= 500),
    log only — never surface a distinguishing error response (that would re-leak
    the taken-vs-new signal). Mirrors `/forgot-password`'s logging pattern.

    Args:
        user (Users): The account the confirmation email is for
        email_validation (Email_Validations): That account's Email_Validations row
        log_context (str): Phrase identifying the caller in the >= 500 error log
    """
    email_send_result = _send_account_confirmation_email(user, email_validation)
    if email_send_result.status_code >= 500:
        error_log(f"(4) Email failed to send: {log_context} for User={user.id}")


def send_resend_registration_email(email: str) -> FlaskResponse:
    """Resend the account-confirmation email for a pending registration, opaquely.

    Modeled on `send_forgot_password_email_to_user()`: every path — unknown
    email, already-validated account, pending account, or a rate-limited
    pending account — returns one identical opaque success so a caller cannot
    learn whether the email is registered or its validation state.

    Args:
        email (str): Email address from the resend request

    Returns:
        (FlaskResponse): JSON and HTTP status code (always the opaque success)
    """
    user: Users | None = Users.query.filter(Users.email == email.lower()).first()
    return _resend_confirmation_if_pending(user, "registration confirmation resend")


def send_resend_validation_email_for_token(token: str) -> FlaskResponse:
    """Resend the account-confirmation email for the account a resend token names.

    Same opaque outcome as the email-keyed path for every token problem.

    Args:
        token (str): The resend token from a login on an unconfirmed account

    Returns:
        (FlaskResponse): JSON and HTTP status code (always the opaque success)
    """
    user = decode_resend_validation_token(token)
    return _resend_confirmation_if_pending(user, "resend token confirmation resend")


def _resend_confirmation_if_pending(
    user: Users | None, log_context: str
) -> FlaskResponse:
    """Shared tail of both resend paths: send only for a pending account."""
    if user is None or user.email_validated or user.email_confirm is None:
        return _build_opaque_resend_success()

    _guard_and_send_confirmation_email(
        user, user.email_confirm, log_context, refresh_token=True
    )

    return _build_opaque_resend_success()


def _build_opaque_resend_success() -> FlaskResponse:
    """The single, uniform opaque success returned on every resend outcome."""
    return APIResponse(message=MEMBER_SUCCESS.CONFIRM_EMAIL_SENT).to_response()


def build_response_for_max_email_attempts_sent() -> FlaskResponse:
    """
    Builds a response when the User has sent too many email attempts.
    The attempts reset after a given amount of time - this is told to the user.

    Response:
        (FlaskResponse): JSON data and HTTP status code
    """
    warning_log(
        f"User {current_user.id} hit max attempts on email validation, wait 1 hr"
    )
    return build_message_error_response(
        message=EMAILS_FAILURE.TOO_MANY_ATTEMPTS_MAX,
        error_code=EmailValidationErrorCodes.MAX_TOTAL_EMAIL_VALIDATION_ATTEMPTS,
        status_code=429,
    )


def build_response_for_email_attempts_rate_limited(
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

    return build_message_error_response(
        message=f"{leftover_attempts}{EMAILS_FAILURE.TOO_MANY_ATTEMPTS}",
        error_code=EmailValidationErrorCodes.MAX_TIME_EMAIL_VALIDATION_ATTEMPTS,
        status_code=429,
    )


def _log_email_send_if_in_development(email_validation: Email_Validations):
    print(
        f"Sending this to the user's email:\n{url_for(ROUTES.SPLASH.VALIDATE_EMAIL, token=email_validation.validation_token, _external=True)}",
        flush=True,
    )


def handle_email_sending_result(email_result: requests.Response) -> FlaskResponse:
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

        return build_message_error_response(
            message=f"{EMAILS.EMAIL_FAILED} | {errors}",
            error_code=EmailValidationErrorCodes.EMAIL_SEND_FAILURE,
            status_code=400,
        )

    return handle_mailjet_failure(
        email_result, error_code=EmailValidationErrorCodes.MAILJET_SERVER_FAILURE
    )


def validate_email_for_user(token: str) -> WerkzeugResponse:
    """
    Handles validating a user's email based on the JWT provided in the URL.

    On success, logs the user in and redirects them to their pending invite page
    if one is stored, else their home page.

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

    Redirects the user to the invite page stored on their Email_Validations row
    (if any), else to their home page. It never joins the user to a UTub: only
    the invite page's explicit Join POST does.

    Args:
        user (Users): The newly validated User
        email_validation (Email_Validations): The Email_Validations object associated with the User

    Returns:
        (WerkzeugResponse): The redirect to the pending invite page or home page

    """
    # Read the reference before the delete/commit, which remove and expire the row
    pending_token: str | None = (
        email_validation.pending_invite.token
        if email_validation.pending_invite is not None
        else None
    )

    user.validate_email()
    db.session.delete(email_validation)
    db.session.commit()

    record_event(EventName.EMAIL_VERIFIED)

    login_user(user)
    session[EMAILS.EMAIL_VALIDATED_SESS_KEY] = True

    safe_add_log(f"User={user.id} email has been validated")

    notification_sender = safe_get_notif_sender(current_app)
    notification_sender.send_notification(f"Welcome! New user: {user.username}")
    if pending_token is not None:
        return redirect(url_for(ROUTES.INVITE_LINKS.INVITE_PAGE, token=pending_token))
    return redirect(url_for(ROUTES.UTUBS.HOME))
