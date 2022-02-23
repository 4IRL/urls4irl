"""
Forms that are needed to be built here:
UTub building form
URL Creation form
Tag form?

"""

from msilib.schema import _Validation_records
from flask import Flask
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length, Email, EqualTo, InputRequired, ValidationError
from urls4irl.models import User


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

    username = StringField('Username', validators=[InputRequired(), Length(min=4, max=20)])
    email = StringField('Email', validators=[InputRequired(), Email()])
    confirm_email = StringField('Confirm Email', validators=[InputRequired(), EqualTo('email')])
    password = PasswordField('Password', validators=[InputRequired(), Length(min=12, max=30)])
    confirm_password = PasswordField('Confirm Password', validators=[InputRequired(), EqualTo('password')])

    submit = SubmitField('Register')

    def validate_username(self, username):
        """Validates username is unique in the db"""
        username_exists = User.query.filter_by(username=username.data).first()

        if username_exists:
            raise ValidationError('That username is already taken. Please choose another.')

    def validate_email(self, email):
        """Validates username is unique in the db"""
        email_exists = User.query.filter_by(email=email.data).first()

        if email_exists:
            raise ValidationError('That email address is already in use.')
        

class LoginForm(FlaskForm):
    """Form to login users. Inherits from FlaskForm. All fields require data.

    Fields:
        ### TODO Email or username to login? (Stringfield): The user
        password (PasswordField): Must match the user's password
        submit (Submitfield): Represents the submit button to submit the form
    """

    username = StringField('Username', validators=[InputRequired()])
    password = PasswordField('Password', validators=[InputRequired()])

    submit = SubmitField('Login')


class UTubForm(FlaskForm):
    """Form to create a UTub. Inherits from FlaskForm. All fields require data.

    Fields:
        name (Stringfield): Maximum 30 chars? TODO
    """
    
    name = StringField('UTub Name', validators=[InputRequired(), Length(min=1, max=30)])

    submit = SubmitField('Create UTub!')