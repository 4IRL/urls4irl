from datetime import datetime
from flask import jsonify, url_for, Response
import requests

from src import db, email_sender
from src.models import ForgotPassword, User
from src.users.forms import ForgotPasswordForm, ResetPasswordForm
from src.utils.strings.email_validation_strs import EMAILS
from src.utils.strings.json_strs import STD_JSON_RESPONSE
from src.utils.strings.reset_password_strs import FORGOT_PASSWORD, RESET_PASSWORD
from src.utils.all_routes import ROUTES

STD_JSON = STD_JSON_RESPONSE


def _handle_email_sending_result(email_result: requests.Response):
    status_code: int = email_result.status_code
    json_response: dict = email_result.json()

    if status_code == 200:
        return (
            jsonify(
                {STD_JSON.STATUS: STD_JSON.SUCCESS, STD_JSON.MESSAGE: EMAILS.EMAIL_SENT}
            ),
            200,
        )

    elif status_code < 500:
        message = json_response.get(EMAILS.MESSAGES, EMAILS.ERROR_WITH_MAILJET)
        if message == EMAILS.ERROR_WITH_MAILJET:
            errors = message
        else:
            errors = message.get(EMAILS.MAILJET_ERRORS, EMAILS.ERROR_WITH_MAILJET)

        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: EMAILS.EMAIL_FAILED,
                    STD_JSON.ERROR_CODE: 3,
                    STD_JSON.ERRORS: errors,
                }
            ),
            400,
        )

    else:
        return _handle_mailjet_failure(email_result, 4)


def _handle_mailjet_failure(email_result: requests.Response, error_code: int = 1):
    json_response = email_result.json()
    message = json_response.get(EMAILS.MESSAGES, EMAILS.ERROR_WITH_MAILJET)
    if message == EMAILS.ERROR_WITH_MAILJET:
        errors = message
    else:
        errors = message.get(EMAILS.MAILJET_ERRORS, EMAILS.ERROR_WITH_MAILJET)
    return (
        jsonify(
            {
                STD_JSON.STATUS: STD_JSON.FAILURE,
                STD_JSON.MESSAGE: EMAILS.ERROR_WITH_MAILJET,
                STD_JSON.ERROR_CODE: error_code,
                STD_JSON.ERRORS: errors,
            }
        ),
        400,
    )


def _handle_after_forgot_password_form_validated(
    forgot_password_form: ForgotPasswordForm,
) -> tuple[Response, int]:
    user_with_email: User = User.query.filter_by(
        email=forgot_password_form.email.data
    ).first()

    if user_with_email is not None:
        if not user_with_email.email_confirm.is_validated:
            return (
                jsonify(
                    {
                        STD_JSON.STATUS: STD_JSON.SUCCESS,
                        STD_JSON.MESSAGE: FORGOT_PASSWORD.EMAIL_SENT_MESSAGE,
                    }
                ),
                200,
            )

        # Check if user has already tried to reset their password before
        prev_forgot_password: ForgotPassword = user_with_email.forgot_password
        forgot_password_obj = _create_or_reset_forgot_password_object_for_user(
            user_with_email, prev_forgot_password
        )

        if forgot_password_obj.is_not_rate_limited():
            forgot_password_obj.increment_attempts()
            db.session.commit()

            if not email_sender.is_production() and not email_sender.is_testing():
                print(
                    f"Sending this to the user's email:\n{url_for(ROUTES.SPLASH.RESET_PASSWORD, token=forgot_password_obj.reset_token, _external=True)}"
                )
            url_for_reset = url_for(
                ROUTES.SPLASH.RESET_PASSWORD,
                token=forgot_password_obj.reset_token,
                _external=True,
            )
            email_send_result = email_sender.send_password_reset_email(
                user_with_email.email, user_with_email.username, url_for_reset
            )
            if email_send_result.status_code >= 500:
                return _handle_mailjet_failure(email_send_result, error_code=3)

    return (
        jsonify(
            {
                STD_JSON.STATUS: STD_JSON.SUCCESS,
                STD_JSON.MESSAGE: FORGOT_PASSWORD.EMAIL_SENT_MESSAGE,
            }
        ),
        200,
    )


def _create_or_reset_forgot_password_object_for_user(
    user: User, forgot_password: ForgotPassword
):
    if forgot_password is None:
        new_token = user.get_password_reset_token()
        forgot_password = ForgotPassword(reset_token=new_token)
        user.forgot_password = forgot_password
        db.session.add(forgot_password)
        db.session.commit()

    else:
        if (
            forgot_password.is_not_rate_limited()
            and forgot_password.is_more_than_hour_old()
        ):
            forgot_password.attempts = 0
            forgot_password.reset_token = user.get_password_reset_token()
            forgot_password.initial_attempt = datetime.utcnow()
            db.session.commit()

    return forgot_password


def _validate_resetting_password(
    reset_password_user: User, reset_password_form: ResetPasswordForm
) -> tuple[Response, int]:
    if reset_password_user.is_new_password_same_as_previous(
        reset_password_form.new_password.data
    ):
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: RESET_PASSWORD.SAME_PASSWORD,
                    STD_JSON.ERROR_CODE: 1,
                }
            ),
            400,
        )

    reset_password_user.change_password(reset_password_form.new_password.data)
    forgot_password_obj = reset_password_user.forgot_password
    db.session.delete(forgot_password_obj)
    db.session.commit()
    return (
        jsonify(
            {
                STD_JSON.STATUS: STD_JSON.SUCCESS,
                STD_JSON.MESSAGE: RESET_PASSWORD.PASSWORD_RESET,
            }
        ),
        200,
    )
