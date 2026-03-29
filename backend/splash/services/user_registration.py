from flask_login import login_user
from backend import db
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.app_logger import safe_add_log, warning_log
from backend.schemas.errors import (
    build_field_error_response,
    build_message_error_response,
)
from backend.models.email_validations import Email_Validations
from backend.models.users import Users
from backend.splash.constants import RegisterErrorCodes
from backend.utils.strings.splash_form_strs import REGISTER_LOGIN_FORM
from backend.utils.strings.user_strs import USER_FAILURE, USER_REGISTERED


def register_new_user(username: str, email: str, password: str) -> FlaskResponse:
    """
    Registers a new user. Checks for email and username uniqueness first.

    If the email belongs to an unvalidated account and that is the only issue,
    short-circuits to a 401 so the frontend can redirect to email validation.

    Args:
        username: The requested username
        email: The requested email
        password: The plaintext password

    Returns:
        FlaskResponse: JSON response indicating success or failure
    """
    errors: dict[str, list[str]] = {}
    unvalidated_email = False

    email_user: Users | None = Users.query.filter(Users.email == email.lower()).first()

    username_user: Users | None = Users.query.filter(Users.username == username).first()

    if email_user:
        if email_user.email_validated:
            errors[REGISTER_LOGIN_FORM.EMAIL] = [USER_FAILURE.EMAIL_TAKEN]
        else:
            unvalidated_email = True

    if username_user and username_user.email_validated:
        errors[REGISTER_LOGIN_FORM.USERNAME] = [USER_FAILURE.USERNAME_TAKEN]

    if errors:
        warning_log("Form errors when registering")
        return build_field_error_response(
            message=USER_FAILURE.UNABLE_TO_REGISTER,
            errors=errors,
            error_code=RegisterErrorCodes.INVALID_FORM_INPUT,
        )

    if unvalidated_email:
        login_user(email_user)
        warning_log(f"User={email_user.id} has not validated email yet")
        return build_message_error_response(
            message=USER_FAILURE.ACCOUNT_CREATED_EMAIL_NOT_VALIDATED,
            error_code=RegisterErrorCodes.ACCOUNT_NOT_EMAIL_VALIDATED,
            status_code=401,
        )

    new_user = _build_new_user(username, email, password)
    new_user.email_confirm = _build_new_email_validation(new_user)

    db.session.add(new_user)
    db.session.commit()

    login_user(new_user)

    safe_add_log(f"User={new_user.id} successfully registered but not email validated")
    return APIResponse(
        status_code=201,
        message=USER_REGISTERED,
    ).to_response()


def _build_new_user(username: str, email: str, password: str) -> Users:
    return Users(
        username=username,
        email=email.lower(),
        plaintext_password=password,
    )


def _build_new_email_validation(user: Users) -> Email_Validations:
    return Email_Validations(validation_token=user.get_email_validation_token())
