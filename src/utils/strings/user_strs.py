from src.utils.strings.json_strs import FAILURE_GENERAL
from src.utils.strings.url_strs import URL_GENERAL
from src.utils.strings.utub_strs import UTUB_GENERAL

# Strings for users success
USER_REMOVED = "User removed."
USER_ADDED = "User added."
USER_ID_REMOVED = "User_ID_removed"
USER_ID_ADDED = "User_ID_added"
USER_REGISTERED = "User registered."
USERNAME_REMOVED = "Username"


class USER_SUCCESS(URL_GENERAL, UTUB_GENERAL):
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
