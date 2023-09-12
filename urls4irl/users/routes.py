from flask import Blueprint, jsonify, redirect, url_for, render_template, request, abort, session
from flask_login import current_user, login_user, logout_user, AnonymousUserMixin
from urls4irl import db, login_manager
from urls4irl.models import Utub, Utub_Users, User, EmailValidation
from urls4irl.users.forms import LoginForm, UserRegistrationForm, UTubNewUserForm, ValidateEmail
from urls4irl.utils import strings as U4I_STRINGS
from urls4irl.utils.constants import EmailConstants
from urls4irl.utils.email_validation import email_validation_required

users = Blueprint("users", __name__)

# Standard response for JSON messages
STD_JSON = U4I_STRINGS.STD_JSON_RESPONSE
USER_FAILURE = U4I_STRINGS.USER_FAILURE
USER_SUCCESS = U4I_STRINGS.USER_SUCCESS
EMAILS = U4I_STRINGS.EMAILS
EMAILS_FAILURE = U4I_STRINGS.EMAILS_FAILURE


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
        TESTING = True
        if TESTING and not user.email_confirm.is_validated:
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
        new_email_validation = EmailValidation(
            confirm_url=email_validation_token
        )
        new_user.email_confirm = new_email_validation
        db.session.add(new_user)
        db.session.commit()
        user = User.query.filter_by(username=username).first()
        login_user(user)
        validate_email_form = ValidateEmail()
        return render_template("emails/email_needs_validation_modal.html", validate_email_form=validate_email_form), 201

    # Input form errors
    if register_form.errors is not None:
        if EMAILS.EMAIL in register_form.errors and USER_FAILURE.ACCOUNT_CREATED_EMAIL_NOT_VALIDATED in register_form.errors[EMAILS.EMAIL]:
            login_user(User.query.filter(User.email == register_form.email.data).first_or_404())
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
    Creater of utub wants to add a user to the utub.

    Args:
        utub_id (int): The utub that this user is being added to
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
    if current_user.email_confirm.is_validated:
        return redirect(url_for("main.home"))
    return render_template("emails/email_needs_validation_modal.html", validate_email_form=ValidateEmail())


@users.route("/send_validation_email", methods=["POST"])
def send_validation_email():
    current_email_validation: EmailValidation = EmailValidation.query.filter(EmailValidation.user_id == current_user.id).first_or_404()

    if current_email_validation.is_validated:
        return redirect(url_for("main.home"))

    if current_email_validation.check_if_too_many_attempts():
        db.session.commit()
        return (jsonify(
            {
                STD_JSON.STATUS: STD_JSON.FAILURE,
                STD_JSON.ERROR_CODE: 1,
                STD_JSON.MESSAGE: EMAILS_FAILURE.TOO_MANY_ATTEMPTS_MAX
                }
        ), 429)

    
    more_attempts_allowed = current_email_validation.increment_attempt()
    db.session.commit()

    if not more_attempts_allowed:
        return (jsonify(
            {
                STD_JSON.STATUS: STD_JSON.FAILURE,
                STD_JSON.ERROR_CODE: 2,
                STD_JSON.MESSAGE: str(EmailConstants.MAX_EMAIL_ATTEMPTS_IN_HOUR - current_email_validation.attempts) + EMAILS_FAILURE.TOO_MANY_ATTEMPTS,
            }
        ), 429)

    print(f"Sending this to the user's email:\n{url_for('users.validate_email', token=current_email_validation.confirm_url, _external=True)}")
    # TODO: Send another email
    return (
        jsonify(
            {
                STD_JSON.STATUS: STD_JSON.SUCCESS,
                STD_JSON.MESSAGE: EMAILS.EMAIL_SENT
            }
    ), 200)



@users.route("/validate/<string:token>", methods=["GET"])
def validate_email(token: str):
    user_to_validate: User = User.verify_email_validation_token(token)
    if not user_to_validate:
        # Link is invalid or token is expired
        return abort(404)
        
    user_to_validate.email_confirm.validate()
    db.session.commit()
    login_user(user_to_validate)
    session[EMAILS.EMAIL_VALIDATED_SESS_KEY] = True
    return redirect(url_for("main.home"))
