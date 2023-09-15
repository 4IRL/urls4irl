from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import Length, Email, EqualTo, InputRequired, ValidationError
from urls4irl.models import User
from urls4irl.utils import strings as U4I_STRINGS
from urls4irl.utils.constants import UserConstants

USER_FAILURE = U4I_STRINGS.USER_FAILURE
LOGIN_REGISTER_FORM = U4I_STRINGS.REGISTER_LOGIN_FORM


class UserRegistrationForm(FlaskForm):
    """
    Form to register users. Inherits from FlaskForm. All fields require data.

    Fields:
        username (StringField): Length Requirements? Must be a unique username
        email (Stringfield): Must be a unique email
        confirm_email (Stringfield): Confirm's email
        password (PasswordField): Can set length requirements
        confirm_password (PasswordField): Confirms passwords
        submit (SubmitField): Represents the button to submit the form
    """

    username = StringField(
        LOGIN_REGISTER_FORM.USERNAME_TEXT,
        validators=[
            InputRequired(),
            Length(min=4, max=UserConstants.MAX_USERNAME_LENGTH),
        ],
    )
    email = StringField(
        LOGIN_REGISTER_FORM.EMAIL_TEXT, validators=[InputRequired(), Email()]
    )
    confirm_email = StringField(
        LOGIN_REGISTER_FORM.CONFIRM_EMAIL_TEXT,
        validators=[InputRequired(), EqualTo(LOGIN_REGISTER_FORM.EMAIL)],
    )
    password = PasswordField(
        LOGIN_REGISTER_FORM.PASSWORD_TEXT,
        validators=[InputRequired(), Length(min=12, max=64)],
    )
    confirm_password = PasswordField(
        LOGIN_REGISTER_FORM.CONFIRM_PASSWORD_TEXT,
        validators=[InputRequired(), EqualTo(LOGIN_REGISTER_FORM.PASSWORD)],
    )

    submit = SubmitField(LOGIN_REGISTER_FORM.REGISTER)

    def validate_username(self, username):
        """Validates username is unique in the db"""
        user: User = User.query.filter_by(username=username.data).first()

        if user and user.email_confirm.is_validated:
            raise ValidationError(USER_FAILURE.USERNAME_TAKEN)

    def validate_email(self, email):
        """Validates username is unique in the db"""
        user: User = User.query.filter_by(email=email.data).first()

        if user:
            if not user.email_confirm.is_validated:
                raise ValidationError(USER_FAILURE.ACCOUNT_CREATED_EMAIL_NOT_VALIDATED)
            raise ValidationError(USER_FAILURE.EMAIL_TAKEN)


class LoginForm(FlaskForm):
    """
    Form to login users. Inherits from FlaskForm. All fields require data.

    Fields:
        ### TODO Email or username to login? (Stringfield): The user
        password (PasswordField): Must match the user's password
        submit (Submitfield): Represents the submit button to submit the form
    """

    username = StringField(
        LOGIN_REGISTER_FORM.USERNAME_TEXT, validators=[InputRequired()]
    )
    password = PasswordField(
        LOGIN_REGISTER_FORM.PASSWORD_TEXT, validators=[InputRequired()]
    )

    submit = SubmitField(LOGIN_REGISTER_FORM.LOGIN)

    def validate_username(self, username):
        user: User = User.query.filter_by(username=username.data).first()

        if not user:
            raise ValidationError(USER_FAILURE.USER_NOT_EXIST)

    def validate_password(self, password):
        user: User = User.query.filter_by(username=self.username.data).first()
        if not user:
            return

        if not user.is_password_correct(password.data):
            raise ValidationError(USER_FAILURE.INVALID_PASSWORD)


class ValidateEmail(FlaskForm):
    submit = SubmitField(LOGIN_REGISTER_FORM.SEND_EMAIL_VALIDATION)


class UTubNewUserForm(FlaskForm):
    """
    Form to add a user to a UTub. Inherits from FlaskForm. All fields require data.

    Fields:
        username (Stringfield): Maximum 30 chars? TODO
    """

    username = StringField(
        LOGIN_REGISTER_FORM.USERNAME_TEXT,
        validators=[InputRequired(), Length(min=1, max=30)],
    )

    submit = SubmitField("Add to this UTub!")

    def validate_username(self, username):
        """Validates username is unique in the db"""
        username_exists = User.query.filter_by(username=username.data).first()

        if not username_exists:
            raise ValidationError(USER_FAILURE.USER_NOT_EXIST)
