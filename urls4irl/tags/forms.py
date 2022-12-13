from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import Length, InputRequired

class UTubNewUrlTagForm(FlaskForm):
    """
    Form to add a tag to a URL in a Utub.

    Fields:
        tag_string (Stringfield): Maximum 30 chars? TODO
    """
    
    tag_string = StringField('Tag', validators=[InputRequired(), Length(min=1, max=30)])

    submit = SubmitField('Add tag to this URL!')

    #TODO Add tag validation (PG filter?)
    