from flask import current_app
import jwt
from jwt import exceptions as JWTExceptions

from src.models.users import Users
from src.models.utils import VerifyTokenResponse
from src.splash.forms import ResetPasswordForm, UserRegistrationForm
from src.utils.strings.config_strs import CONFIG_ENVS
from src.utils.strings.email_validation_strs import EMAILS
from src.utils.strings.reset_password_strs import RESET_PASSWORD
from src.utils.strings.splash_form_strs import REGISTER_FORM, REGISTER_LOGIN_FORM


def verify_token(token: str, token_key: str) -> VerifyTokenResponse:
    """
    Returns a valid user if one found, or None.
    Boolean indicates whether the token is expired or not.

    Args:
        token (str): The token to check
        token_key (str): The key of the token

    Returns:
        tuple[Users | None, bool]: Returns a User/None and Boolean
    """
    try:
        username_to_validate = jwt.decode(
            jwt=token,
            key=current_app.config[CONFIG_ENVS.SECRET_KEY],
            algorithms=[EMAILS.ALGORITHM],
        )

    except JWTExceptions.ExpiredSignatureError:
        return VerifyTokenResponse(is_expired=True)

    except (
        RuntimeError,
        TypeError,
        JWTExceptions.DecodeError,
    ):
        return VerifyTokenResponse(failed_due_to_exception=True)

    return VerifyTokenResponse(
        user=Users.query.filter(
            Users.username == username_to_validate[token_key]
        ).first_or_404(),
    )


def build_form_errors(
    form: ResetPasswordForm | UserRegistrationForm,
) -> dict[str, list[str]]:
    errors = {}
    if isinstance(form, ResetPasswordForm):
        if form.confirm_new_password.errors:
            errors[RESET_PASSWORD.CONFIRM_NEW_PASSWORD_FIELD] = (
                form.confirm_new_password.errors
            )
        if form.new_password.errors:
            errors[RESET_PASSWORD.NEW_PASSWORD_FIELD] = form.new_password.errors

    elif isinstance(form, UserRegistrationForm):
        if form.username.errors:
            errors[REGISTER_LOGIN_FORM.USERNAME] = form.username.errors
        if form.email.errors:
            errors[REGISTER_LOGIN_FORM.EMAIL] = form.email.errors
        if form.confirm_email.errors:
            errors[REGISTER_FORM.CONFIRM_EMAIL] = form.confirm_email.errors
        if form.password.errors:
            errors[REGISTER_LOGIN_FORM.PASSWORD] = form.password.errors
        if form.confirm_password.errors:
            errors[REGISTER_FORM.CONFIRM_PASSWORD] = form.confirm_password.errors

    return errors
