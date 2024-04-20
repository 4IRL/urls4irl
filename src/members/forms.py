from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import Length, InputRequired, ValidationError
from src.models import User
from src.utils.strings.splash_form_strs import REGISTER_LOGIN_FORM
from src.utils.strings.user_strs import USER_FAILURE


class UTubNewMemberForm(FlaskForm):
    """
    Form to add a user to a UTub. Inherits from FlaskForm. All fields require data.

    Fields:
        username (Stringfield): Maximum 30 chars? TODO
    """

    username = StringField(
        REGISTER_LOGIN_FORM.USERNAME_TEXT,
        validators=[InputRequired(), Length(min=1, max=30)],
    )

    submit = SubmitField("Add to this UTub!")

    def validate_username(self, username):
        """Validates username is unique in the db"""
        username_exists = User.query.filter_by(username=username.data).first()

        if not username_exists:
            raise ValidationError(USER_FAILURE.USER_NOT_EXIST)
