# Strings for standardizing the JSON response
ERRORS = "Errors"
STATUS = "Status"
MESSAGE = "Message"
ERROR_CODE = "Error_code"
FAILURE = "Failure"
SUCCESS = "Success"
NO_CHANGE = "No change"
BASE_URL = "https://urls4irl.app/"


class STD_JSON_RESPONSE:
    ERRORS = ERRORS
    STATUS = STATUS
    MESSAGE = MESSAGE
    ERROR_CODE = ERROR_CODE
    FAILURE = FAILURE
    SUCCESS = SUCCESS
    NO_CHANGE = NO_CHANGE


# Strings for all forms
CSRF_TOKEN = "csrf_token"


class GENERAL_FORM:
    CSRF_TOKEN = CSRF_TOKEN


# Strings for login/register forms
USERNAME = "username"
EMAIL = "email"
CONFIRM_EMAIL = "confirm_email"
PASSWORD = "password"
CONFIRM_PASSWORD = "confirm_password"
USERNAME_TEXT = "Username"
EMAIL_TEXT = "Email"
CONFIRM_EMAIL_TEXT = "Confirm Email"
PASSWORD_TEXT = "Password"
CONFIRM_PASSWORD_TEXT = "Confirm Password"
REGISTER = "Register"
LOGIN = "Login"
SEND_EMAIL_VALIDATION = "Send Validation Email"
SEND_PASSWORD_RESET_EMAIL = "Send Password Reset Email"


class REGISTER_LOGIN_FORM(GENERAL_FORM):
    EMAIL = EMAIL
    USERNAME = USERNAME
    PASSWORD = PASSWORD
    USERNAME_TEXT = USERNAME_TEXT
    EMAIL_TEXT = EMAIL_TEXT
    CONFIRM_EMAIL_TEXT = CONFIRM_EMAIL_TEXT
    PASSWORD_TEXT = PASSWORD_TEXT
    CONFIRM_PASSWORD_TEXT = CONFIRM_PASSWORD_TEXT
    REGISTER = REGISTER
    LOGIN = LOGIN
    SEND_EMAIL_VALIDATION = SEND_EMAIL_VALIDATION
    SEND_PASSWORD_RESET_EMAIL = SEND_PASSWORD_RESET_EMAIL


class REGISTER_FORM(REGISTER_LOGIN_FORM):
    CONFIRM_EMAIL = CONFIRM_EMAIL
    CONFIRM_PASSWORD = CONFIRM_PASSWORD
    REGISTER_FORM_KEYS = (USERNAME, EMAIL, CONFIRM_EMAIL, PASSWORD, CONFIRM_PASSWORD)


class LOGIN_FORM(REGISTER_LOGIN_FORM):
    LOGIN_FORM_KEYS = (USERNAME, PASSWORD)


# Strings for general success, included in JSON message
UTUB_ID = "UTub_ID"
UTUB_NAME = "UTub_name"
UTUB_USERS = "UTub_users"
UTUB_DESCRIPTION = "UTub_description"
URL = "URL"
REDIRECT = "redirect"


class SUCCESS_GENERAL:
    UTUB_ID = UTUB_ID
    UTUB_NAME = UTUB_NAME
    UTUB_USERS = UTUB_USERS
    URL = URL
    REDIRECT = REDIRECT


# Strings for general failure, included in JSON message
NOT_AUTHORIZED = "Not authorized."
FIELD_REQUIRED = ["This field is required."]
EMAIL_VALIDATED = "Email_validated"
SOMETHING_WENT_WRONG = "Something went wrong."


class FAILURE_GENERAL:
    NOT_AUTHORIZED = NOT_AUTHORIZED
    FIELD_REQUIRED = FIELD_REQUIRED
    REDIRECT = REDIRECT
    EMAIL_VALIDATED = EMAIL_VALIDATED
    SOMETHING_WENT_WRONG = SOMETHING_WENT_WRONG


# Strings for users success
USER_REMOVED = "User removed."
USER_ADDED = "User added."
USER_ID_REMOVED = "User_ID_removed"
USER_ID_ADDED = "User_ID_added"
USER_REGISTERED = "User registered."
USERNAME_REMOVED = "Username"


