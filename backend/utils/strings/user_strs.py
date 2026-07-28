from backend.utils.strings.json_strs import FAILURE_GENERAL
from backend.utils.strings.url_strs import URL_GENERAL
from backend.utils.strings.utub_strs import UTUB_GENERAL

# General strings
REDIRECT_URL = "redirectUrl"
COOKIE_BANNER_SEEN = "cookie_banner_seen=true"  # Both the name and value of the cookie
COOKIE_BANNER_KEY = COOKIE_BANNER_SEEN.split("=")[0]

# Flask session key stamped (as a UTC epoch float) by the user_logged_in
# signal handler on every login; compared against Users.sessionsInvalidatedAt
# by the user_loader to reject sessions issued before an invalidation.
SESSION_ISSUED_AT_KEY = "session_issued_at"

# Strings for users/members success
MEMBER_REMOVED = "Member removed."
MEMBER_ADDED = "Member added."
MEMBER_ID_ADDED = "userID"
MEMBER_ID_REMOVED = MEMBER_ID_ADDED
USER_REGISTERED = "User registered."
CONFIRM_EMAIL_SENT = (
    "Almost there — check your email for a link to confirm your account."
)
MEMBER = "member"
# Change-username 200 banner copy (server-sourced envelope text — DD-12; no JS
# bridge, surfaced dynamically off xhr.responseJSON.message).
USERNAME_CHANGE_SUCCESS = "Your username has been updated."
USERNAME_CHANGE_NO_CHANGE = "No change — that's already your username."
MEMBER_DELETE_WARNING = (
    "This member will no longer have access to the URLs in this UTub."
)
MEMBER_LEAVE_WARNING = "You will no longer have access to the URLs in this UTub."
MEMBER_SEARCH_NO_RESULTS = "No members found"
MEMBER_SEARCH_PLACEHOLDER = "Filter members"
MEMBER_SEARCH_COUNT_TEMPLATE = "{{ visible }} of {{ total }} members shown"


class MEMBER_SUCCESS(URL_GENERAL, UTUB_GENERAL):
    MEMBER_REMOVED = MEMBER_REMOVED
    MEMBER_ADDED = MEMBER_ADDED
    MEMBER_ID_REMOVED = MEMBER_ID_REMOVED
    MEMBER_ID_ADDED = MEMBER_ID_ADDED
    USER_REGISTERED = USER_REGISTERED
    CONFIRM_EMAIL_SENT = CONFIRM_EMAIL_SENT
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
INVALID_PASSWORD = "Invalid password. If you signed up using a third-party provider, this account may not have a password — use one of the sign-in options below."
INVALID_CREDENTIALS = "Invalid username or password."
ACCOUNT_CREATED_EMAIL_NOT_VALIDATED = "An account already exists with that information but the email has not been validated."
INVALID_EMAIL = "Email is not valid."
ACCOUNT_SUSPENDED = "This account has been suspended."
USERNAME_CHANGE_RATE_LIMITED = (
    "You've changed your username too many times today. Try again later."
)


class USER_FAILURE(FAILURE_GENERAL):
    UNABLE_TO_LOGIN = UNABLE_TO_LOGIN
    UNABLE_TO_REGISTER = UNABLE_TO_REGISTER
    EMAIL_TAKEN = EMAIL_TAKEN
    USERNAME_TAKEN = USERNAME_TAKEN
    USER_NOT_EXIST = USER_NOT_EXIST
    ACCOUNT_CREATED_EMAIL_NOT_VALIDATED = ACCOUNT_CREATED_EMAIL_NOT_VALIDATED
    INVALID_PASSWORD = INVALID_PASSWORD
    INVALID_CREDENTIALS = INVALID_CREDENTIALS
    INVALID_EMAIL = INVALID_EMAIL
    ACCOUNT_SUSPENDED = ACCOUNT_SUSPENDED
    USERNAME_CHANGE_RATE_LIMITED = USERNAME_CHANGE_RATE_LIMITED


class MEMBER_FAILURE(FAILURE_GENERAL):
    CREATOR_CANNOT_REMOVE_THEMSELF = CREATOR_CANNOT_REMOVE_THEMSELF
    INVALID_PERMISSION_TO_REMOVE = INVALID_PERMISSION_TO_REMOVE
    INVALID_PERMISSION_TO_ADD = INVALID_PERMISSION_TO_ADD
    MEMBER_NOT_IN_UTUB = MEMBER_NOT_IN_UTUB
    MEMBER_ALREADY_IN_UTUB = MEMBER_ALREADY_IN_UTUB
    UNABLE_TO_ADD_MEMBER = UNABLE_TO_ADD_MEMBER
