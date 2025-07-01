from src.utils.strings.json_strs import FAILURE_GENERAL
from src.utils.strings.url_strs import URL_GENERAL
from src.utils.strings.utub_strs import UTUB_GENERAL

# Strings for users/members success
MEMBER_REMOVED = "Member removed."
MEMBER_ADDED = "Member added."
MEMBER_ID_ADDED = "userID"
MEMBER_ID_REMOVED = MEMBER_ID_ADDED
USER_REGISTERED = "User registered."
MEMBER = "member"
MEMBER_DELETE_WARNING = (
    "This member will no longer have access to the URLs in this UTub."
)
MEMBER_LEAVE_WARNING = "You will no longer have access to the URLs in this UTub."


class MEMBER_SUCCESS(URL_GENERAL, UTUB_GENERAL):
    MEMBER_REMOVED = MEMBER_REMOVED
    MEMBER_ADDED = MEMBER_ADDED
    MEMBER_ID_REMOVED = MEMBER_ID_REMOVED
    MEMBER_ID_ADDED = MEMBER_ID_ADDED
    USER_REGISTERED = USER_REGISTERED
    MEMBER = MEMBER


# Strings for users/members errors
UNABLE_TO_LOGIN = "Unable to login user."
UNABLE_TO_REGISTER = "Unable to register user."
CREATOR_CANNOT_REMOVE_THEMSELF = "UTub creator cannot remove themselves."
INVALID_PERMISSION_TO_REMOVE = "Not allowed to remove a member from this UTub."
INVALID_PERMISSION_TO_ADD = "Not allowed to add a member to this UTub."
MEMBER_NOT_IN_UTUB = "Member does not exist or not found in this UTub."
MEMBER_ALREADY_IN_UTUB = "Member already in UTub."
UNABLE_TO_ADD_MEMBER = "Unable to add that member to this UTub."
EMAIL_TAKEN = "That email address is already in use."
USERNAME_TAKEN = "That username is already taken. Please choose another."
USER_NOT_EXIST = "That user does not exist. Note this is case sensitive."
INVALID_PASSWORD = "Invalid password."
ACCOUNT_CREATED_EMAIL_NOT_VALIDATED = "An account already exists with that information but the email has not been validated."
INVALID_EMAIL = "Email is not valid."


class USER_FAILURE(FAILURE_GENERAL):
    UNABLE_TO_LOGIN = UNABLE_TO_LOGIN
    UNABLE_TO_REGISTER = UNABLE_TO_REGISTER
    EMAIL_TAKEN = EMAIL_TAKEN
    USERNAME_TAKEN = USERNAME_TAKEN
    USER_NOT_EXIST = USER_NOT_EXIST
    ACCOUNT_CREATED_EMAIL_NOT_VALIDATED = ACCOUNT_CREATED_EMAIL_NOT_VALIDATED
    INVALID_PASSWORD = INVALID_PASSWORD
    INVALID_EMAIL = INVALID_EMAIL


class MEMBER_FAILURE(FAILURE_GENERAL):
    CREATOR_CANNOT_REMOVE_THEMSELF = CREATOR_CANNOT_REMOVE_THEMSELF
    INVALID_PERMISSION_TO_REMOVE = INVALID_PERMISSION_TO_REMOVE
    INVALID_PERMISSION_TO_ADD = INVALID_PERMISSION_TO_ADD
    MEMBER_NOT_IN_UTUB = MEMBER_NOT_IN_UTUB
    MEMBER_ALREADY_IN_UTUB = MEMBER_ALREADY_IN_UTUB
    UNABLE_TO_ADD_MEMBER = UNABLE_TO_ADD_MEMBER
