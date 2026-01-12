from flask import (
    Blueprint,
    redirect,
    url_for,
    render_template,
    request,
    abort,
)
from flask_login import current_user, login_user
from werkzeug import Response as WerkzeugResponse

from src import db
from src.api_common.auth_decorators import (
    no_authenticated_users_allowed,
)
from src.api_common.responses import FlaskResponse
from src.app_logger import (
    safe_add_log,
    warning_log,
)
from src.models.email_validations import Email_Validations
from src.models.users import Users
from src.splash.forms import (
    LoginForm,
    UserRegistrationForm,
    ValidateEmailForm,
    ForgotPasswordForm,
)
from src.splash.services.forgot_password import (
    handle_invalid_forgot_password_form_input,
    send_forgot_password_email_to_user,
)
from src.splash.services.reset_password import reset_password_for_user
from src.splash.services.user_login import (
    handle_invalid_user_login_form_inputs,
    login_user_to_u4i,
)
from src.splash.services.user_registration import (
    handle_invalid_user_registration_form_inputs,
    register_new_user,
)
from src.splash.services.validate_email import (
    send_validation_email_to_user,
    validate_email_for_user,
)
from src.utils.strings.email_validation_strs import EMAILS
from src.utils.all_routes import ROUTES
from src.utils.constants import provide_config_for_constants

splash = Blueprint("splash", __name__)


# TODO: Separate splash context processor from home page context processor
@splash.context_processor
def provide_constants():
    return provide_config_for_constants()


@splash.route("/invalid")
def error_page():
    abort(404)


@splash.route("/", methods=["GET"])
def splash_page() -> WerkzeugResponse | str:
    """Splash page for an unlogged in user."""
    if current_user.is_authenticated and current_user.email_validated:
        safe_add_log(f"User={current_user} already logged in")
        return redirect(url_for(ROUTES.UTUBS.HOME))
    return render_template("pages/splash.html")


@splash.route("/register", methods=["GET", "POST"])
@no_authenticated_users_allowed
def register_user() -> FlaskResponse | WerkzeugResponse | str | tuple[str, int]:
    """Allows a user to register an account."""
    register_form: UserRegistrationForm = UserRegistrationForm()

    if request.method == "GET":
        return render_template(
            "components/splash/register_user.html", register_form=register_form
        )

    if not register_form.validate_on_submit():
        return handle_invalid_user_registration_form_inputs(register_form)

    return register_new_user(register_form=register_form)


@splash.route("/login", methods=["GET", "POST"])
@no_authenticated_users_allowed
def login():
    """Login page. Allows user to register or login."""
    login_form = LoginForm()

    if request.method == "GET":
        return render_template("components/splash/login.html", login_form=login_form)

    if not login_form.validate_on_submit():
        return handle_invalid_user_login_form_inputs(login_form)

    return login_user_to_u4i(login_form)


@splash.route("/confirm-email", methods=["GET"])
def confirm_email_after_register() -> WerkzeugResponse | str:
    if current_user.is_anonymous:
        safe_add_log("No user logged in")
        return redirect(url_for(ROUTES.SPLASH.SPLASH_PAGE))
    if current_user.email_validated:
        warning_log(f"User={current_user.id} already logged in")
        return redirect(url_for(ROUTES.UTUBS.HOME))
    return render_template(
        "components/splash/validate_email.html",
        validate_email_form=ValidateEmailForm(),
    )


@splash.route("/send-validation-email", methods=["POST"])
def send_validation_email() -> WerkzeugResponse | FlaskResponse:
    return send_validation_email_to_user()


@splash.route("/validate/expired", methods=["GET"])
def validate_email_expired():
    expired_token = request.args.get("token", None)
    if expired_token is None:
        warning_log("No token provided")
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

    safe_add_log(f"User={user_with_expired_token.id} email validation token reset")
    return (
        render_template(
            "pages/splash.html",
            validate_email_form=ValidateEmailForm(),
            email_token_is_expired=True,
            expired_token_message=EMAILS.TOKEN_EXPIRED,
        ),
        200,
    )


@splash.route("/validate/<string:token>", methods=["GET"])
def validate_email(token: str) -> WerkzeugResponse:
    return validate_email_for_user(token)


@splash.route("/forgot-password", methods=["GET", "POST"])
@no_authenticated_users_allowed
def forgot_password() -> str | FlaskResponse:
    forgot_password_form = ForgotPasswordForm()
    if request.method == "GET":
        return render_template(
            "components/splash/forgot_password.html",
            forgot_password_form=forgot_password_form,
        )

    if not forgot_password_form.validate_on_submit():
        return handle_invalid_forgot_password_form_input(forgot_password_form)

    return send_forgot_password_email_to_user(forgot_password_form)


@splash.route("/reset-password/<string:token>", methods=["GET", "POST"])
def reset_password(token: str):
    return reset_password_for_user(token)
