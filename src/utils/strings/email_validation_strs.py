from src.utils.strings.json_strs import FAILURE_GENERAL
from src.utils.strings.form_strs import EMAIL

VALIDATE_EMAIL = "validate_email"
EXPIRATION = "exp"
ALGORITHM = "HS256"
EMAIL_VALIDATED_SESS_KEY = "email_validated"
EMAIL_VALIDATION_MODAL_CALL = "emailValidation.js"
TOKEN_EXPIRED = "Your token expired. Please try again."
EMAIL_SENT = "Email sent!"
EMAIL_FAILED = "Email could not be sent."
BASE_API_URL = "https://api.us.mailjet.com/"
EMAIL_SIGNATURE = "URLS4IRL Team"
MESSAGES, FROM, TO, NAME = "Messages", "From", "To", "Name"
SUBJECT, TEXTPART, HTMLPART = "Subject", "TextPart", "HTMLPart"
ACCOUNT_CONFIRMATION_SUBJECT = "URLS4IRL Account Confirmation"
PASSWORD_RESET_SUBJECT = "URLS4IRL Password Reset"
SANDBOXMODE = "SandboxMode"
MAILJET_STATUS_CODE = "StatusCode"
MAILJET_ERROR_MESSAGE = "ErrorMessage"
MAILJET_ERROR_CODE = "ErrorCode"
MAILJET_ERROR_RELATED_TO = "ErrorRelatedTo"
MAILJET_ERRORS = "Errors"
ERROR_WITH_MAILJET = "Error with Mailjet service."
INVALID_EMAIL_INPUT = "Invalid email address."


# Email related strings
class EMAILS:
    VALIDATE_EMAIL = VALIDATE_EMAIL
    EXPIRATION = EXPIRATION
    ALGORITHM = ALGORITHM
    EMAIL = EMAIL
    EMAIL_VALIDATED_SESS_KEY = EMAIL_VALIDATED_SESS_KEY
    EMAIL_SENT = EMAIL_SENT
    EMAIL_VALIDATION_MODAL_CALL = EMAIL_VALIDATION_MODAL_CALL
    TOKEN_EXPIRED = TOKEN_EXPIRED
    BASE_API_URL = BASE_API_URL
    SUBJECT, TEXTPART, HTMLPART = SUBJECT, TEXTPART, HTMLPART
    MESSAGES, FROM, TO, NAME = MESSAGES, FROM, TO, NAME
    EMAIL_SIGNATURE = EMAIL_SIGNATURE
    ACCOUNT_CONFIRMATION_SUBJECT = ACCOUNT_CONFIRMATION_SUBJECT
    SANDBOXMODE = SANDBOXMODE
    MAILJET_STATUSCODE = MAILJET_STATUS_CODE
    MAILJET_ERROR_MESSAGE = MAILJET_ERROR_MESSAGE
    MAILJET_ERROR_CODE = MAILJET_ERROR_CODE
    MAILJET_ERROR_RELATED_TO = MAILJET_ERROR_RELATED_TO
    MAILJET_ERRORS = MAILJET_ERRORS
    EMAIL_FAILED = EMAIL_FAILED
    ERROR_WITH_MAILJET = ERROR_WITH_MAILJET
    PASSWORD_RESET_SUBJECT = PASSWORD_RESET_SUBJECT


# Strings for email validation errors
USER_INVALID_EMAIL = "User has not validated their email."
TOO_MANY_ATTEMPTS_MAX = "Too many attempts, please wait 1 hour."
TOO_MANY_ATTEMPTS = " attempts left. Please wait 1 minute before sending another email."
ATTEMPTS = "attempts"


class EMAILS_FAILURE(FAILURE_GENERAL):
    USER_INVALID_EMAIL = USER_INVALID_EMAIL
    TOO_MANY_ATTEMPTS = TOO_MANY_ATTEMPTS
    TOO_MANY_ATTEMPTS_MAX = TOO_MANY_ATTEMPTS_MAX
    ATTEMPTS = ATTEMPTS
    INVALID_EMAIL_INPUT = INVALID_EMAIL_INPUT
