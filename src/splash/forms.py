
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import Length, Email, EqualTo, InputRequired, ValidationError
from src.models import User
from src.utils.strings.reset_password_strs import FORGOT_PASSWORD, RESET_PASSWORD
from src.utils.strings.splash_form_strs import REGISTER_LOGIN_FORM, REGISTER_FORM
from src.utils.strings.user_strs import USER_FAILURE
from src.utils.constants import USER_CONSTANTS

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
        REGISTER_LOGIN_FORM.USERNAME_TEXT,
        validators=[
            InputRequired(),
            Length(min=4, max=USER_CONSTANTS.MAX_USERNAME_LENGTH),
        ],
    )
    email = StringField(
        REGISTER_LOGIN_FORM.EMAIL_TEXT, validators=[InputRequired(), Email()]
    )
    confirm_email = StringField(
        REGISTER_LOGIN_FORM.CONFIRM_EMAIL_TEXT,
        validators=[InputRequired(), EqualTo(REGISTER_LOGIN_FORM.EMAIL)],
        name=REGISTER_FORM.CONFIRM_EMAIL
    )
    password = PasswordField(
        REGISTER_LOGIN_FORM.PASSWORD_TEXT,
        validators=[InputRequired(), Length(min=12, max=64)],
    )
    confirm_password = PasswordField(
        REGISTER_LOGIN_FORM.CONFIRM_PASSWORD_TEXT,
        validators=[InputRequired(), EqualTo(REGISTER_LOGIN_FORM.PASSWORD)],
        name=REGISTER_FORM.CONFIRM_PASSWORD
    )

    submit = SubmitField(REGISTER_LOGIN_FORM.REGISTER)

    def validate_username(self, username):
        """Validates username is unique in the db"""
        user: User = User.query.filter_by(username=username.data).first()

        if user and user.email_confirm.is_validated:
            raise ValidationError(USER_FAILURE.USERNAME_TAKEN)

    def validate_email(self, email):
        """Validates username is unique in the db"""
        user: User = User.query.filter_by(email=email.data.lower()).first()

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
        REGISTER_LOGIN_FORM.USERNAME_TEXT, validators=[InputRequired()]
    )
    password = PasswordField(
        REGISTER_LOGIN_FORM.PASSWORD_TEXT, validators=[InputRequired()]
    )

    submit = SubmitField(REGISTER_LOGIN_FORM.LOGIN)

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


class ValidateEmailForm(FlaskForm):
    submit = SubmitField(REGISTER_LOGIN_FORM.SEND_EMAIL_VALIDATION)


class ForgotPasswordForm(FlaskForm):
    email = StringField(
        FORGOT_PASSWORD.EMAIL_TEXT, validators=[InputRequired(), Email()]
    )

    submit = SubmitField(FORGOT_PASSWORD.SEND_PASSWORD_RESET_EMAIL)


class ResetPasswordForm(FlaskForm):
    new_password = PasswordField(
        RESET_PASSWORD.NEW_PASSWORD,
        validators=[InputRequired(), Length(min=12, max=64)],
        name=RESET_PASSWORD.NEW_PASSWORD_FIELD
    )
    confirm_new_password = PasswordField(
        RESET_PASSWORD.CONFIRM_NEW_PASSWORD,
        validators=[InputRequired()],
        name=RESET_PASSWORD.CONFIRM_NEW_PASSWORD_FIELD
    )

    submit = SubmitField(RESET_PASSWORD.RESET_YOUR_PASSWORD)

    def validate_confirm_new_password(self, confirm_new_password):
        if confirm_new_password.data != self.new_password.data:
            raise ValidationError(RESET_PASSWORD.PASSWORDS_NOT_IDENTICAL)
