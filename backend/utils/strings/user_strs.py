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
# Change-password 200 banner copy (server-sourced envelope text — surfaced
# dynamically off xhr.responseJSON.message; no JS bridge).
PASSWORD_CHANGE_SUCCESS = (
    "Your password has been updated. You've been signed out of all other devices."
)
# Change-email confirm-outcome banner copy (server-sourced; no JS bridge —
# rendered into pages/splash.html and pages/home.html by build_email_change_banner
# off the confirm route's redirect query param, and asserted by the Python UI/
# integration tests). DD-12: login is username-only, so the success copy must not
# tell the user to "log in with your new email" — the login credential never
# changes. DD-15: the HOME (already-logged-in) render path drops the login clause
# entirely, since telling a logged-in viewer to "log in as usual" contradicts the
# page they are already on.
EMAIL_CHANGE_SUCCESS = (
    "Your email address has been updated. Your username hasn't changed — "
    "log in as usual to continue."
)
EMAIL_CHANGE_SUCCESS_AUTHENTICATED = "Your email address has been updated."
EMAIL_CHANGE_CONFIRM_INVALID = "That confirmation link is invalid or has expired."
EMAIL_CHANGE_CONFIRM_TAKEN = "That email address is no longer available."
# The single confirm-outcome query param key the confirm route redirects back
# with (DD-1). A shared wire constant: the backend reads it (splash_page / home /
# RECOGNIZED_HOME_QUERY_PARAMS) AND the frontend must recognize it so the /home
# pageshow guard does not treat the forwarded param as malformed (DD-9). Sourced
# here (a leaf strings module) so it can be JS-bridged via generate_strings_js()
# without a splash-service import cycle; re-exported from change_email.py, which
# owns the closed set of outcome *codes* that ride this param.
EMAIL_CHANGE_STATUS_QUERY_PARAM = "email_change_status"
# Change-email START endpoint (PUT /users/<id>/email) banner copy (server-sourced
# envelope text — surfaced dynamically off xhr.responseJSON.message; no JS bridge).
EMAIL_CHANGE_CONFIRMATION_SENT = (
    "We've sent a confirmation link to your new email address. Click it to "
    "finish changing your email."
)
EMAIL_CHANGE_NO_CHANGE = "That's already your email address."
# Deactivate-account 200 banner copy (server-sourced envelope text — surfaced
# dynamically off xhr.responseJSON.message; no JS bridge). The reversible-pause
# success message the client shows before navigating to splash post-logout.
ACCOUNT_DEACTIVATED_SUCCESS = (
    "Your account has been deactivated. Log back in anytime to reactivate it."
)
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
# Per-day email-change send cap copy (429). Distinct from the re-auth
# brute-force lockout copy (TOO_MANY_PASSWORD_ATTEMPTS): hitting the daily cap is
# not a wrong-password event. Mirrors USERNAME_CHANGE_RATE_LIMITED.
EMAIL_CHANGE_RATE_LIMITED = (
    "You've requested too many email changes today. Try again later."
)
# Dedicated change-password re-auth failure copy (Decision #9). NOT a reuse of
# INVALID_PASSWORD, whose text carries an OAuth-signup clause that does not
# apply to this authenticated re-auth check (the OAuth-only case is handled by
# the separate OAUTH_ONLY_NO_PASSWORD guard).
CURRENT_PASSWORD_INCORRECT = "Current password is incorrect."
# OAuth-only guard copy for the change-password endpoint (defense-in-depth:
# the template hides the form for password-less accounts).
PASSWORD_CHANGE_OAUTH_ONLY = (
    "Password change isn't available for accounts that sign in with Google or "
    "GitHub."
)
# OAuth-only guard copy for the change-email START endpoint (defense-in-depth:
# the template hides the form for password-less accounts). A dedicated sibling
# of PASSWORD_CHANGE_OAUTH_ONLY so the copy names the email flow specifically.
EMAIL_CHANGE_OAUTH_ONLY = (
    "Email change isn't available for accounts that sign in with Google or GitHub."
)
# Shared brute-force lockout copy (DD-1) returned with HTTP 429 by BOTH re-auth
# gates — change-password and the settings OAuth-link password re-auth — once a
# per-user failure counter trips. Reused for both (the settings-link copy does
# not need to differ from the change-password copy).
TOO_MANY_PASSWORD_ATTEMPTS = (
    "Too many incorrect password attempts. Please try again later."
)
# Sole-admin guard copy (403) shared by the deactivate + delete endpoints
# (DD-21): the last active admin cannot remove their own account, since doing so
# would leave the portal with zero admins. Mirrors the admin portal's
# last-admin-forbidden invariant but self-scoped.
SOLE_ADMIN_CANNOT_LEAVE = (
    "You're the only active admin. Assign another admin before removing your "
    "account."
)
# Interim-stub copy (DD-3) returned with HTTP 501 by the deactivate + delete
# endpoints' OAuth-only branch until Step 5 wires the OAuth-proof round-trip.
# Shared by both removal flows; retired with the stub in Step 5 (DD-16).
OAUTH_ONLY_REMOVAL_NOT_YET_AVAILABLE = (
    "Account removal for accounts that sign in with Google or GitHub isn't "
    "available yet. Please check back soon."
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
    EMAIL_CHANGE_RATE_LIMITED = EMAIL_CHANGE_RATE_LIMITED
    CURRENT_PASSWORD_INCORRECT = CURRENT_PASSWORD_INCORRECT
    PASSWORD_CHANGE_OAUTH_ONLY = PASSWORD_CHANGE_OAUTH_ONLY
    EMAIL_CHANGE_OAUTH_ONLY = EMAIL_CHANGE_OAUTH_ONLY
    TOO_MANY_PASSWORD_ATTEMPTS = TOO_MANY_PASSWORD_ATTEMPTS
    SOLE_ADMIN_CANNOT_LEAVE = SOLE_ADMIN_CANNOT_LEAVE
    OAUTH_ONLY_REMOVAL_NOT_YET_AVAILABLE = OAUTH_ONLY_REMOVAL_NOT_YET_AVAILABLE


class MEMBER_FAILURE(FAILURE_GENERAL):
    CREATOR_CANNOT_REMOVE_THEMSELF = CREATOR_CANNOT_REMOVE_THEMSELF
    INVALID_PERMISSION_TO_REMOVE = INVALID_PERMISSION_TO_REMOVE
    INVALID_PERMISSION_TO_ADD = INVALID_PERMISSION_TO_ADD
    MEMBER_NOT_IN_UTUB = MEMBER_NOT_IN_UTUB
    MEMBER_ALREADY_IN_UTUB = MEMBER_ALREADY_IN_UTUB
    UNABLE_TO_ADD_MEMBER = UNABLE_TO_ADD_MEMBER
