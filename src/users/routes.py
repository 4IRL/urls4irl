from datetime import datetime

from flask import (
    Blueprint,
    jsonify,
    redirect,
    url_for,
    render_template,
    request,
    abort,
    session,
    Response,
)
from flask_login import current_user, login_user, logout_user
from requests import Response

from src import db, login_manager, email_sender
from src.models import Utub, Utub_Users, User, EmailValidation, ForgotPassword
from src.users.forms import (
    LoginForm,
    UserRegistrationForm,
    UTubNewUserForm,
    ValidateEmailForm,
    ForgotPasswordForm,
    ResetPasswordForm,
)
from src.utils import strings as U4I_STRINGS
from src.utils.constants import EMAIL_CONSTANTS
from src.utils.email_validation import email_validation_required

users = Blueprint("users", __name__)

# Standard response for JSON messages
STD_JSON = U4I_STRINGS.STD_JSON_RESPONSE
USER_FAILURE = U4I_STRINGS.USER_FAILURE
USER_SUCCESS = U4I_STRINGS.USER_SUCCESS
EMAILS = U4I_STRINGS.EMAILS
EMAILS_FAILURE = U4I_STRINGS.EMAILS_FAILURE
RESET_PASSWORD = U4I_STRINGS.RESET_PASSWORD
FORGOT_PASSWORD = U4I_STRINGS.FORGOT_PASSWORD


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@login_manager.unauthorized_handler
def unauthorized():
    if not current_user.is_authenticated:
        return redirect(url_for("main.splash"))
    if current_user.is_authenticated and not current_user.email_confirm.is_validated:
        return redirect(url_for("users.confirm_email_after_register"))


@users.route("/login", methods=["GET", "POST"])
def login():
    """Login page. Allows user to register or login."""
    if current_user.is_authenticated:
        if not current_user.email_confirm.is_validated:
            return redirect(url_for("users.confirm_email_after_register"))
        return redirect(url_for("main.home"))

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

        return redirect(next_page) if next_page else url_for("main.home")

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


@users.route("/logout")
def logout():
    """Logs user out by clearing session details. Returns to login page."""
    logout_user()
    if EMAILS.EMAIL_VALIDATED_SESS_KEY in session.keys():
        session.pop(EMAILS.EMAIL_VALIDATED_SESS_KEY)
    return redirect(url_for("main.splash"))


@users.route("/register", methods=["GET", "POST"])
def register_user():
    """Allows a user to register an account."""
    if current_user.is_authenticated:
        if not current_user.email_confirm.is_validated:
            return redirect(url_for("users.confirm_email_after_register"))
        return redirect(url_for("main.home"))

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
                            STD_JSON.ERROR_CODE: 2,
                            STD_JSON.ERRORS: register_form.errors,
                        }
                    ),
                    401,
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
            401,
        )

    return render_template("register_user.html", register_form=register_form)


