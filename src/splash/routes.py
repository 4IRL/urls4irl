from urllib.parse import parse_qs, urlencode, urlparse
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
from src.models.email_validations import Email_Validations
from src.models.forgot_passwords import Forgot_Passwords
from src.models.users import Users
from src.models.utils import verify_token
from src.models.utub_members import Utub_Members
from src.splash.forms import (
    LoginForm,
    UserRegistrationForm,
    ValidateEmailForm,
    ForgotPasswordForm,
    ResetPasswordForm,
)
from src.utils.strings.email_validation_strs import EMAILS, EMAILS_FAILURE
from src.utils.strings.json_strs import STD_JSON_RESPONSE
from src.utils.strings.reset_password_strs import FORGOT_PASSWORD, RESET_PASSWORD
from src.utils.strings.user_strs import USER_FAILURE
from src.utils.all_routes import ROUTES
from src.utils.constants import CONSTANTS, EMAIL_CONSTANTS
from src.splash.utils import (
    _handle_after_forgot_password_form_validated,
    _handle_email_sending_result,
    _validate_resetting_password,
    build_form_errors,
)
from src.utils.strings.utub_strs import UTUB_ID_QUERY_PARAM

# Standard response for JSON messages
STD_JSON = STD_JSON_RESPONSE

splash = Blueprint("splash", __name__)


@splash.context_processor
def provide_constants():
    return dict(CONSTANTS=CONSTANTS())


@splash.route("/invalid")
def error_page():
    abort(404)


@splash.route("/", methods=["GET"])
def splash_page():
    """Splash page for an unlogged in user."""
    if current_user.is_authenticated and current_user.email_validated:
        return redirect(url_for(ROUTES.UTUBS.HOME))
    return render_template("splash.html")


@splash.route("/register", methods=["GET", "POST"])
def register_user():
    """Allows a user to register an account."""
    if current_user.is_authenticated:
        if not current_user.email_validated:
            return redirect(url_for(ROUTES.SPLASH.CONFIRM_EMAIL))
        return redirect(url_for(ROUTES.UTUBS.HOME))

    register_form: UserRegistrationForm = UserRegistrationForm()

    if request.method == "GET":
        return render_template("register_user.html", register_form=register_form)

    if register_form.validate_on_submit():
        username = register_form.username.data
        email = register_form.email.data
        plain_password = register_form.password.data
        new_user = Users(
            username=username,  # type: ignore
            email=email.lower(),  # type: ignore
            plaintext_password=plain_password,  # type: ignore
        )
        email_validation_token = new_user.get_email_validation_token()
        new_email_validation = Email_Validations(
            validation_token=email_validation_token
        )
        new_user.email_confirm = new_email_validation
        db.session.add(new_user)
        db.session.commit()
        user = Users.query.filter(Users.username == username).first()
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
                    email_errors.remove(  # type: ignore
                        USER_FAILURE.ACCOUNT_CREATED_EMAIL_NOT_VALIDATED
                    )
                return (
                    jsonify(
                        {
                            STD_JSON.STATUS: STD_JSON.FAILURE,
                            STD_JSON.MESSAGE: USER_FAILURE.UNABLE_TO_REGISTER,
                            STD_JSON.ERROR_CODE: 2,
                            STD_JSON.ERRORS: build_form_errors(register_form),
                        }
                    ),
                    400,
                )
            else:
                login_user(
                    Users.query.filter(
                        Users.email == register_form.email.data.lower()  # type: ignore
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
                    STD_JSON.ERRORS: build_form_errors(register_form),
                }
            ),
            400,
        )

    return render_template("register_user.html", register_form=register_form)


@splash.route("/login", methods=["GET", "POST"])
def login():
    """Login page. Allows user to register or login."""
    if current_user.is_authenticated:
        if not current_user.email_validated:
            return redirect(url_for(ROUTES.SPLASH.CONFIRM_EMAIL))
        return redirect(url_for(ROUTES.UTUBS.HOME))

    login_form = LoginForm()

    if request.method == "GET":
        return render_template("login.html", login_form=login_form)

    if login_form.validate_on_submit():
        username = login_form.username.data
        user: Users = Users.query.filter(Users.username == username).first()
        login_user(user)  # Can add Remember Me functionality here
        if not user.email_validated:
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
        next_page = _verify_and_provide_next_page(request.args.to_dict())
        return next_page if next_page else url_for(ROUTES.UTUBS.HOME)

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
            400,
        )

    return render_template("login.html", login_form=login_form)


def _verify_and_provide_next_page(request_args: dict[str, str]) -> str:
    url = ""
    if (
        len(request_args) != 1
        or "next" not in request_args
        or not isinstance(request_args.get("next"), str)
    ):
        return url

    rel_url = urlparse(request_args.get("next"))
    if rel_url.path != url_for(ROUTES.UTUBS.HOME):
        return url

    query_params = parse_qs(str(rel_url.query))
    if len(query_params) != 1 or UTUB_ID_QUERY_PARAM not in query_params:
        return url

    utub_id_vals = query_params.get(UTUB_ID_QUERY_PARAM, None)
    if not utub_id_vals or len(utub_id_vals) != 1:
        return url

    utub_id = utub_id_vals[0]

    if not utub_id.isdigit() or int(utub_id) <= 0:
        return url

    if Utub_Members.query.get((int(utub_id), current_user.id)) is None:
        return url

    url = (
        f"{url_for(ROUTES.UTUBS.HOME)}?{urlencode({UTUB_ID_QUERY_PARAM: int(utub_id)})}"
    )
    return url


