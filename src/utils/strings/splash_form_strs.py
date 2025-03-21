from src.utils.strings.form_strs import GENERAL_FORM
from src.utils.strings.model_strs import EMAIL, PASSWORD, USERNAME

# Strings for login/register forms
CONFIRM_EMAIL = "confirmEmail"
CONFIRM_PASSWORD = "confirmPassword"
USERNAME_TEXT = "Username"
EMAIL_TEXT = "Email"
CONFIRM_EMAIL_TEXT = "Confirm Email"
PASSWORD_TEXT = "Password"
CONFIRM_PASSWORD_TEXT = "Confirm Password"
REGISTER = "Register"
LOGIN = "Login"
SEND_EMAIL_VALIDATION = "Resend Validation Email"


class REGISTER_LOGIN_FORM(GENERAL_FORM):
    USERNAME = USERNAME
    USERNAME_TEXT = USERNAME_TEXT
    EMAIL_TEXT = EMAIL_TEXT
    CONFIRM_EMAIL_TEXT = CONFIRM_EMAIL_TEXT
    PASSWORD_TEXT = PASSWORD_TEXT
    CONFIRM_PASSWORD_TEXT = CONFIRM_PASSWORD_TEXT
    REGISTER = REGISTER
    LOGIN = LOGIN
    SEND_EMAIL_VALIDATION = SEND_EMAIL_VALIDATION


class REGISTER_FORM(REGISTER_LOGIN_FORM):
    CONFIRM_EMAIL = CONFIRM_EMAIL
    CONFIRM_PASSWORD = CONFIRM_PASSWORD
    REGISTER_FORM_KEYS = (USERNAME, EMAIL, CONFIRM_EMAIL, PASSWORD, CONFIRM_PASSWORD)


class LOGIN_FORM(REGISTER_LOGIN_FORM):
    LOGIN_FORM_KEYS = (USERNAME, PASSWORD)
