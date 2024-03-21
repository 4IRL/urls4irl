from flask import (
    Blueprint,
    jsonify,
    redirect,
    url_for,
    render_template,
    request,
    abort,
    session,
)
from flask_login import current_user, login_user

from src import db, email_sender
from src.models import User, EmailValidation, ForgotPassword, verify_token
from src.users.forms import (
    LoginForm,
    UserRegistrationForm,
    ValidateEmailForm,
    ForgotPasswordForm,
    ResetPasswordForm,
)
from src.utils.strings.email_validation_strs import EMAILS, EMAILS_FAILURE
from src.utils.strings.json_strs import STD_JSON_RESPONSE
from src.utils.strings.reset_password_strs import FORGOT_PASSWORD, RESET_PASSWORD
from src.utils.strings.user_strs import USER_FAILURE, USER_SUCCESS
from src.utils.all_routes import ROUTES
from src.utils.constants import EMAIL_CONSTANTS
from src.splash.utils import (
    _handle_after_forgot_password_form_validated,
    _handle_email_sending_result,
    _validate_resetting_password,
)

# Standard response for JSON messages
STD_JSON = STD_JSON_RESPONSE

splash = Blueprint("splash", __name__)


@splash.route("/", methods=["GET"])
def splash_page():
    """Splash page for an unlogged in user."""
    if current_user.is_authenticated:
        if not current_user.email_confirm.is_validated:
            return render_template("splash.html", email_validation_modal=True)
        return redirect(url_for(ROUTES.UTUBS.HOME))
    return render_template("splash.html")


@splash.route("/register", methods=["GET", "POST"])
def register_user():
    """Allows a user to register an account."""
    if current_user.is_authenticated:
        if not current_user.email_confirm.is_validated:
            return redirect(url_for(ROUTES.SPLASH.CONFIRM_EMAIL))
        return redirect(url_for(ROUTES.UTUBS.HOME))

    register_form: UserRegistrationForm = UserRegistrationForm()

    if request.method == "GET":
        return render_template("register_user.html", register_form=register_form)

    if register_form.validate_on_submit():
        username = register_form.username.data
        email = register_form.email.data
        plain_password = register_form.password.data
        new_user = User(
            username=username,
            email=email,
            plaintext_password=plain_password,
        )
        email_validation_token = new_user.get_email_validation_token()
        new_email_validation = EmailValidation(confirm_url=email_validation_token)
        new_user.email_confirm = new_email_validation
        db.session.add(new_user)
        db.session.commit()
        user = User.query.filter_by(username=username).first()
        login_user(user)
        validate_email_form = ValidateEmailForm()
        return (
            render_template(
                "email_validation/email_needs_validation_modal.html",
                validate_email_form=validate_email_form,
            ),
            201,
        )

    # Input form errors
    if register_form.errors is not None:
        if EMAILS.EMAIL in register_form.errors:
            email_errors = register_form.errors[EMAILS.EMAIL]
            if (
                USER_FAILURE.ACCOUNT_CREATED_EMAIL_NOT_VALIDATED not in email_errors
                or len(register_form.errors) != 1
                or len(email_errors) != 1
            ):
                # Do not show to user that this email has not been validated if they have other form errors
                if USER_FAILURE.ACCOUNT_CREATED_EMAIL_NOT_VALIDATED in email_errors:
                    email_errors.remove(
                        USER_FAILURE.ACCOUNT_CREATED_EMAIL_NOT_VALIDATED
                    )
                return (
                    jsonify(
                        {
                            STD_JSON.STATUS: STD_JSON.FAILURE,
                            STD_JSON.MESSAGE: USER_FAILURE.UNABLE_TO_REGISTER,
                            STD_JSON.ERROR_CODE: 3,
                            STD_JSON.ERRORS: register_form.errors,
                        }
                    ),
                    400,
                )
            else:
                login_user(
                    User.query.filter(
                        User.email == register_form.email.data
                    ).first_or_404()
                )
                return (
                    jsonify(
                        {
                            STD_JSON.STATUS: STD_JSON.FAILURE,
                            STD_JSON.MESSAGE: USER_FAILURE.ACCOUNT_CREATED_EMAIL_NOT_VALIDATED,
                            STD_JSON.ERROR_CODE: 1,
                        }
                    ),
                    401,
                )

        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: USER_FAILURE.UNABLE_TO_REGISTER,
                    STD_JSON.ERROR_CODE: 2,
                    STD_JSON.ERRORS: register_form.errors,
                }
            ),
            400,
        )

    return render_template("register_user.html", register_form=register_form)


