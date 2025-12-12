from flask import abort, redirect, render_template, request, url_for
from werkzeug import Response as WerkzeugResponse

from src import db
from src.api_common.responses import APIResponse, FlaskResponse
from src.app_logger import critical_log, warning_log
from src.models.forgot_passwords import Forgot_Passwords
from src.models.users import Users
from src.models.utils import VerifyTokenResponse
from src.splash.forms import ResetPasswordForm
from src.splash.utils import build_form_errors, verify_token
from src.utils.all_routes import ROUTES
from src.utils.strings.reset_password_strs import RESET_PASSWORD
from src.utils.strings.user_strs import USER_FAILURE


def reset_password_for_user(token: str) -> WerkzeugResponse | FlaskResponse | str:
    """
    Handles resetting a password for a User. Users pass a JWT token via URL and this token must be validated before the password must be reset.

    Args:
        token (str): The JWT passed in the URL to reset the password

    Response:
        (WerkzeugResponse): When redirecting the User to another URL
        (FlaskRespnse): Contains JSON and HTTP status code in response
        (str): Rendered HTML for the user
    """
    verify_token_response = verify_token(token, RESET_PASSWORD.RESET_PASSWORD_KEY)

    if verify_token_response.is_expired:
        return _handle_expired_password_reset_token(
            verify_token_response=verify_token_response, token=token
        )

    if not verify_token_response.user:
        # Invalid token
        critical_log("Invalid user associated with token")
        abort(404)

    reset_password_user = verify_token_response.user

    if not reset_password_user.email_validated:
        # Remove the object if it exists
        _handle_reset_token_for_user_with_invalid_email(
            user=reset_password_user, token=token
        )
        abort(404)

    if _is_invalid_or_expired_token(reset_password_user, token):
        critical_log(
            f"User={reset_password_user.id} never reset password, or token expired or invalid"
        )
        abort(404)

    reset_password_form = ResetPasswordForm()

    if request.method == "GET":
        return render_template(
            "pages/splash.html",
            is_resetting_password=True,
            reset_password_form=reset_password_form,
        )

    if not reset_password_form.validate_on_submit():
        return _handle_invalid_reset_password_form_input(
            reset_password_form=reset_password_form, user=reset_password_user
        )

    return _validate_resetting_password(reset_password_user, reset_password_form)


def _handle_expired_password_reset_token(
    verify_token_response: VerifyTokenResponse,
    token: str,
) -> WerkzeugResponse:
    """
    If user has an expired reset token, redirect them back to the splash page.

    Args:
        verify_token_response (VerifyTokenResponse): Data related to token verification
        token (str): The JWT token in the URL

    Response:
        (WerkzeugResponse): URL redirect to the Splash Page
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


def _handle_invalid_reset_password_form_input(
    reset_password_form: ResetPasswordForm, user: Users
) -> FlaskResponse:
    if reset_password_form.errors is not None:
        warning_log(f"User={user.id} | Invalid form for resetting password")
        return APIResponse(
            status_code=400,
            message=RESET_PASSWORD.RESET_PASSWORD_INVALID,
            error_code=1,
            errors=build_form_errors(reset_password_form),
        ).to_response()

    critical_log(f"User={user.id} unable to reset password")
    return APIResponse(
        status_code=404, message=USER_FAILURE.SOMETHING_WENT_WRONG, error_code=2
    ).to_response()


def _validate_resetting_password(
    reset_password_user: Users, reset_password_form: ResetPasswordForm
) -> FlaskResponse:

    reset_password_user.change_password(reset_password_form.get_new_password())
    forgot_password_obj = reset_password_user.forgot_password
    db.session.delete(forgot_password_obj)
    db.session.commit()

    return APIResponse(
        message=RESET_PASSWORD.PASSWORD_RESET,
    ).to_response()