@splash.route("/confirm-email", methods=["GET"])
def confirm_email_after_register():
    if current_user.is_anonymous:
        return redirect(url_for(ROUTES.SPLASH.SPLASH_PAGE))
    if current_user.email_validated:
        return redirect(url_for(ROUTES.UTUBS.HOME))
    return render_template(
        "email_validation/email_needs_validation_modal.html",
        validate_email_form=ValidateEmailForm(),
    )


@splash.route("/send-validation-email", methods=["POST"])
def send_validation_email():
    current_email_validation: Email_Validations = Email_Validations.query.filter(
        Email_Validations.user_id == current_user.id
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
            f"Sending this to the user's email:\n{url_for(ROUTES.SPLASH.VALIDATE_EMAIL, token=current_email_validation.validation_token, _external=True)}"
        )
    url_for_confirmation = url_for(
        ROUTES.SPLASH.VALIDATE_EMAIL,
        token=current_email_validation.validation_token,
        _external=True,
    )
    email_send_result = email_sender.send_account_email_confirmation(
        current_user.email, current_user.username, url_for_confirmation
    )
    return _handle_email_sending_result(email_send_result)


@splash.route("/validate/expired", methods=["GET"])
def validate_email_expired():
    expired_token = request.args.get("token", None)
    if expired_token is None:
        abort(404)

    invalid_email: Email_Validations = Email_Validations.query.filter(
        Email_Validations.validation_token == expired_token
    ).first_or_404()

    user_with_expired_token: Users = invalid_email.user
    new_token = user_with_expired_token.get_email_validation_token()
    invalid_email.validation_token = new_token
    invalid_email.reset_attempts()
    db.session.commit()
    login_user(user_with_expired_token)

    return (
        render_template(
            "splash.html",
            validate_email_form=ValidateEmailForm(),
            email_token_is_expired=True,
            expired_token_message=EMAILS.TOKEN_EXPIRED,
        ),
        200,
    )


@splash.route("/validate/<string:token>", methods=["GET"])
def validate_email(token: str):
    user_to_validate: Users
    expired: bool
    user_to_validate, expired = verify_token(token, EMAILS.VALIDATE_EMAIL)

    if expired:
        return redirect(url_for("splash.validate_email_expired", token=token))

    if not user_to_validate:
        # Link is invalid, so remove any users and email validation rows associated with this token
        invalid_emails = Email_Validations.query.filter(
            Email_Validations.validation_token == token
        ).all()
        if invalid_emails is not None:
            for invalid_email in invalid_emails:
                user_of_invalid_email = invalid_email.user
                db.session.delete(user_of_invalid_email)
                db.session.delete(invalid_email)
            db.session.commit()
        abort(404)

    email_validation: Email_Validations = user_to_validate.email_confirm

    if not email_validation.validation_token == token:
        abort(404)

    user_to_validate.validate_email()
    db.session.delete(email_validation)
    db.session.commit()
    login_user(user_to_validate)
    session[EMAILS.EMAIL_VALIDATED_SESS_KEY] = True
    return redirect(url_for(ROUTES.UTUBS.HOME))


@splash.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if current_user.is_authenticated:
        if not current_user.email_validated:
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


@splash.route("/reset-password/<string:token>", methods=["GET", "POST"])
def reset_password(token: str):
    reset_password_user: Users
    expired: bool
    reset_password_user, expired = verify_token(
        token, RESET_PASSWORD.RESET_PASSWORD_KEY
    )

    if expired:
        reset_password_obj = Forgot_Passwords.query.filter(
            Forgot_Passwords.reset_token == token
        ).first_or_404()
        db.session.delete(reset_password_obj)
        db.session.commit()
        return redirect(url_for(ROUTES.SPLASH.SPLASH_PAGE))

    if not reset_password_user:
        # Invalid token
        abort(404)

    if not reset_password_user.email_validated:
        # Remove the object if it exists
        reset_password_obj = Forgot_Passwords.query.filter(
            Forgot_Passwords.reset_token == token
        ).first_or_404()
        db.session.delete(reset_password_obj)
        db.session.commit()
        abort(404)

    if (
        reset_password_user.forgot_password is None
        or reset_password_user.forgot_password.reset_token != token
        or reset_password_user.forgot_password.is_more_than_hour_old()
    ):
        abort(404)

    reset_password_form = ResetPasswordForm()

    if request.method == "GET":
        return render_template(
            "splash.html",
            is_resetting_password=True,
            reset_password_form=reset_password_form,
        )

    if reset_password_form.validate_on_submit():
        return _validate_resetting_password(reset_password_user, reset_password_form)

    if reset_password_form.errors is not None:
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: RESET_PASSWORD.RESET_PASSWORD_INVALID,
                    STD_JSON.ERROR_CODE: 1,
                    STD_JSON.ERRORS: build_form_errors(reset_password_form),
                }
            ),
            400,
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
