from flask_wtf import FlaskForm
from wtforms import SubmitField
from wtforms.validators import Length, InputRequired, ValidationError

from src.api_common.input_sanitization import sanitize_user_input
from src.utils.form_utils import StringFieldV2, TextAreaFieldV2
from src.utils.strings.json_strs import FAILURE_GENERAL
from src.contact.constants import CONTACT_FORM_CONSTANTS


class ContactForm(FlaskForm):
    """
    Form to contact U4I creators. All fields require data.

    Fields:
        name (Stringfield): Maximum 30 chars?
    """

    subject = StringFieldV2(
        name="Subject",
        label="Subject",
        validators=[
            InputRequired(),
            Length(min=5, max=CONTACT_FORM_CONSTANTS.MAX_SUBJECT_LENGTH),
        ],
    )
    content = TextAreaFieldV2(
        name="Content",
        label="Content",
        validators=[
            InputRequired(),
            Length(max=CONTACT_FORM_CONSTANTS.MAX_CONTENT_LENGTH),
        ],
    )

    submit = SubmitField()

    def validate_subject(self, subject):
        if not subject.get():
            raise ValidationError(FAILURE_GENERAL.INVALID_INPUT)

        sanitized_subject = sanitize_user_input(subject.data)

        if sanitized_subject is None or sanitized_subject != subject.data:
            raise ValidationError(FAILURE_GENERAL.INVALID_INPUT)

    def validate_content(self, content):
        if not content.get():
            raise ValidationError(FAILURE_GENERAL.INVALID_INPUT)

        sanitized_content = sanitize_user_input(content.data)

        if sanitized_content is None or sanitized_content != content.data:
            raise ValidationError(FAILURE_GENERAL.INVALID_INPUT)
