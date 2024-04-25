ERRORS = "errors"
STATUS = "status"
MESSAGE = "message"
ERROR_CODE = "errorCode"
FAILURE = "Failure"
SUCCESS = "Success"
NO_CHANGE = "No change"
TOO_MANY_REQUESTS = "Too many requests."


class STD_JSON_RESPONSE:
    ERRORS = ERRORS
    STATUS = STATUS
    MESSAGE = MESSAGE
    ERROR_CODE = ERROR_CODE
    FAILURE = FAILURE
    SUCCESS = SUCCESS
    NO_CHANGE = NO_CHANGE
    TOO_MANY_REQUESTS = TOO_MANY_REQUESTS


# Strings for general failure, included in JSON message
NOT_AUTHORIZED = "Not authorized."
FIELD_REQUIRED = ["This field is required."]
EMAIL_VALIDATED = "Email_validated"
SOMETHING_WENT_WRONG = "Something went wrong."
REDIRECT = "redirect"


class FAILURE_GENERAL:
    NOT_AUTHORIZED = NOT_AUTHORIZED
    FIELD_REQUIRED = FIELD_REQUIRED
    REDIRECT = REDIRECT
    EMAIL_VALIDATED = EMAIL_VALIDATED
    SOMETHING_WENT_WRONG = SOMETHING_WENT_WRONG