@splash.route("/login", methods=["GET", "POST"])
def login():
    """Login page. Allows user to register or login."""
    if current_user.is_authenticated:
        if not current_user.email_confirm.is_validated:
            return redirect(url_for(ROUTES.SPLASH.CONFIRM_EMAIL))
        return redirect(url_for(ROUTES.UTUBS.HOME))

    login_form = LoginForm()

    if request.method == "GET":
        return render_template("login.html", login_form=login_form)

    if login_form.validate_on_submit():
        username = login_form.username.data
        user: User = User.query.filter_by(username=username).first()
        login_user(user)  # Can add Remember Me functionality here
        if not user.email_confirm.is_validated:
            return (
                jsonify(
                    {
                        STD_JSON.STATUS: STD_JSON.FAILURE,
                        STD_JSON.MESSAGE: USER_FAILURE.ACCOUNT_CREATED_EMAIL_NOT_VALIDATED,
                        STD_JSON.ERROR_CODE: 1,
                    }
                ),
                401,
            )

        next_page = request.args.get(
            "next"
        )  # Takes user to the page they wanted to originally before being logged in

        return redirect(next_page) if next_page else url_for(ROUTES.UTUBS.HOME)

    # Input form errors
    if login_form.errors is not None:
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: USER_FAILURE.UNABLE_TO_LOGIN,
                    STD_JSON.ERROR_CODE: 2,
                    STD_JSON.ERRORS: login_form.errors,
                }
            ),
            401,
        )

    return render_template("login.html", login_form=login_form)


@splash.route("/confirm-email", methods=["GET"])
def confirm_email_after_register():
    if current_user.is_anonymous:
        return redirect(url_for(ROUTES.SPLASH.SPLASH_PAGE))
    if current_user.email_confirm.is_validated:
        return redirect(url_for(ROUTES.UTUBS.HOME))
    return render_template(
        "email_validation/email_needs_validation_modal.html",
        validate_email_form=ValidateEmailForm(),
    )


@splash.route("/send-validation-email", methods=["POST"])
def send_validation_email():
    current_email_validation: EmailValidation = EmailValidation.query.filter(
        EmailValidation.user_id == current_user.id
    ).first_or_404()

    if current_email_validation.is_validated:
        return redirect(url_for(ROUTES.UTUBS.HOME))

    if current_email_validation.check_if_too_many_attempts():
        db.session.commit()
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.ERROR_CODE: 1,
                    STD_JSON.MESSAGE: EMAILS_FAILURE.TOO_MANY_ATTEMPTS_MAX,
                }
            ),
            429,
        )

    more_attempts_allowed = current_email_validation.increment_attempt()
    db.session.commit()

    if not more_attempts_allowed:
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.ERROR_CODE: 2,
                    STD_JSON.MESSAGE: str(
                        EMAIL_CONSTANTS.MAX_EMAIL_ATTEMPTS_IN_HOUR
                        - current_email_validation.attempts
                    )
                    + EMAILS_FAILURE.TOO_MANY_ATTEMPTS,
                }
            ),
            429,
        )

    if not email_sender.is_production() and not email_sender.is_testing():
        print(
            f"Sending this to the user's email:\n{url_for(ROUTES.SPLASH.VALIDATE_EMAIL, token=current_email_validation.confirm_url, _external=True)}"
        )
    url_for_confirmation = url_for(
        ROUTES.SPLASH.VALIDATE_EMAIL,
        token=current_email_validation.confirm_url,
        _external=True,
    )
    email_send_result = email_sender.send_account_email_confirmation(
        current_user.email, current_user.username, url_for_confirmation
    )
    return _handle_email_sending_result(email_send_result)


