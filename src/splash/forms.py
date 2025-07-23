from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, EmailField
from wtforms.validators import Length, Email, EqualTo, InputRequired, ValidationError

from src.models.users import Users
from src.utils.constants import USER_CONSTANTS
from src.utils.input_sanitization import sanitize_user_input
from src.utils.string_field_v2 import StringFieldV2
from src.utils.strings.reset_password_strs import FORGOT_PASSWORD, RESET_PASSWORD
from src.utils.strings.splash_form_strs import REGISTER_LOGIN_FORM, REGISTER_FORM
from src.utils.strings.user_strs import USER_FAILURE


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

    username = StringFieldV2(
        REGISTER_LOGIN_FORM.USERNAME_TEXT,
        validators=[
            InputRequired(),
            Length(
                min=USER_CONSTANTS.MIN_USERNAME_LENGTH,
                max=USER_CONSTANTS.MAX_USERNAME_LENGTH,
            ),
        ],
    )
    email = EmailField(
        REGISTER_LOGIN_FORM.EMAIL_TEXT, validators=[InputRequired(), Email()]
    )
    confirm_email = EmailField(
        REGISTER_LOGIN_FORM.CONFIRM_EMAIL_TEXT,
        validators=[InputRequired(), EqualTo(REGISTER_LOGIN_FORM.EMAIL)],
        name=REGISTER_FORM.CONFIRM_EMAIL,
    )
    password = PasswordField(
        REGISTER_LOGIN_FORM.PASSWORD_TEXT,
        validators=[
            InputRequired(),
            Length(
                min=USER_CONSTANTS.MIN_PASSWORD_LENGTH,
                max=USER_CONSTANTS.MAX_PASSWORD_LENGTH,
            ),
        ],
    )
    confirm_password = PasswordField(
        REGISTER_LOGIN_FORM.CONFIRM_PASSWORD_TEXT,
        validators=[InputRequired(), EqualTo(REGISTER_LOGIN_FORM.PASSWORD)],
        name=REGISTER_FORM.CONFIRM_PASSWORD,
    )

    submit = SubmitField(REGISTER_LOGIN_FORM.REGISTER)

    def get_email(self) -> str:
        return self.email.data if self.email.data is not None else ""

    def get_password(self) -> str:
        return self.password.data if self.password.data is not None else ""

    def validate_username(self, username: StringFieldV2):
        """Validates username is unique in the db"""
        user: Users = Users.query.filter(Users.username == username.get()).first()

        if user and user.email_validated:
            raise ValidationError(USER_FAILURE.USERNAME_TAKEN)

        sanitized_username = sanitize_user_input(username.get())

        if (
            sanitized_username is None
            or not isinstance(sanitized_username, str)
            or len(sanitized_username) < USER_CONSTANTS.MIN_USERNAME_LENGTH
            or sanitized_username != username.get()
        ):
            raise ValidationError(USER_FAILURE.INVALID_INPUT)

    def validate_email(self, email):
        """Validates username is unique in the db"""
        user: Users = Users.query.filter(Users.email == email.data.lower()).first()

        if user:
            if not user.email_validated:
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
        REGISTER_LOGIN_FORM.USERNAME_TEXT,
        validators=[
            InputRequired(),
            Length(
                min=USER_CONSTANTS.MIN_USERNAME_LENGTH,
                max=USER_CONSTANTS.MAX_USERNAME_LENGTH,
            ),
        ],
    )
    password = PasswordField(
        REGISTER_LOGIN_FORM.PASSWORD_TEXT, validators=[InputRequired()]
    )

    submit = SubmitField(REGISTER_LOGIN_FORM.LOGIN)

    def validate_username(self, username):
        user: Users = Users.query.filter(Users.username == username.data).first()

        if not user:
            raise ValidationError(USER_FAILURE.USER_NOT_EXIST)

    def validate_password(self, password):
        user: Users = Users.query.filter(Users.username == self.username.data).first()
        if not user:
            return

        if not user.is_password_correct(password.data):
            raise ValidationError(USER_FAILURE.INVALID_PASSWORD)


class ValidateEmailForm(FlaskForm):
    submit = SubmitField(REGISTER_LOGIN_FORM.SEND_EMAIL_VALIDATION)


class ForgotPasswordForm(FlaskForm):
    email = EmailField(
        FORGOT_PASSWORD.EMAIL_TEXT, validators=[InputRequired(), Email()]
    )

    submit = SubmitField(FORGOT_PASSWORD.SEND_PASSWORD_RESET_EMAIL)

    def get_email(self) -> str:
        return self.email.data if self.email.data is not None else ""


class ResetPasswordForm(FlaskForm):
    new_password = PasswordField(
        RESET_PASSWORD.NEW_PASSWORD,
        validators=[InputRequired(), Length(min=12, max=64)],
        name=RESET_PASSWORD.NEW_PASSWORD_FIELD,
    )
    confirm_new_password = PasswordField(
        RESET_PASSWORD.CONFIRM_NEW_PASSWORD,
        validators=[InputRequired()],
        name=RESET_PASSWORD.CONFIRM_NEW_PASSWORD_FIELD,
    )

    submit = SubmitField(RESET_PASSWORD.RESET_YOUR_PASSWORD)

    def get_new_password(self) -> str:
        return self.new_password.data if self.new_password.data is not None else ""

    def validate_confirm_new_password(self, confirm_new_password):
        if confirm_new_password.data != self.new_password.data:
            raise ValidationError(RESET_PASSWORD.PASSWORDS_NOT_IDENTICAL)
