from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, ValidationError
from wtforms.validators import Length, InputRequired

from src.utils.constants import URL_CONSTANTS
from src.utils.input_sanitization import sanitize_user_input
from src.utils.string_field_v2 import StringFieldV2
from src.utils.strings.model_strs import MODELS
from src.utils.strings.url_strs import URL_FAILURE


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
    url_title = StringFieldV2(
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

    def validate_url_title(self, url_title):
        sanitized_url_title = sanitize_user_input(url_title.data)

        if (
            sanitized_url_title is None
            or not isinstance(sanitized_url_title, str)
            or len(sanitized_url_title) < URL_CONSTANTS.MIN_URL_TITLE_LENGTH
            or sanitized_url_title != url_title.data
        ):
            raise ValidationError(URL_FAILURE.INVALID_INPUT)


class UpdateURLForm(FlaskForm):
    """
    Form to update a URL in this UTub. Inherits from FlaskForm.

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

    def get_url_string(self) -> str:
        return self.url_string.data if self.url_string.data is not None else ""


class UpdateURLTitleForm(FlaskForm):
    """
    Form to update a URL in this UTub. Inherits from FlaskForm.

    Fields:
        url_title (Stringfield): Required. Maximum 2000 chars? TODO
    """

    url_title = StringFieldV2(
        "URL Title",
        validators=[InputRequired(), Length(max=URL_CONSTANTS.MAX_URL_TITLE_LENGTH)],
        name=MODELS.URL_TITLE,
    )

    submit = SubmitField("Edit URL Title!")

    def validate_url_title(self, url_title):
        sanitized_url_title = sanitize_user_input(url_title.data)

        if (
            sanitized_url_title is None
            or not isinstance(sanitized_url_title, str)
            or len(sanitized_url_title) < URL_CONSTANTS.MIN_URL_TITLE_LENGTH
            or sanitized_url_title != url_title.data
        ):
            raise ValidationError(URL_FAILURE.INVALID_INPUT)
