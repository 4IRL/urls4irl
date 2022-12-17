from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import Length, InputRequired, ValidationError

class UTubNewUrlTagForm(FlaskForm):
    """
    Form to add a tag to a URL in a Utub.

    Fields:
        tag_string (Stringfield): Maximum 30 chars? TODO
    """
    
    tag_string = StringField('Tag', validators=[InputRequired(), Length(min=1, max=30)])

    submit = SubmitField('Add tag to this URL!')
    
    def validate_tag_string(self, tag_string):
        """Validates tag is not empty strings"""
        if tag_string.data.replace(' ', '') == '':
            raise ValidationError('Tag must not be empty.')
            
    #TODO Add tag validation (PG filter?)
    