from src.utils.strings.email_validation_strs import EXPIRATION
from src.utils.strings.form_strs import GENERAL_FORM
from src.utils.strings.splash_form_strs import EMAIL_TEXT
from src.utils.strings.user_strs import INVALID_EMAIL

# Strings for Forgot Password form
SEND_PASSWORD_RESET_EMAIL = "Send Password Reset Email"
EMAIL_SENT_MESSAGE = (
    "If you entered a valid email, you should receive a reset password link soon."
)


class FORGOT_PASSWORD(GENERAL_FORM):
    EMAIL_TEXT = EMAIL_TEXT
    EMAIL_SENT_MESSAGE = EMAIL_SENT_MESSAGE
    SEND_PASSWORD_RESET_EMAIL = SEND_PASSWORD_RESET_EMAIL
    INVALID_EMAIL = INVALID_EMAIL


RESET_PASSWORD_KEY = "reset_password"
NEW_PASSWORD = "New Password"
NEW_PASSWORD_FIELD = "new_password"
CONFIRM_NEW_PASSWORD_FIELD = "confirm_new_password"
CONFIRM_NEW_PASSWORD = "Confirm New Password"
RESET_YOUR_PASSWORD = "Reset your password"
RESET_PASSWORD_MODAL_CALL = "resetPasswordModalOpener"
RESET_PASSWORD_INVALID = "Could not reset the password."
SAME_PASSWORD = "Invalid password. Try another password."
PASSWORD_RESET = "Password reset."
PASSWORDS_NOT_IDENTICAL = "Passwords are not identical."


class RESET_PASSWORD(GENERAL_FORM):
    RESET_PASSWORD_KEY = RESET_PASSWORD_KEY
    EXPIRATION = EXPIRATION
    NEW_PASSWORD = NEW_PASSWORD
    NEW_PASSWORD_FIELD = NEW_PASSWORD_FIELD
    CONFIRM_NEW_PASSWORD_FIELD = CONFIRM_NEW_PASSWORD_FIELD
    CONFIRM_NEW_PASSWORD = CONFIRM_NEW_PASSWORD
    RESET_YOUR_PASSWORD = RESET_YOUR_PASSWORD
    RESET_PASSWORD_MODAL_CALL = RESET_PASSWORD_MODAL_CALL
    RESET_PASSWORD_INVALID = RESET_PASSWORD_INVALID
    SAME_PASSWORD = SAME_PASSWORD
    PASSWORD_RESET = PASSWORD_RESET
    PASSWORDS_NOT_IDENTICAL = PASSWORDS_NOT_IDENTICAL