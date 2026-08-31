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
MEMBER_ROLE_MODIFIED = "Member role updated."
OWNERSHIP_TRANSFERRED = "UTub ownership transferred."
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
# Update-preferences 200 banner copy (server-sourced envelope text — surfaced
# dynamically off xhr.responseJSON.message; no JS bridge). Mirrors the
# change-username success/no-op pair.
PREFERENCES_CHANGE_SUCCESS = "Your display preferences have been saved."
PREFERENCES_CHANGE_NO_CHANGE = "No change — those are already your preferences."
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
# Delete-account 200 banner copy (server-sourced envelope text — surfaced
# dynamically off xhr.responseJSON.message; no JS bridge). The irreversible
# erasure success message shown before navigating to splash post-logout.
ACCOUNT_DELETED_SUCCESS = (
    "Your account has been permanently deleted. We're sorry to see you go."
)
# Log-out-everywhere 200 banner copy (server-sourced envelope text — surfaced
# dynamically off xhr.responseJSON.message; no JS bridge). Non-destructive
# session revocation: the acting session dies too (D-4), so the client navigates
# to splash after showing this message.
LOGOUT_EVERYWHERE_SUCCESS = (
    "You've been signed out on all devices. Log back in to continue."
)
# Data-export 200 envelope banner copy (server-sourced envelope text — surfaced
# off xhr.responseJSON.message; no JS bridge, mirroring the bare
# LOGOUT_EVERYWHERE_SUCCESS constant form rather than a USER_SUCCESS class
# member, since this file has no such class). The frontend export controller
# writes its own in-panel status copy (SETTINGS_EXPORT_*, Step 4); this is the
# response envelope's message field.
DATA_EXPORT_SUCCESS = "Your data export is ready."
# Typed-username confirmation mismatch copy (400 field error on ``confirmUsername``,
# DD-C) — the server re-check of the typed phrase, defense-in-depth against a
# client-gated-only submit.
DELETE_CONFIRMATION_MISMATCH = (
    "The username you typed doesn't match. Type your exact username to confirm."
)
MEMBER_DELETE_WARNING = (
    "This member will no longer have access to the URLs in this UTub."
)
MEMBER_LEAVE_WARNING = "You will no longer have access to the URLs in this UTub."
MEMBER_SEARCH_NO_RESULTS = "No members found"
MEMBER_SEARCH_PLACEHOLDER = "Filter members"
MEMBER_SEARCH_COUNT_TEMPLATE = "{{ visible }} of {{ total }} members shown"

# Grant/revoke co-owner (role.ts). Client-authored confirm-modal copy + menu-item
# labels + row-action announcements, so they take the full 5-file string bridge.
# Two complete-sentence success templates (DD-19) — never a {{role}} ternary.
MAKE_CO_OWNER_ACTION = "Make co-owner"
REVOKE_CO_OWNER_ACTION = "Revoke co-owner"
MAKE_CO_OWNER_TITLE = "Make this member a co-owner?"
MAKE_CO_OWNER_WARNING = (
    "Co-owners can add and remove members and manage this UTub's URLs."
)
REVOKE_CO_OWNER_TITLE = "Revoke this member's co-owner status?"
REVOKE_CO_OWNER_WARNING = (
    "This member will return to a regular member with no management access."
)
MEMBER_ROLE_CHANGE_GRANT_SUCCESS = "{{ username }} is now a co-owner."
MEMBER_ROLE_CHANGE_REVOKE_SUCCESS = "{{ username }} is no longer a co-owner."

