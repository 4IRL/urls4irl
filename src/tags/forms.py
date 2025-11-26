from flask_wtf import FlaskForm
from wtforms import SubmitField
from wtforms.validators import Length, InputRequired, ValidationError

from src.api_common.input_sanitization import sanitize_user_input
from src.utils.constants import TAG_CONSTANTS
from src.utils.string_field_v2 import StringFieldV2
from src.utils.strings import model_strs as MODEL_STRS
from src.utils.strings.tag_strs import TAGS_FAILURE


class NewTagForm(FlaskForm):
    """
    Form to add a tag to a URL in a Utub.

    Fields:
        tag_string (Stringfield): Maximum 30 chars? TODO
    """

    tag_string = StringFieldV2(
        "Tag",
        validators=[
            InputRequired(),
            Length(min=TAG_CONSTANTS.MIN_TAG_LENGTH, max=TAG_CONSTANTS.MAX_TAG_LENGTH),
        ],
        name=MODEL_STRS.TAG_STRING,
    )

    submit = SubmitField("Add tag to this URL!")

    def validate_tag_string(self, tag_string):
        """Validates tag is not empty strings"""
        if tag_string.data.replace(" ", "") == "":
            raise ValidationError("Tag must not be empty.")

        sanitized_tag = sanitize_user_input(tag_string.data)

        if (
            sanitized_tag is None
            or not isinstance(sanitized_tag, str)
            or len(sanitized_tag) < TAG_CONSTANTS.MIN_TAG_LENGTH
            or sanitized_tag != tag_string.data
        ):
            raise ValidationError(TAGS_FAILURE.INVALID_INPUT)

    # TODO Add tag validation (PG filter?)