@splash.route("/validate/<string:token>", methods=["GET"])
def validate_email(token: str):
    user_to_validate: User
    expired: bool
    user_to_validate, expired = verify_token(token, EMAILS.VALIDATE_EMAIL)

    if expired:
        invalid_email: EmailValidation = EmailValidation.query.filter(
            EmailValidation.confirm_url == token
        ).first_or_404()
        user_with_expired_token: User = invalid_email.user
        new_token = user_with_expired_token.get_email_validation_token()
        invalid_email.confirm_url = new_token
        invalid_email.reset_attempts()
        db.session.commit()
        login_user(user_with_expired_token)
        return (
            render_template(
                "splash.html",
                email_validation_modal=True,
                expired_token=EMAILS.TOKEN_EXPIRED,
            ),
            400,
        )

    if not user_to_validate:
        # Link is invalid, so remove any users and email validation rows associated with this token
        invalid_emails = EmailValidation.query.filter(
            EmailValidation.confirm_url == token
        ).all()
        if invalid_emails is not None:
            for invalid_email in invalid_emails:
                user_of_invalid_email = invalid_email.user
                db.session.delete(user_of_invalid_email)
                db.session.delete(invalid_email)
            db.session.commit()
        abort(404)

    if not user_to_validate.email_confirm.confirm_url == token:
        abort(404)

    user_to_validate.email_confirm.validate()
    user_to_validate.email_confirm.confirm_url = ""
    db.session.commit()
    login_user(user_to_validate)
    session[EMAILS.EMAIL_VALIDATED_SESS_KEY] = True
    return redirect(url_for(ROUTES.UTUBS.HOME))


@splash.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if current_user.is_authenticated:
        if not current_user.email_confirm.is_validated:
            return redirect(url_for(ROUTES.SPLASH.CONFIRM_EMAIL))
        return redirect(url_for(ROUTES.UTUBS.HOME))

    forgot_password_form = ForgotPasswordForm()
    if request.method == "GET":
        return render_template(
            "password_reset/forgot_password.html",
            forgot_password_form=forgot_password_form,
        )

    if forgot_password_form.validate_on_submit():
        return _handle_after_forgot_password_form_validated(forgot_password_form)

    if forgot_password_form.errors is not None:
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: FORGOT_PASSWORD.INVALID_EMAIL,
                    STD_JSON.ERROR_CODE: 1,
                    STD_JSON.ERRORS: forgot_password_form.errors,
                }
            ),
            401,
        )

    return (
        jsonify(
            {
                STD_JSON.STATUS: STD_JSON.FAILURE,
                STD_JSON.MESSAGE: USER_FAILURE.SOMETHING_WENT_WRONG,
                STD_JSON.ERROR_CODE: 2,
            }
        ),
        404,
    )


@splash.route("/confirm-password-reset", methods=["GET"])
def confirm_password_reset():
    return render_template(
        "password_reset/reset_password.html", reset_password_form=ResetPasswordForm()
    )


@splash.route("/reset-password/<string:token>", methods=["GET", "POST"])
def reset_password(token: str):
    reset_password_user: User
    expired: bool
    reset_password_user, expired = verify_token(
        token, RESET_PASSWORD.RESET_PASSWORD_KEY
    )

    if expired:
        reset_password_obj = ForgotPassword.query.filter(
            ForgotPassword.reset_token == token
        ).first_or_404()
        db.session.delete(reset_password_obj)
        db.session.commit()
        return redirect(url_for(ROUTES.SPLASH.SPLASH_PAGE))

    if not reset_password_user:
        # Invalid token
        abort(404)

    if not reset_password_user.is_email_authenticated():
        # Remove the object if it exists
        reset_password_obj = ForgotPassword.query.filter(
            ForgotPassword.reset_token == token
        ).first_or_404()
        db.session.delete(reset_password_obj)
        db.session.commit()
        abort(404)

    if (
        reset_password_user.forgot_password.reset_token != token
        or reset_password_user.forgot_password.is_more_than_hour_old()
    ):
        abort(404)

    if request.method == "GET":
        return render_template(
            "splash.html",
            forgot_password_modal=True,
        )

    reset_password_form = ResetPasswordForm()

    if reset_password_form.validate_on_submit():
        return _validate_resetting_password(reset_password_user, reset_password_form)

    if reset_password_form.errors is not None:
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: RESET_PASSWORD.RESET_PASSWORD_INVALID,
                    STD_JSON.ERROR_CODE: 2,
                    STD_JSON.ERRORS: reset_password_form.errors,
                }
            ),
            400,
        )