# Ownership-transfer UI (transfer.ts / transfer-picker.ts). Client-authored
# picker + confirm-modal copy + row-action announcements + the delete-flow
# "Transfer instead" redirect label, so they take the full 5-file string bridge
# like the co-owner action labels above. Templated tokens use {{ username }},
# client-substituted via .replace("{{ username }}", …) exactly like role.ts.
TRANSFER_OWNER_ACTION = "Transfer ownership"
TRANSFER_OWNER_PICKER_TITLE = "Transfer ownership to…"
TRANSFER_OWNER_FILTER_PLACEHOLDER = "Filter members…"
TRANSFER_OWNER_NO_MATCHES = "No members match your search."
TRANSFER_OWNER_NO_ELIGIBLE = (
    "This UTub has no other members to transfer to. Add a member first."
)
TRANSFER_OWNER_SUBMIT = "Transfer ownership"
TRANSFER_OWNER_LISTBOX_ARIA = "Choose a member to transfer ownership to"
TRANSFER_OWNER_CONFIRM_TITLE = "Transfer ownership of this UTub?"
TRANSFER_OWNER_CONFIRM_WARNING = (
    "You'll hand ownership to {{ username }} and stay on as a co-owner. Only "
    "the new owner can transfer it back."
)
TRANSFER_OWNER_CONFIRM_SUBMIT = "Transfer to {{ username }}"
TRANSFER_OWNER_SUCCESS = "{{ username }} is now the owner. You're a co-owner."
TRANSFER_INSTEAD_ACTION = "Transfer instead"

# Kebab (overflow) row-action strings (members.ts). Client-authored: the
# "Remove member" menu-item text and the per-row kebab aria-label (a
# {{ username }} template resolved client-side), so they take the full 5-file
# string bridge like the co-owner action labels above.
MEMBER_REMOVE_ACTION = "Remove member"
MEMBER_ROW_ACTIONS_ARIA_LABEL = "Actions for {{ username }}"

# Add-member combobox (member-combobox.ts). Distinct from the MEMBER_SEARCH_*
# strings above, which belong to the client-side member-list FILTER, not this
# add-member typeahead.
MEMBER_ADD_LABEL = "Add member"
MEMBER_ADD_PLACEHOLDER = "Add a member by username"
MEMBER_ADD_SUBMIT = "Add"
MEMBER_ADD_LOADING_HINT = "Loading matches…"
MEMBER_ADD_NO_COMEMBERS_HINT = "No shared members yet — type a username to add"
MEMBER_ADD_ALREADY_MEMBER_HINT = '"{{ username }}" is already a member'
MEMBER_ADD_OUTSIDER_LABEL = 'Add "{{ username }}" by username'
MEMBER_ADD_SHARES_COUNT_ONE = "shares 1 UTub"
MEMBER_ADD_SHARES_COUNT = "shares {n} UTubs"
# "Add N" batch-submit label (Step 6). MEMBER_ADD_SUBMIT ("Add") is the disabled
# zero-staged base; this carries the staged count once ≥1 chip is staged.
MEMBER_ADD_SUBMIT_COUNT = "Add {n}"
# Batched aria-live count summary (Step 6): a brief count recap announced once
# after the whole batch settles (e.g. "3 members added, 2 members couldn't be
# added"). Per-chip ✓/✗ markers carry the specifics; 429-skipped chips are
# excluded from the counts. Singular/plural pair mirrors TAGS_MATCH_COUNT(_ONE).
MEMBER_ADD_SUMMARY_ADDED_ONE = "1 member added"
MEMBER_ADD_SUMMARY_ADDED = "{{ count }} members added"
MEMBER_ADD_SUMMARY_FAILED_ONE = "1 member couldn't be added"
MEMBER_ADD_SUMMARY_FAILED = "{{ count }} members couldn't be added"


