from backend import db
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.app_logger import safe_add_log, warning_log
from backend.extensions.metrics.writer import record_event
from backend.invite_links.lookup import find_invite_by_token
from backend.invite_links.next_target import parse_invite_next
from backend.metrics.events import EventName
from backend.models.email_validations import Email_Validations
from backend.models.users import Users
from backend.schemas.errors import build_field_error_response
from backend.splash.constants import RegisterErrorCodes
from backend.splash.services.validate_email import (
    _guard_and_send_confirmation_email,
    _send_confirmation_email_and_log,
)
from backend.utils.strings.splash_form_strs import REGISTER_LOGIN_FORM
from backend.utils.strings.user_strs import MEMBER_SUCCESS, USER_FAILURE


def register_new_user(
    username: str, email: str, password: str, invite_next: str | None = None
) -> FlaskResponse:
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
        invite_next: Raw invite path from the splash page; silently ignored
            unless it parses and resolves to an invite row

    Returns:
        FlaskResponse: JSON response indicating success or failure
    """
    email_user: Users | None = Users.query.filter(Users.email == email.lower()).first()

    username_user: Users | None = Users.query.filter(Users.username == username).first()

    # Resolved once, identically on every branch, so the work is the same
    # whatever the outcome. Liveness is deliberately not checked here.
    target = parse_invite_next(invite_next)
    invite = find_invite_by_token(target.token) if target is not None else None

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
        # A resolved invite is stored on the existing row (latest wins) and
        # committed before the guard so it holds even when the send is
        # rate-limited; an unresolved value never clears a stored reference.
        if email_user.email_confirm is not None:
            if invite is not None:
                email_user.email_confirm.pending_invite_id = invite.id
                db.session.commit()
            _guard_and_send_confirmation_email(
                email_user, email_user.email_confirm, "registration confirmation"
            )
        return _opaque_register_success()

    # Branch 4: new account. Build the user + token, then send the confirmation
    # email server-side. Do NOT log the user in — validation completes via the
    # emailed link, keeping genuine and taken paths uniform.
    new_user = _build_new_user(username, email, password)
    new_user.email_confirm = _build_new_email_validation(new_user)
    if invite is not None:
        new_user.email_confirm.pending_invite_id = invite.id

    db.session.add(new_user)
    db.session.commit()

    record_event(EventName.REGISTER_SUCCESS)

    safe_add_log(f"User={new_user.id} successfully registered but not email validated")

    _send_confirmation_email_and_log(
        new_user, new_user.email_confirm, "registration confirmation"
    )
    return _opaque_register_success()


def _opaque_register_success() -> FlaskResponse:
    """The single, uniform opaque success returned on every email-axis outcome."""
    return APIResponse(message=MEMBER_SUCCESS.CONFIRM_EMAIL_SENT).to_response()


def _build_new_user(username: str, email: str, password: str) -> Users:
    return Users(
        username=username,
        email=email.lower(),
        plaintext_password=password,
    )


def _build_new_email_validation(user: Users) -> Email_Validations:
    return Email_Validations(validation_token=user.get_email_validation_token())
