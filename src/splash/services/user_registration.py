from typing import Sequence, cast
from flask import render_template
from flask_login import login_user
from src import db
from src.api_common.responses import APIResponse, FlaskResponse
from src.app_logger import safe_add_log, warning_log
from src.models.email_validations import Email_Validations
from src.models.users import Users
from src.splash.forms import UserRegistrationForm, ValidateEmailForm
from src.splash.utils import build_form_errors
from src.utils.strings.email_validation_strs import EMAILS
from src.utils.strings.user_strs import USER_FAILURE


def handle_invalid_user_registration_form_inputs(
    register_form: UserRegistrationForm,
) -> FlaskResponse | str:
    """
    Handles building a response when there are form errors in the registration form.

    We have to handle invalidated email errors separately. The invalidated email error
    must be the only form error for it to be shown.

    Args:
        register_form (UserRegistrationForm): The registration form for the new user

    Returns:
        tuple[Response, int]:
            (Response): The JSON data to respond with containing the form errors
            (int): The HTTP status code for the response
        OR (str): The HTML to render if there are no form errors
    """
    # Input form errors
    if register_form.errors is not None:
        if EMAILS.EMAIL in register_form.errors:
            return _build_response_for_email_errors(register_form)

        warning_log("User had form errors on register")
        return APIResponse(
            status_code=400,
            message=USER_FAILURE.UNABLE_TO_REGISTER,
            error_code=2,
            errors=build_form_errors(register_form),
        ).to_response()

    return render_template("register_user.html", register_form=register_form)


def _build_response_for_email_errors(
    register_form: UserRegistrationForm,
) -> FlaskResponse:
    """
    We want to limit displaying invalidated email errors to the User until they have finished
    no other errors exist. This means the form should be fully valid before receiving an error
    that shows the email is not validated yet.

    If the invalidated email error is the only error, then the response will indicate that.

    If there are any other errors, besides the invalidated email error, then all other errors are shown and the invalidated email error is not shown.

    Args:
        register_form (UserRegistrationForm): The registration form for the new user

    Returns:
        tuple[Response, int]:
            (Response): The JSON data to respond with containing the form errors
            (int): The HTTP status code for the response
    """
    email_errors = cast(Sequence, register_form.errors[EMAILS.EMAIL])

    invalidated_email_error_is_not_only_error = (
        _check_if_invalidated_email_error_only_form_error(
            email_errors=email_errors, register_form=register_form
        )
    )

    if invalidated_email_error_is_not_only_error:
        return _build_response_when_invalidated_email_not_only_error_in_register_form(
            email_errors=email_errors, register_form=register_form
        )

    return _build_response_when_invalidated_email_only_error(register_form)


def _check_if_invalidated_email_error_only_form_error(
    email_errors: Sequence, register_form: UserRegistrationForm
) -> bool:
    """
    Checks if the invalidated email error is the only error in the Registration form errors.

    Args:
        email_errors (Sequence): All Form Errors in the form
        register_form (UserRegistrationForm): The registration form for the new user

    Returns:
        (bool): True if the invalidated email error is the only form error
    """
    return (
        USER_FAILURE.ACCOUNT_CREATED_EMAIL_NOT_VALIDATED not in email_errors
        or len(register_form.errors) != 1
        or len(email_errors) != 1
    )


def _build_response_when_invalidated_email_not_only_error_in_register_form(
    email_errors: Sequence, register_form: UserRegistrationForm
) -> FlaskResponse:
    """
    Checks if the invalidated email error is the only error in the Registration form errors.

    Args:
        email_errors (Sequence): All Form Errors in the form
        register_form (UserRegistrationForm): The registration form for the new user

    Returns:
        tuple[Response, int]:
            (Response): The JSON data to respond with containing the form errors
            (int): The HTTP status code for the response
    """
    warning_log("Form errors when registering")
    # Do not show to user that this email has not been validated if they have other form errors
    if USER_FAILURE.ACCOUNT_CREATED_EMAIL_NOT_VALIDATED in email_errors:
        warning_log("User not email validated but other form errors")

        # We remove the invalidated email error when there are other form errors
        email_errors.remove(  # type: ignore
            USER_FAILURE.ACCOUNT_CREATED_EMAIL_NOT_VALIDATED
        )

    return APIResponse(
        status_code=400,
        message=USER_FAILURE.UNABLE_TO_REGISTER,
        error_code=2,
        errors=build_form_errors(register_form),
    ).to_response()


def _build_response_when_invalidated_email_only_error(
    register_form: UserRegistrationForm,
) -> FlaskResponse:
    """
    Builds the JSON response when the invalidated email form error is the only form error.

    Args:
        register_form (UserRegistrationForm): The registration form for the new user

    Returns:
        tuple[Response, int]:
            (Response): The JSON data to respond with containing the form errors
            (int): The HTTP status code for the response
    """
    user: Users = Users.query.filter(
        Users.email == register_form.get_email().lower()
    ).first_or_404()

    # Login the new user so they can send another validation email to themselves
    login_user(user)

    warning_log(f"User={user.id} has not validated email yet")
    return APIResponse(
        status_code=401,
        message=USER_FAILURE.ACCOUNT_CREATED_EMAIL_NOT_VALIDATED,
        error_code=1,
    ).to_response()


def register_new_user(register_form: UserRegistrationForm) -> tuple[str, int]:
    """
    Registers a new user and sends them the email validation form HTML in response.

    Args:
        register_form (UserRegistrationForm): The registration form for the new user

    Returns:
        tuple[str, int]:
            (str): The HTML for the email validation form
            (int): The HTTP status code for the response
    """
    new_user = _build_new_user(register_form)
    new_user.email_confirm = _build_new_email_validation(new_user)

    db.session.add(new_user)
    db.session.commit()

    login_user(new_user)

    safe_add_log(f"User={new_user.id} successfully registered but not email validated")
    validate_email_form = ValidateEmailForm()
    return (
        render_template(
            "email_validation/email_needs_validation_modal.html",
            validate_email_form=validate_email_form,
        ),
        201,
    )


def _build_new_user(register_form: UserRegistrationForm) -> Users:
    return Users(
        username=register_form.username.get(),
        email=register_form.get_email().lower(),
        plaintext_password=register_form.get_password(),
    )


def _build_new_email_validation(user: Users) -> Email_Validations:
    return Email_Validations(validation_token=user.get_email_validation_token())