class MEMBER_SUCCESS(URL_GENERAL, UTUB_GENERAL):
    MEMBER_REMOVED = MEMBER_REMOVED
    MEMBER_ADDED = MEMBER_ADDED
    MEMBER_ROLE_MODIFIED = MEMBER_ROLE_MODIFIED
    OWNERSHIP_TRANSFERRED = OWNERSHIP_TRANSFERRED
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
# Generic invalid-form-input error for the grant/revoke co-owner endpoint (the
# 400 INVALID_FORM_INPUT copy — missing/bad `member_role`). Distinct from the
# more specific CANNOT_MODIFY_OWNER_ROLE (400, targeting the owner) and
# MEMBER_NOT_IN_UTUB (404). Mirrors the UNABLE_TO_ADD_MEMBER pattern.
UNABLE_TO_MODIFY_MEMBER_ROLE = "Unable to modify that member's role in this UTub."
# Guard copy (400) returned when the grant/revoke endpoint targets the UTub's
# literal owner (the creator's role cannot be changed).
CANNOT_MODIFY_OWNER_ROLE = "Cannot change the UTub owner's role."
# Integrity-guard copy (403) returned by the remove-member endpoint when anyone
# other than the literal owner themselves attempts to remove the owner. Prevents
# orphaning UTub ownership (Utubs.utub_creator pointing at a deleted membership).
# Distinct from CREATOR_CANNOT_REMOVE_THEMSELF (400, owner removing self).
CANNOT_REMOVE_OWNER = "The UTub owner cannot be removed."
# Generic 400 error_message for the transfer-ownership endpoint (invalid/missing
# `new_owner_id` body). Mirrors the UNABLE_TO_MODIFY_MEMBER_ROLE pattern.
UNABLE_TO_TRANSFER_OWNERSHIP = "Unable to transfer ownership of this UTub."
# Guard copy (400) returned by the transfer-ownership endpoint when the target
# member is already the UTub owner (a no-op transfer to self).
TARGET_ALREADY_OWNER = "That member is already the UTub owner."
# Per-user per-day add-member cap copy. Fail-open anti-abuse counter that bounds
# username-oracle probing; not a security boundary. Mirrors
# USERNAME_CHANGE_RATE_LIMITED.
MEMBER_ADD_RATE_LIMITED = "You've added too many members today. Please try again later."
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
# Sole-admin guard copy (403) used by the delete endpoint (DD-21): the last
# active admin cannot remove their own account, since doing so would leave the
# portal with zero admins. Mirrors the admin portal's last-admin-forbidden
# invariant but self-scoped.
SOLE_ADMIN_CANNOT_LEAVE = (
    "You're the only active admin. Assign another admin before removing your "
    "account."
)
# OAuth-proof round-trip 200 banner copy (DD-6) returned by the delete
# endpoint's OAuth-only branch: a password-less account re-consents through an
# already-linked provider before the removal completes. Server-sourced envelope
# text (no JS bridge); pairs with ``AccountRemovalResponseSchema`` as the
# response type for the removal flow.
OAUTH_PROOF_REDIRECT_PENDING = "Re-authenticate with your linked provider to continue."


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
    DELETE_CONFIRMATION_MISMATCH = DELETE_CONFIRMATION_MISMATCH


class ACCOUNT_AUDIT_ACTIONS:
    """Users-domain audit action constants for self-service account actions.

    The users-domain equivalent of ``ADMIN_AUDIT_ACTIONS`` (kept as its own
    constant rather than imported from ``admin_portal_strs.py``, per the Step-2
    import-direction rule — the users domain does not import admin-module
    strings), so the ``AuditLogs`` trail distinguishes an admin-initiated erase
    (``ADMIN_AUDIT_ACTIONS.USER_ERASE``) from a self-service account deletion
    (``SELF_ACCOUNT_ERASE``, DD-4).
    """

    SELF_ACCOUNT_ERASE: str = "user.account.self_erase"


class MEMBER_FAILURE(FAILURE_GENERAL):
    CREATOR_CANNOT_REMOVE_THEMSELF = CREATOR_CANNOT_REMOVE_THEMSELF
    INVALID_PERMISSION_TO_REMOVE = INVALID_PERMISSION_TO_REMOVE
    INVALID_PERMISSION_TO_ADD = INVALID_PERMISSION_TO_ADD
    MEMBER_NOT_IN_UTUB = MEMBER_NOT_IN_UTUB
    MEMBER_ALREADY_IN_UTUB = MEMBER_ALREADY_IN_UTUB
    UNABLE_TO_ADD_MEMBER = UNABLE_TO_ADD_MEMBER
    UNABLE_TO_MODIFY_MEMBER_ROLE = UNABLE_TO_MODIFY_MEMBER_ROLE
    CANNOT_MODIFY_OWNER_ROLE = CANNOT_MODIFY_OWNER_ROLE
    CANNOT_REMOVE_OWNER = CANNOT_REMOVE_OWNER
    UNABLE_TO_TRANSFER_OWNERSHIP = UNABLE_TO_TRANSFER_OWNERSHIP
    TARGET_ALREADY_OWNER = TARGET_ALREADY_OWNER
    MEMBER_ADD_RATE_LIMITED = MEMBER_ADD_RATE_LIMITED