class USER_SUCCESS(SUCCESS_GENERAL):
    USER_REMOVED = USER_REMOVED
    USER_ADDED = USER_ADDED
    USER_ID_REMOVED = USER_ID_REMOVED
    USER_ID_ADDED = USER_ID_ADDED
    USERNAME_REMOVED = USERNAME_REMOVED
    USER_REGISTERED = USER_REGISTERED


# Strings for users errors
UNABLE_TO_LOGIN = "Unable to login user."
UNABLE_TO_REGISTER = "Unable to register user."
CREATOR_CANNOT_REMOVE_THEMSELF = "UTub creator cannot remove themselves."
INVALID_PERMISSION_TO_REMOVE = "Not allowed to remove a user from this UTub."
INVALID_PERMISSION_TO_ADD = "Not allowed to add a user to this UTub."
USER_NOT_IN_UTUB = "User does not exist or not found in this UTub."
USER_ALREADY_IN_UTUB = "User already in UTub."
UNABLE_TO_ADD = "Unable to add that user to this UTub."
EMAIL_TAKEN = "That email address is already in use."
USERNAME_TAKEN = "That username is already taken. Please choose another."
USER_NOT_EXIST = "That user does not exist. Note this is case sensitive."
INVALID_PASSWORD = "Invalid password."
ACCOUNT_CREATED_EMAIL_NOT_VALIDATED = "An account already exists with that information but the email has not been validated."
INVALID_EMAIL = "Email is not valid."


class USER_FAILURE(FAILURE_GENERAL):
    UNABLE_TO_LOGIN = UNABLE_TO_LOGIN
    UNABLE_TO_REGISTER = UNABLE_TO_REGISTER
    CREATOR_CANNOT_REMOVE_THEMSELF = CREATOR_CANNOT_REMOVE_THEMSELF
    INVALID_PERMISSION_TO_REMOVE = INVALID_PERMISSION_TO_REMOVE
    INVALID_PERMISSION_TO_ADD = INVALID_PERMISSION_TO_ADD
    USER_NOT_IN_UTUB = USER_NOT_IN_UTUB
    USER_ALREADY_IN_UTUB = USER_ALREADY_IN_UTUB
    UNABLE_TO_ADD = UNABLE_TO_ADD
    EMAIL_TAKEN = EMAIL_TAKEN
    USERNAME_TAKEN = USERNAME_TAKEN
    USER_NOT_EXIST = USER_NOT_EXIST
    ACCOUNT_CREATED_EMAIL_NOT_VALIDATED = ACCOUNT_CREATED_EMAIL_NOT_VALIDATED
    INVALID_PASSWORD = INVALID_PASSWORD
    INVALID_EMAIL = INVALID_EMAIL


# Strings for URL success
URL_STRING = "url_string"
URL_ID = "url_ID"
URL_DESCRIPTION = "url_description"
ADDED_BY = "Added_by"
URL_CREATED_ADDED = "New URL created and added to UTub."
URL_ADDED = "URL added to UTub."
URL_REMOVED = "URL removed from this UTub."
URL_DESC_MODIFIED = "URL description was modified."
URL_OR_DESC_MODIFIED = "URL and/or URL description modified."


class URL_SUCCESS(SUCCESS_GENERAL):
    URL_ADDED = URL_ADDED
    URL_STRING = URL_STRING
    URL_ID = URL_ID
    URL_DESCRIPTION = URL_DESCRIPTION
    ADDED_BY = ADDED_BY
    URL_REMOVED = URL_REMOVED
    URL_CREATED_ADDED = URL_CREATED_ADDED
    URL_DESC_MODIFIED = URL_DESC_MODIFIED
    URL_OR_DESC_MODIFIED = URL_OR_DESC_MODIFIED


# Strings for URL failure
UNABLE_TO_REMOVE_URL = "Unable to remove this URL."
UNABLE_TO_ADD_URL = "Unable to add this URL."
URL_IN_UTUB = "URL already in UTub."
UNABLE_TO_ADD_URL_FORM = "Unable to add this URL, please check inputs."
UNABLE_TO_MODIFY_URL_FORM = "Unable to modify this URL, please check inputs."
UNABLE_TO_MODIFY_URL = "Unable to modify this URL."
EMPTY_URL = "URL cannot be empty."


