from flask_wtf import FlaskForm
from wtforms import SubmitField

from backend.utils.strings.splash_form_strs import REGISTER_LOGIN_FORM


class ValidateEmailForm(FlaskForm):
    submit = SubmitField(REGISTER_LOGIN_FORM.SEND_EMAIL_VALIDATION)
