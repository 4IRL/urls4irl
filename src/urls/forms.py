from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import Length, InputRequired

from src.utils.strings.model_strs import MODELS


class NewURLForm(FlaskForm):
    """
    Form to add a URL to a UTub. Inherits from FlaskForm.

    Fields:
        URL (Stringfield): Required. Maximum 2000 chars? TODO
        URL Title (Stringfield): Not required. Maximum 100 chars? TODO
    """

    url_string = StringField(
        "URL", validators=[InputRequired(), Length(min=1, max=2000)], name=MODELS.URL_STRING
    )
    url_title = StringField(
        "URL Title", validators=[InputRequired(), Length(min=1, max=100)], name=MODELS.URL_TITLE
    )

    submit = SubmitField("Add URL to this UTub!")


class EditURLAndTitleForm(FlaskForm):
    """
    Form to edit a URL in this UTub. Inherits from FlaskForm.

    Fields:
        URL (Stringfield): Required. Maximum 2000 chars? TODO
        url_title (Stringfield): Maximum 140 characters?
    """

    url_string = StringField(
        "URL", validators=[InputRequired(), Length(min=1, max=2000)], name=MODELS.URL_STRING
    )
    url_title = StringField("URL Title", validators=[Length(max=140)], name=MODELS.URL_TITLE)

    submit = SubmitField("Edit URL!")

    def validate_url_title(self, url_title):
        if url_title.data is None:
            return

        if url_title.data.replace(" ", "") == "":
            url_title.data = ""


class EditURLForm(FlaskForm):
    """
    Form to edit a URL in this UTub. Inherits from FlaskForm.

    Fields:
        URL (Stringfield): Required. Maximum 2000 chars? TODO
    """

    url_string = StringField(
        "URL", validators=[InputRequired(), Length(min=1, max=2000)], name=MODELS.URL_STRING
    )

    submit = SubmitField("Edit URL!")


class EditURLTitleForm(FlaskForm):
    """
    Form to edit a URL in this UTub. Inherits from FlaskForm.

    Fields:
        url_title (Stringfield): Required. Maximum 2000 chars? TODO
    """

    url_title = StringField("URL Title", validators=[InputRequired(), Length(max=140)], name=MODELS.URL_TITLE)

    submit = SubmitField("Edit URL Title!")