class URL_FAILURE(FAILURE_GENERAL):
    UNABLE_TO_ADD_URL = UNABLE_TO_ADD_URL
    UNABLE_TO_REMOVE_URL = UNABLE_TO_REMOVE_URL
    URL_IN_UTUB = URL_IN_UTUB
    UNABLE_TO_ADD_URL_FORM = UNABLE_TO_ADD_URL_FORM
    UNABLE_TO_MODIFY_URL = UNABLE_TO_MODIFY_URL
    EMPTY_URL = EMPTY_URL
    UNABLE_TO_MODIFY_URL_FORM = UNABLE_TO_MODIFY_URL_FORM
    URL_DESCRIPTION = URL_DESCRIPTION


# Strings for URL no change
URL_AND_DESC_NOT_MODIFIED = "URL and URL description were not modified."


class URL_NO_CHANGE:
    URL_AND_DESC_NOT_MODIFIED = URL_AND_DESC_NOT_MODIFIED


# Strings for tags success
TAG_ADDED_TO_URL = "Tag added to this URL."
TAG_REMOVED_FROM_URL = "Tag removed from this URL."
TAG_MODIFIED_ON_URL = "Tag on this URL modified."
COUNT_IN_UTUB = "Count_in_UTub"
TAG = "Tag"


class TAGS_SUCCESS(SUCCESS_GENERAL):
    TAG_ADDED_TO_URL = TAG_ADDED_TO_URL
    TAG_REMOVED_FROM_URL = TAG_REMOVED_FROM_URL
    TAG = TAG
    COUNT_IN_UTUB = COUNT_IN_UTUB
    TAG_MODIFIED_ON_URL = TAG_MODIFIED_ON_URL


# Strings for tags failure
UNABLE_TO_ADD_TAG_TO_URL = "Unable to add tag to URL."
FIVE_TAGS_MAX = "URLs can only have up to 5 tags."
TAG_ALREADY_ON_URL = "URL already has this tag."
ONLY_UTUB_MEMBERS_REMOVE_TAGS = "Only UTub members can remove tags."
ONLY_UTUB_MEMBERS_MODIFY_TAGS = "Only UTub members can modify tags."


class TAGS_FAILURE(FAILURE_GENERAL):
    UNABLE_TO_ADD_TAG_TO_URL = UNABLE_TO_ADD_TAG_TO_URL
    FIVE_TAGS_MAX = FIVE_TAGS_MAX
    TAG_ALREADY_ON_URL = TAG_ALREADY_ON_URL
    ONLY_UTUB_MEMBERS_MODIFY_TAGS = ONLY_UTUB_MEMBERS_MODIFY_TAGS
    ONLY_UTUB_MEMBERS_REMOVE_TAGS = ONLY_UTUB_MEMBERS_REMOVE_TAGS


# Strings for tags no change
TAG_NOT_MODIFIED = "Tag was not modified on this URL."


class TAGS_NO_CHANGE:
    TAG_NOT_MODIFIED = TAG_NOT_MODIFIED


# Strings for utub success
UTUB_CREATOR_ID = "UTub_creator_id"
UTUB_DELETED = "UTub deleted."


class UTUB_SUCCESS(SUCCESS_GENERAL):
    UTUB_DESCRIPTION = UTUB_DESCRIPTION
    UTUB_CREATOR_ID = UTUB_CREATOR_ID
    UTUB_DELETED = UTUB_DELETED


# Strings for utub failure
UNABLE_TO_MAKE_UTUB = "Unable to make a UTub with that information."
UNABLE_TO_MODIFY_UTUB_NAME = "Unable to modify this UTub's name."
UNABLE_TO_MODIFY_UTUB_DESC = "Unable to modify this UTub's description."
UTUB_DESC_TOO_LONG = "UTub description is too long."
UTUB_DESC_FIELD_TOO_LONG = ["Field cannot be longer than 500 characters."]
UTUB_NAME_FIELD_INVALID = ["Field must be between 1 and 30 characters long."]


class UTUB_FAILURE(FAILURE_GENERAL):
    UTUB_DESCRIPTION = UTUB_DESCRIPTION
    UNABLE_TO_MODIFY_UTUB_NAME = UNABLE_TO_MODIFY_UTUB_NAME
    UNABLE_TO_MAKE_UTUB = UNABLE_TO_MAKE_UTUB
    UNABLE_TO_MODIFY_UTUB_DESC = UNABLE_TO_MODIFY_UTUB_DESC
    UTUB_DESC_TOO_LONG = UTUB_DESC_TOO_LONG
    UTUB_DESC_FIELD_TOO_LONG = UTUB_DESC_FIELD_TOO_LONG
    UTUB_NAME_FIELD_INVALID = UTUB_NAME_FIELD_INVALID