@users.route("/user/remove/<int:utub_id>/<int:user_id>", methods=["POST"])
@email_validation_required
def delete_user(utub_id: int, user_id: int):
    """
    Delete a user from a Utub. The creator of the Utub can delete anyone but themselves.
    Any user can remove themselves from a UTub they did not create.

    Args:
        utub_id (int): ID of the UTub to remove the user from
        user_id (int): ID of the User to remove from the UTub
    """
    current_utub = Utub.query.get_or_404(utub_id)

    if user_id == current_utub.created_by.id:
        # Creator tried to delete themselves, not allowed
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: USER_FAILURE.CREATOR_CANNOT_REMOVE_THEMSELF,
                    USER_FAILURE.EMAIL_VALIDATED: str(True),
                    STD_JSON.ERROR_CODE: 1,
                }
            ),
            400,
        )

    current_user_ids_in_utub = [member.user_id for member in current_utub.members]
    current_user_id = current_user.id

    # User can't remove if current user is not in this current UTub's members
    # User can't remove if current user is not creator of UTub and requested user is not same as current user
    current_user_not_in_utub = current_user_id not in current_user_ids_in_utub
    member_trying_to_remove_another_member = (
        current_user_id != current_utub.created_by.id and user_id != current_user_id
    )

    if current_user_not_in_utub or member_trying_to_remove_another_member:
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: USER_FAILURE.INVALID_PERMISSION_TO_REMOVE,
                    USER_FAILURE.EMAIL_VALIDATED: str(True),
                    STD_JSON.ERROR_CODE: 2,
                }
            ),
            403,
        )

    if user_id not in current_user_ids_in_utub:
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: USER_FAILURE.USER_NOT_IN_UTUB,
                    USER_FAILURE.EMAIL_VALIDATED: str(True),
                    STD_JSON.ERROR_CODE: 3,
                }
            ),
            404,
        )

    user_to_delete_in_utub = Utub_Users.query.filter(
        Utub_Users.utub_id == utub_id, Utub_Users.user_id == user_id
    ).first_or_404()

    deleted_user = User.query.get(user_id)
    deleted_user_username = deleted_user.username

    db.session.delete(user_to_delete_in_utub)
    db.session.commit()

    return (
        jsonify(
            {
                STD_JSON.STATUS: STD_JSON.SUCCESS,
                STD_JSON.MESSAGE: USER_SUCCESS.USER_REMOVED,
                USER_SUCCESS.USER_ID_REMOVED: f"{user_id}",
                USER_SUCCESS.USERNAME_REMOVED: f"{deleted_user_username}",
                USER_SUCCESS.UTUB_ID: f"{utub_id}",
                USER_SUCCESS.UTUB_NAME: f"{current_utub.name}",
                USER_SUCCESS.UTUB_USERS: [
                    user.to_user.username for user in current_utub.members
                ],
            }
        ),
        200,
    )


@users.route("/user/add/<int:utub_id>", methods=["POST"])
@email_validation_required
def add_user(utub_id: int):
    """
    Creator of utub wants to add a user to the utub.

    Args:
        utub_id (int): The utub to which this user is being added
    """
    utub = Utub.query.get_or_404(utub_id)

    if int(utub.created_by.id) != int(current_user.get_id()):
        # User not authorized to add a user to this UTub
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: USER_FAILURE.NOT_AUTHORIZED,
                    STD_JSON.ERROR_CODE: 1,
                }
            ),
            403,
        )

    utub_new_user_form = UTubNewUserForm()

    if utub_new_user_form.validate_on_submit():
        username = utub_new_user_form.username.data

        new_user = User.query.filter_by(username=username).first_or_404()
        already_in_utub = [
            member for member in utub.members if int(member.user_id) == int(new_user.id)
        ]

        if already_in_utub:
            # User already exists in UTub
            return (
                jsonify(
                    {
                        STD_JSON.STATUS: STD_JSON.FAILURE,
                        STD_JSON.MESSAGE: USER_FAILURE.USER_ALREADY_IN_UTUB,
                        STD_JSON.ERROR_CODE: 2,
                    }
                ),
                400,
            )

        else:
            new_user_to_utub = Utub_Users()
            new_user_to_utub.to_user = new_user
            utub.members.append(new_user_to_utub)
            db.session.commit()

            # Successfully added user to UTub
            return (
                jsonify(
                    {
                        STD_JSON.STATUS: STD_JSON.SUCCESS,
                        STD_JSON.MESSAGE: USER_SUCCESS.USER_ADDED,
                        USER_SUCCESS.USER_ID_ADDED: int(new_user.id),
                        USER_SUCCESS.UTUB_ID: int(utub_id),
                        USER_SUCCESS.UTUB_NAME: f"{utub.name}",
                        USER_SUCCESS.UTUB_USERS: [
                            user.to_user.username for user in utub.members
                        ],
                    }
                ),
                200,
            )

    if utub_new_user_form.errors is not None:
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: USER_FAILURE.UNABLE_TO_ADD,
                    STD_JSON.ERROR_CODE: 3,
                    STD_JSON.ERRORS: utub_new_user_form.errors,
                }
            ),
            404,
        )

    return (
        jsonify(
            {
                STD_JSON.STATUS: STD_JSON.FAILURE,
                STD_JSON.MESSAGE: USER_FAILURE.UNABLE_TO_ADD,
                STD_JSON.ERROR_CODE: 4,
            }
        ),
        404,
    )


