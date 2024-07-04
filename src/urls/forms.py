from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import Length, InputRequired

from src.utils.constants import URL_CONSTANTS
from src.utils.strings.model_strs import MODELS


class NewURLForm(FlaskForm):
    """
    Form to add a URL to a UTub. Inherits from FlaskForm.

    Fields:
        URL (Stringfield): Required. Maximum 2000 chars? TODO
        URL Title (Stringfield): Not required. Maximum 100 chars? TODO
    """

    url_string = StringField(
        "URL",
        validators=[
            InputRequired(),
            Length(min=URL_CONSTANTS.MIN_URL_LENGTH, max=URL_CONSTANTS.MAX_URL_LENGTH),
        ],
        name=MODELS.URL_STRING,
    )
    url_title = StringField(
        "URL Title",
        validators=[
            InputRequired(),
            Length(
                min=URL_CONSTANTS.MIN_URL_TITLE_LENGTH,
                max=URL_CONSTANTS.MAX_URL_TITLE_LENGTH,
            ),
        ],
        name=MODELS.URL_TITLE,
    )

    submit = SubmitField("Add URL to this UTub!")


class EditURLForm(FlaskForm):
    """
    Form to edit a URL in this UTub. Inherits from FlaskForm.

    Fields:
        URL (Stringfield): Required. Maximum 2000 chars? TODO
    """

    url_string = StringField(
        "URL",
        validators=[
            InputRequired(),
            Length(min=URL_CONSTANTS.MIN_URL_LENGTH, max=URL_CONSTANTS.MAX_URL_LENGTH),
        ],
        name=MODELS.URL_STRING,
    )

    submit = SubmitField("Edit URL!")


class EditURLTitleForm(FlaskForm):
    """
    Form to edit a URL in this UTub. Inherits from FlaskForm.

    Fields:
        url_title (Stringfield): Required. Maximum 2000 chars? TODO
    """

    url_title = StringField(
        "URL Title",
        validators=[InputRequired(), Length(max=URL_CONSTANTS.MAX_URL_TITLE_LENGTH)],
        name=MODELS.URL_TITLE,
    )

    submit = SubmitField("Edit URL Title!")