# Strings for standardizing the model serialization
ID = "id"
NAME = "name"
URL_TAGS = "url_tags"
TAGGED_URL = "tagged_url"
CREATED_BY = "created_by"
CREATED_AT = "created_at"
DESCRIPTION = "description"
MEMBERS = "members"
URLS = "urls"
TAG_STRING = "tag_string"
TAGS = "tags"


class MODELS:
    ID = ID
    NAME = NAME
    URL_ID = URL_ID
    URL_TAGS = URL_TAGS
    URL_STRING = URL_STRING
    ADDED_BY = ADDED_BY
    URL_DESCRIPTION = URL_DESCRIPTION
    TAGGED_URL = TAGGED_URL
    USERNAME = USERNAME
    TAG = TAG
    CREATED_AT = CREATED_AT
    CREATED_BY = CREATED_BY
    DESCRIPTION = DESCRIPTION
    MEMBERS = MEMBERS
    URLS = URLS
    TAGS = TAGS
    URL = URL
    TAG_STRING = TAG_STRING
    UTUB_DESCRIPTION = UTUB_DESCRIPTION


class TAG_FORM(GENERAL_FORM):
    TAG_STRING = TAG_STRING


class URL_FORM(GENERAL_FORM):
    URL_STRING = URL_STRING
    URL_DESCRIPTION = URL_DESCRIPTION


class ADD_USER_FORM(GENERAL_FORM):
    USERNAME = USERNAME


class UTUB_FORM(GENERAL_FORM):
    NAME = NAME
    DESCRIPTION = DESCRIPTION


UTUB_DESCRIPTION_FOR_FORM = "utub_description"


class UTUB_DESCRIPTION_FORM(GENERAL_FORM):
    UTUB_DESCRIPTION = UTUB_DESCRIPTION
    UTUB_DESCRIPTION_FOR_FORM = UTUB_DESCRIPTION_FOR_FORM


VALIDATE_EMAIL = "validate_email"
EXPIRATION = "exp"
ALGORITHM = "HS256"
EMAIL_VALIDATED_SESS_KEY = "email_validated"
EMAIL_VALIDATION_MODAL_CALL = "emailValidationModalOpener"
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


RESET_PASSWORD_KEY = "reset_password"
NEW_PASSWORD = "New Password"
NEW_PASSWORD_FIELD = "new_password"
CONFIRM_NEW_PASSWORD = "Confirm New Password"
RESET_YOUR_PASSWORD = "Reset your password"
EMAIL_SENT_MESSAGE = (
    "If you entered a valid email, you should receive a reset password link soon."
)
RESET_PASSWORD_MODAL_CALL = "resetPasswordModalOpener"
RESET_PASSWORD_INVALID = "Could not reset the password."
SAME_PASSWORD = "Invalid password. Try another password."
PASSWORD_RESET = "Password reset."


class RESET_PASSWORD:
    RESET_PASSWORD_KEY = RESET_PASSWORD_KEY
    EXPIRATION = EXPIRATION
    NEW_PASSWORD = NEW_PASSWORD
    NEW_PASSWORD_FIELD = NEW_PASSWORD_FIELD
    CONFIRM_NEW_PASSWORD = CONFIRM_NEW_PASSWORD
    RESET_YOUR_PASSWORD = RESET_YOUR_PASSWORD
    EMAIL_SENT_MESSAGE = EMAIL_SENT_MESSAGE
    RESET_PASSWORD_MODAL_CALL = RESET_PASSWORD_MODAL_CALL
    RESET_PASSWORD_INVALID = RESET_PASSWORD_INVALID
    SAME_PASSWORD = SAME_PASSWORD
    PASSWORD_RESET = PASSWORD_RESET


# Config Env vars labels
class CONFIG_ENVS:
    DATABASE_URL_DEV = "DATABASE_URL_DEV"
    DATABASE_URL_TEST = "DATABASE_URL_TEST"
    SECRET_KEY = "SECRET_KEY"
    MAILJET_SECRET_KEY = "MAILJET_SECRET_KEY"
    MAILJET_API_KEY = "MAILJET_API_KEY"
    BASE_EMAIL = "BASE_EMAIL"