@users.route("/confirm_email", methods=["GET"])
def confirm_email_after_register():
    if current_user.is_anonymous:
        return redirect(url_for("main.splash"))
    if current_user.email_confirm.is_validated:
        return redirect(url_for("main.home"))
    return render_template(
        "email_validation/email_needs_validation_modal.html",
        validate_email_form=ValidateEmailForm(),
    )


@users.route("/send_validation_email", methods=["POST"])
def send_validation_email():
    current_email_validation: EmailValidation = EmailValidation.query.filter(
        EmailValidation.user_id == current_user.id
    ).first_or_404()

    if current_email_validation.is_validated:
        return redirect(url_for("main.home"))

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
            f"Sending this to the user's email:\n{url_for('users.validate_email', token=current_email_validation.confirm_url, _external=True)}"
        )
    url_for_confirmation = url_for(
        "users.validate_email",
        token=current_email_validation.confirm_url,
        _external=True,
    )
    email_send_result = email_sender.send_account_email_confirmation(
        current_user.email, current_user.username, url_for_confirmation
    )
    return _handle_email_sending_result(email_send_result)


def _handle_email_sending_result(email_result: Response):
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


def _handle_mailjet_failure(email_result: Response, error_code: int = 1):
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


@users.route("/validate/<string:token>", methods=["GET"])
def validate_email(token: str):
    user_to_validate, expired = User.verify_token(token, EMAILS.VALIDATE_EMAIL)

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
        return render_template(
            "splash.html",
            email_validation_modal=True,
            expired_token=EMAILS.TOKEN_EXPIRED,
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
        return abort(404)

    if not user_to_validate.email_confirm.confirm_url == token:
        return abort(404)

    user_to_validate.email_confirm.validate()
    user_to_validate.email_confirm.confirm_url = ""
    db.session.commit()
    login_user(user_to_validate)
    session[EMAILS.EMAIL_VALIDATED_SESS_KEY] = True
    return redirect(url_for("main.home"))


@users.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    if current_user.is_authenticated:
        if not current_user.email_confirm.is_validated:
            return redirect(url_for("users.confirm_email_after_register"))
        return redirect(url_for("main.home"))

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


def _handle_after_forgot_password_form_validated(
    forgot_password_form: ForgotPasswordForm,
) -> Response:
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
                    f"Sending this to the user's email:\n{url_for('users.reset_password', token=forgot_password_obj.reset_token, _external=True)}"
                )
            url_for_reset = url_for(
                "users.reset_password",
                token=forgot_password_obj.reset_token,
                _external=True,
            )
            email_send_result = email_sender.send_password_reset_email(
                user_with_email.email, user_with_email.username, url_for_reset
            )
            if email_send_result.status_code >= 500:
                return _handle_mailjet_failure(email_send_result)

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


@users.route("/confirm_password_reset", methods=["GET"])
def confirm_password_reset():
    return render_template(
        "password_reset/reset_password.html", reset_password_form=ResetPasswordForm()
    )


@users.route("/reset_password/<string:token>", methods=["GET", "POST"])
def reset_password(token: str):
    reset_password_user, expired = User.verify_token(
        token, RESET_PASSWORD.RESET_PASSWORD_KEY
    )

    if expired:
        reset_password_obj = ForgotPassword.query.filter(
            ForgotPassword.reset_token == token
        ).first_or_404()
        db.session.delete(reset_password_obj)
        db.session.commit()
        return redirect(url_for("main.splash"))

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
