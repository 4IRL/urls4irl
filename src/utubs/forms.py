from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, ValidationError
from wtforms.validators import Length, InputRequired

from src.utils.constants import UTUB_CONSTANTS
from src.utils.strings.form_strs import UTUB_FORM, UTUB_DESCRIPTION_FORM
from src.utils.strings.utub_strs import UTUB_FAILURE


class UTubForm(FlaskForm):
    """
    Form to create a UTub. Inherits from FlaskForm. All fields require data.

    Fields:
        name (Stringfield): Maximum 30 chars? TODO
    """

    name = StringField(
        name=UTUB_FORM.UTUB_NAME,
        label="UTub Name",
        validators=[
            InputRequired(),
            Length(
                min=UTUB_CONSTANTS.MIN_NAME_LENGTH, max=UTUB_CONSTANTS.MAX_NAME_LENGTH
            ),
        ],
    )
    description = StringField(
        name=UTUB_FORM.UTUB_DESCRIPTION,
        label="UTub Description",
        validators=[Length(max=UTUB_CONSTANTS.MAX_DESCRIPTION_LENGTH)],
    )

    submit = SubmitField()

    def validate_name(self, name):
        if name.data.replace(" ", "") == "":
            raise ValidationError(UTUB_FAILURE.UTUB_NAME_EMPTY)


class UTubNewNameForm(FlaskForm):
    """
    Form to edit a UTub name. Inherits from FlaskForm. All fields require data.

    Fields:
        name (Stringfield): Maximum 30 chars? TODO
    """

    name = StringField(
        name=UTUB_FORM.UTUB_NAME,
        label="UTub Name",
        validators=[
            InputRequired(),
            Length(
                min=UTUB_CONSTANTS.MIN_NAME_LENGTH, max=UTUB_CONSTANTS.MAX_NAME_LENGTH
            ),
        ],
    )

    submit = SubmitField()

    def validate_name(self, name):
        if name.data.replace(" ", "") == "":
            raise ValidationError(UTUB_FAILURE.UTUB_NAME_EMPTY)


class UTubDescriptionForm(FlaskForm):
    """
    Form to add a description to the UTub.

    To pre-populate forms:
    https://stackoverflow.com/questions/35892144/pre-populate-an-edit-form-with-wtforms-and-flask

    Fields:
        utub_description (Stringfield): Maximum 500 chars? TODO
    """

    # Not required, so as to allow the User to delete the description
    description = StringField(
        name=UTUB_DESCRIPTION_FORM.UTUB_DESCRIPTION,
        label="UTub Description",
        validators=[Length(max=UTUB_CONSTANTS.MAX_DESCRIPTION_LENGTH)],
    )

    submit = SubmitField()

    def validate_description(self, description):
        if description.data is None:
            return

        if description.data.replace(" ", "") == "":
            description.data = ""
