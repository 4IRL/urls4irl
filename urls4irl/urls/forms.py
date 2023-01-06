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

    #TODO Add validation for the URL here..


class UTubEditURLForm(FlaskForm):
    """
    Form to edit a URL in this UTub. Inherits from FlaskForm.

    Fields:
        URL (Stringfield): Required. Maximum 2000 chars? TODO
    """
    
    url_string = StringField('URL', validators=[Length(min=1, max=2000)])

    submit = SubmitField('Edit URL!')

    #TODO Add validation for the URL here..


class UTubEditURLDescriptionForm(FlaskForm):
    """
    Form to edit a URL in this UTub. Inherits from FlaskForm.

    Fields:
        URL (Stringfield): Required. Maximum 2000 chars? TODO
    """
    
    url_description = StringField('URL Description', validators=[Length(min=1, max=100)])

    submit = SubmitField('Edit URL Description!')
