"""
Forms that are needed to be built here:
User registration form
Login Form
UTub building form
URL Creation form?

"""

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length, Email, EqualTo


class UserRegistrationForm(FlaskForm):
    """Form to register users. Inherits from FlaskForm. All fields require data.

    Fields:
        username (StringField): Length Requirements? Must be a unique username
        email (Stringfield): Must be a unique email
        confirm_email (Stringfield): Confirm's email
        password (PasswordField): Can set length requirements
        confirm_password (PasswordField): Confirms passwords
        submit (SubmitField): Represents the button to submit the form
    """

    username = StringField('Username', validators=[DataRequired(), Length(min=2, max=20)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    confirm_email = StringField('Confirm Email', validators=[DataRequired(), EqualTo(email)])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Password', validators=[DataRequired(), EqualTo(password)])

    submit = SubmitField('Register')


class LoginForm(FlaskForm):
    """Form to login users. Inherits from FlaskForm. All fields require data.

    Fields:
        ### TODO Email or username to login? (Stringfield): The user
        password (PasswordField): Must match the user's password
        submit (Submitfield): Represents the submit button to submit the form
    """

    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])

    submit = SubmitField('Login')


