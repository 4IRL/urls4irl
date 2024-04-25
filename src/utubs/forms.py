from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, ValidationError
from wtforms.validators import Length, InputRequired


class UTubForm(FlaskForm):
    """
    Form to create a UTub. Inherits from FlaskForm. All fields require data.

    Fields:
        name (Stringfield): Maximum 30 chars? TODO
    """

    name = StringField("UTub Name", validators=[InputRequired(), Length(min=1, max=30)])
    description = StringField("UTub Description", validators=[Length(max=500)])

    submit = SubmitField("Create UTub!")

    def validate_name(self, name):
        if name.data.replace(" ", "") == "":
            raise ValidationError("Name cannot contain only spaces or be empty.")


class UTubNewNameForm(FlaskForm):
    """
    Form to edit a UTub name. Inherits from FlaskForm. All fields require data.

    Fields:
        name (Stringfield): Maximum 30 chars? TODO
    """

    name = StringField("UTub Name", validators=[InputRequired(), Length(min=1, max=30)])

    submit = SubmitField("Edit UTub title!")

    def validate_name(self, name):
        if name.data.replace(" ", "") == "":
            raise ValidationError("Name cannot contain only spaces or be empty.")


class UTubDescriptionForm(FlaskForm):
    """
    Form to add a description to the UTub.

    To pre-populate forms:
    https://stackoverflow.com/questions/35892144/pre-populate-an-edit-form-with-wtforms-and-flask

    Fields:
        utub_description (Stringfield): Maximum 500 chars? TODO
    """

    # Not required, so as to allow the User to delete the description
    description = StringField("UTub Description", validators=[Length(max=500)])

    submit = SubmitField("Add Description To UTub!")

    def validate_description(self, description):
        if description.data is None:
            return

        if description.data.replace(" ", "") == "":
            description.data = ""
