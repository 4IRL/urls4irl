from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import Length, InputRequired, ValidationError

from src.utils.constants import TAG_CONSTANTS
from src.utils.strings import model_strs as MODEL_STRS


class UTubNewUrlTagForm(FlaskForm):
    """
    Form to add a tag to a URL in a Utub.

    Fields:
        tag_string (Stringfield): Maximum 30 chars? TODO
    """

    tag_string = StringField(
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

    # TODO Add tag validation (PG filter?)
