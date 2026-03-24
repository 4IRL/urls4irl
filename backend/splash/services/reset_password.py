from flask import abort, redirect, render_template, url_for
from werkzeug import Response as WerkzeugResponse

from backend import db
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.app_logger import critical_log, warning_log
from backend.models.forgot_passwords import Forgot_Passwords
from backend.models.users import Users
from backend.models.utils import VerifyTokenResponse
from backend.splash.utils import verify_token
from backend.utils.all_routes import ROUTES
from backend.utils.strings.reset_password_strs import RESET_PASSWORD


def _validate_reset_token(token: str) -> Users | WerkzeugResponse:
    """
    Validates the reset password JWT token and returns the associated user,
    or a redirect response if the token is expired.

    If the token is invalid (bad user, unvalidated email, or stale/mismatched
    token), this function calls ``abort(404)`` which raises an ``HTTPException``
    and never returns.

    Args:
        token: The JWT passed in the URL to reset the password

    Returns:
        Users: The user associated with the valid token
        WerkzeugResponse: A redirect to the splash page when the token is expired
    """
    verify_token_response = verify_token(token, RESET_PASSWORD.RESET_PASSWORD_KEY)

    if verify_token_response.is_expired:
        return _handle_expired_password_reset_token(
            verify_token_response=verify_token_response, token=token
        )

    if not verify_token_response.user:
        critical_log("Invalid user associated with token")
        abort(404)

    reset_password_user = verify_token_response.user

    if not reset_password_user.email_validated:
        _handle_reset_token_for_user_with_invalid_email(
            user=reset_password_user, token=token
        )
        abort(404)

    if _is_invalid_or_expired_token(reset_password_user, token):
        critical_log(
            f"User={reset_password_user.id} never reset password, or token expired or invalid"
        )
        abort(404)

    return reset_password_user


def get_reset_password_page(token: str) -> WerkzeugResponse | str:
    """
    Handles GET request for the reset password page. Validates the token
    and renders the reset password modal.

    Args:
        token: The JWT passed in the URL to reset the password

    Returns:
        WerkzeugResponse: A redirect when the token is expired
        str: Rendered HTML for the reset password page
    """
    result = _validate_reset_token(token)
    if isinstance(result, WerkzeugResponse):
        return result

    return render_template("pages/splash.html", is_resetting_password=True)


def reset_password_for_user(token: str, new_password: str) -> FlaskResponse:
    """
    Handles POST request for resetting a password. Validates the token
    and changes the user's password.

    Args:
        token: The JWT passed in the URL to reset the password
        new_password: The new password to set

    Returns:
        FlaskResponse: JSON response indicating success or failure
    """
    result = _validate_reset_token(token)
    if isinstance(result, WerkzeugResponse):
        return result

    return _validate_resetting_password(result, new_password)


def _handle_expired_password_reset_token(
    verify_token_response: VerifyTokenResponse,
    token: str,
) -> WerkzeugResponse:
    """
    If user has an expired reset token, redirect them back to the splash page.

    Args:
        verify_token_response: Data related to token verification
        token: The JWT token in the URL

    Returns:
        WerkzeugResponse: URL redirect to the Splash Page
    """
    reset_password_user = verify_token_response.user
    reset_password_obj = Forgot_Passwords.query.filter(
        Forgot_Passwords.reset_token == token
    ).first_or_404()
    db.session.delete(reset_password_obj)
    db.session.commit()
    warning_log(
        f"User={reset_password_user.id if reset_password_user else 'None'} reset password token expired"
    )
    return redirect(url_for(ROUTES.SPLASH.SPLASH_PAGE))


def _handle_reset_token_for_user_with_invalid_email(user: Users, token: str):
    reset_password_obj = Forgot_Passwords.query.filter(
        Forgot_Passwords.reset_token == token
    ).first_or_404()
    db.session.delete(reset_password_obj)
    db.session.commit()
    critical_log(
        f"User={user.id} not email validated but received password reset token"
    )


def _is_invalid_or_expired_token(user: Users, token: str) -> bool:
    return (
        user.forgot_password is None
        or user.forgot_password.reset_token != token
        or user.forgot_password.is_more_than_hour_old()
    )


def _validate_resetting_password(
    reset_password_user: Users, new_password: str
) -> FlaskResponse:

    reset_password_user.change_password(new_password)
    forgot_password_obj = reset_password_user.forgot_password
    db.session.delete(forgot_password_obj)
    db.session.commit()

    return APIResponse(
        message=RESET_PASSWORD.PASSWORD_RESET,
    ).to_response()
