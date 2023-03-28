from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import Length, InputRequired

class UTubNewURLForm(FlaskForm):
    """
    Form to add a URL to a UTub. Inherits from FlaskForm.

    Fields:
        URL (Stringfield): Required. Maximum 2000 chars? TODO
        URL Description (Stringfield): Not required. Maximum 100 chars? TODO
    """
    
    url_string = StringField('URL', validators=[InputRequired(), Length(min=1, max=2000)])
    url_description = StringField('URL Description', validators=[InputRequired(), Length(min=1, max=100)])

    submit = SubmitField('Add URL to this UTub!')

class UTubEditURLForm(FlaskForm):
    """
    Form to edit a URL in this UTub. Inherits from FlaskForm.

    Fields:
        URL (Stringfield): Required. Maximum 2000 chars? TODO
        url_description (Stringfield): Maximum 140 characters?
    """
    
    url_string = StringField('URL', validators=[InputRequired(), Length(min=1, max=2000)])
    url_description = StringField('URL Description', validators=[Length(max=140)])

    submit = SubmitField('Edit URL!')

    def validate_url_description(self, url_description):
        if url_description.data is None:
            return

        if url_description.data.replace(" ", "") == "":
            url_description.data = ""


class UTubEditURLDescriptionForm(FlaskForm):
    """
    Form to edit a URL in this UTub. Inherits from FlaskForm.

    Fields:
        url_description (Stringfield): Required. Maximum 2000 chars? TODO
    """
    
    url_description = StringField('URL Description', validators=[Length(max=140)])

    submit = SubmitField('Edit URL Description!')
