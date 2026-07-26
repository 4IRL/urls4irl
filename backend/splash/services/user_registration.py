from backend import db
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.app_logger import error_log, safe_add_log, warning_log
from backend.extensions.metrics.writer import record_event
from backend.metrics.events import EventName
from backend.models.email_validations import Email_Validations
from backend.models.users import Users
from backend.schemas.errors import build_field_error_response
from backend.splash.constants import RegisterErrorCodes
from backend.splash.services.validate_email import _send_account_confirmation_email
from backend.utils.strings.splash_form_strs import REGISTER_LOGIN_FORM
from backend.utils.strings.user_strs import MEMBER_SUCCESS, USER_FAILURE


def register_new_user(username: str, email: str, password: str) -> FlaskResponse:
    """
    Registers a new user while keeping every email-axis outcome opaque.

    Username-taken remains a field error (usernames are inherently enumerable),
    but the email axis (new / already-registered-validated /
    already-registered-unvalidated) always returns one identical "check your
    email" success so a caller cannot learn whether an email is registered.

    Args:
        username: The requested username
        email: The requested email
        password: The plaintext password

    Returns:
        FlaskResponse: JSON response indicating success or failure
    """
    email_user: Users | None = Users.query.filter(Users.email == email.lower()).first()

    username_user: Users | None = Users.query.filter(Users.username == username).first()

    # Branch 1: username taken (validated). A hard, accepted enumeration signal.
    # Username precedence: a taken username short-circuits before the email axis
    # is ever reflected in the response body, though the email-taken metric is
    # still recorded internally when both axes are taken.
    if username_user and username_user.email_validated:
        warning_log("Form errors when registering")
        record_event(
            EventName.REGISTER_REJECTED,
            dimensions={"reason": "username_taken"},
        )
        if email_user and email_user.email_validated:
            record_event(
                EventName.REGISTER_REJECTED,
                dimensions={"reason": "email_taken"},
            )
        return build_field_error_response(
            message=USER_FAILURE.UNABLE_TO_REGISTER,
            errors={REGISTER_LOGIN_FORM.USERNAME: [USER_FAILURE.USERNAME_TAKEN]},
            error_code=RegisterErrorCodes.INVALID_FORM_INPUT,
        )

    # Branch 2: email taken, validated. Send no email — return opaque success.
    if email_user and email_user.email_validated:
        record_event(
            EventName.REGISTER_REJECTED,
            dimensions={"reason": "email_taken"},
        )
        return _opaque_register_success()

    # Branch 3: email taken, unvalidated. Resend the confirmation email to the
    # real pending owner, but gate the send through the same per-account
    # attempt-count/rate-limit guard the resend endpoint uses so a repeated
    # register cannot become an unbounded email-send oracle. Whether the send
    # fires or is skipped, the response is the identical opaque success.
    if email_user:
        warning_log(f"User={email_user.id} has not validated email yet")
        record_event(
            EventName.REGISTER_REJECTED,
            dimensions={"reason": "unvalidated_email"},
        )
        # Guard email_confirm presence (mirrors send_resend_registration_email):
        # an unvalidated user normally retains an Email_Validations row, but the
        # admin erasure path clears it while leaving email_validated False. Skip
        # the send in that case — still returning the identical opaque success so
        # the outcome stays indistinguishable rather than raising a 500.
        if email_user.email_confirm is not None:
            _send_confirmation_email_if_not_rate_limited(
                email_user, email_user.email_confirm
            )
        return _opaque_register_success()

    # Branch 4: new account. Build the user + token, then send the confirmation
    # email server-side. Do NOT log the user in — validation completes via the
    # emailed link, keeping genuine and taken paths uniform.
    new_user = _build_new_user(username, email, password)
    new_user.email_confirm = _build_new_email_validation(new_user)

    db.session.add(new_user)
    db.session.commit()

    record_event(EventName.REGISTER_SUCCESS)

    safe_add_log(f"User={new_user.id} successfully registered but not email validated")

    _send_confirmation_email_and_log(new_user, new_user.email_confirm)
    return _opaque_register_success()


def _opaque_register_success() -> FlaskResponse:
    """The single, uniform opaque success returned on every email-axis outcome."""
    return APIResponse(message=MEMBER_SUCCESS.CONFIRM_EMAIL_SENT).to_response()


def _send_confirmation_email_if_not_rate_limited(
    user: Users, email_validation: Email_Validations
) -> None:
    """Resend the confirmation email to a pending account, gated by the same
    per-account attempt guard `send_validation_email_to_user()` uses.

    A skipped (rate-limited) send is deliberately indistinguishable from a
    completed one — the caller always returns the uniform opaque success.
    """
    if email_validation.has_too_many_email_attempts():
        return

    has_more_attempts = email_validation.increment_attempt()
    db.session.commit()

    if not has_more_attempts:
        return

    _send_confirmation_email_and_log(user, email_validation)


def _send_confirmation_email_and_log(
    user: Users, email_validation: Email_Validations
) -> None:
    """Send the confirmation email and, on a Mailjet server failure (>= 500),
    log only — never surface a distinguishing error response (that would re-leak
    the taken-vs-new signal). Mirrors `/forgot-password`'s logging pattern.
    """
    email_send_result = _send_account_confirmation_email(user, email_validation)
    if email_send_result.status_code >= 500:
        error_log(
            f"(4) Email failed to send: registration confirmation for "
            f"User={user.id}"
        )


def _build_new_user(username: str, email: str, password: str) -> Users:
    return Users(
        username=username,
        email=email.lower(),
        plaintext_password=password,
    )


def _build_new_email_validation(user: Users) -> Email_Validations:
    return Email_Validations(validation_token=user.get_email_validation_token())
