from backend.utils.strings.json_strs import FAILURE_GENERAL

# Server-side messages for the invite link manager API (create / update / replace /
# revoke). Server messages only: nothing here is bridged to TypeScript.

# Strings for invite link success
INVITE_LINK_CREATED = "Invite link created."
INVITE_LINK_UPDATED = "Invite link updated."
INVITE_LINK_REPLACED = "Invite link replaced."
INVITE_LINK_REVOKED = "Invite link revoked."
INVITE_LINK_JOINED = "Joined UTub."
INVITE_LINK_ALREADY_MEMBER = "Already a member of this UTub."


class INVITE_LINK_SUCCESS:
    INVITE_LINK_CREATED = INVITE_LINK_CREATED
    INVITE_LINK_UPDATED = INVITE_LINK_UPDATED
    INVITE_LINK_REPLACED = INVITE_LINK_REPLACED
    INVITE_LINK_REVOKED = INVITE_LINK_REVOKED
    JOINED = INVITE_LINK_JOINED
    ALREADY_MEMBER = INVITE_LINK_ALREADY_MEMBER


# Public invite page copy (rendered by Jinja; Playwright asserts it via ui_testing_strs).
INVITE_PAGE_EYEBROW_TEMPLATE = "{inviter} invited you to join"


class INVITE_LINK_PAGE:
    EYEBROW_TEMPLATE = INVITE_PAGE_EYEBROW_TEMPLATE
    JOIN_HINT = "You'll join as a member and can add URLs and tags."
    LOGIN_HINT = (
        "URLS4IRL is a shared space for collecting and tagging links. Create a free "
        "account or log in to join; you'll land right in this UTub."
    )
    DEAD_HEADING = "This invite has expired or doesn't exist"
    DEAD_HINT = (
        "Invite links expire and can be revoked by the people who manage the UTub. "
        "Ask the person who sent it for a new link."
    )
    UNVALIDATED_HEADING = "Confirm your email to join"
    UNVALIDATED_MESSAGE = (
        "Confirm your email address using the link we sent you, then open this "
        "invite link again."
    )
    LOGIN_MESSAGE = "You're logged out. Log in to join this UTub."
    CSRF_HEADING = "This page expired"
    CSRF_MESSAGE = "Reload this invite link and try again."
    RATE_LIMIT_HEADING = "Too many attempts"
    RATE_LIMIT_MESSAGE = "Wait a minute, then reload this invite link and try again."
    BACK_TO_INVITE = "Back to the invite"
    TITLE_JOIN = "Join a UTub - URLS4IRL"
    TITLE_UNVALIDATED = "Confirm your email - URLS4IRL"
    TITLE_DEAD = "Invite unavailable - URLS4IRL"
    TITLE_CSRF = "Page expired - URLS4IRL"
    TITLE_RATE_LIMIT = "Too many attempts - URLS4IRL"


# Strings for invite link failure
INVITE_LINK_NOT_FOUND_MESSAGE = "This UTub has no active invite link."
INVALID_INVITE_LINK_INPUT = "Unable to process the invite link settings."
UTUB_IS_LOCKED_MESSAGE = "Invite links can't be changed while this UTub is locked."
LIVE_LINK_EXISTS_MESSAGE = "This UTub already has a live invite link."
DEAD_LINK_UPDATE_MESSAGE = (
    "This invite link has expired or can no longer be used. Replace it instead."
)
USES_BELOW_JOINED_MESSAGE = (
    "The use limit can't be lower than the number of people who already joined."
)


class INVITE_LINK_FAILURE(FAILURE_GENERAL):
    INVITE_LINK_NOT_FOUND = INVITE_LINK_NOT_FOUND_MESSAGE
    INVALID_FORM_INPUT = INVALID_INVITE_LINK_INPUT
    UTUB_IS_LOCKED = UTUB_IS_LOCKED_MESSAGE
    LIVE_LINK_EXISTS = LIVE_LINK_EXISTS_MESSAGE
    DEAD_LINK_UPDATE = DEAD_LINK_UPDATE_MESSAGE
    USES_BELOW_JOINED = USES_BELOW_JOINED_MESSAGE
