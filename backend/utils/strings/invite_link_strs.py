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
class INVITE_LINK_PAGE:
    EYEBROW_TEMPLATE = "{inviter} invited you to join"
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
    LOGIN_MESSAGE = "You're logged out. Log in to join this UTub."
    CSRF_HEADING = "This page expired"
    CSRF_MESSAGE = "Reload this invite link and try again."
    RATE_LIMIT_HEADING = "Too many attempts"
    RATE_LIMIT_MESSAGE = "Wait a minute, then reload this invite link and try again."
    BACK_TO_INVITE = "Back to the invite"
    JOINING_LABEL = "Joining..."
    JOIN_LABEL = "Join UTub"
    NOT_NOW_LABEL = "Not now"
    GO_TO_APP_LABEL = "Go to URLS4IRL"
    TITLE_JOIN = "Join a UTub - URLS4IRL"
    TITLE_DEAD = "Invite unavailable - URLS4IRL"
    TITLE_CSRF = "Page expired - URLS4IRL"
    TITLE_RATE_LIMIT = "Too many attempts - URLS4IRL"
    PREVIEW_BADGE_LABEL = "Read-only preview"
    PREVIEW_URL_COUNT_ONE = "1 URL"
    PREVIEW_URL_COUNT_TEMPLATE = "{count} URLs"
    PREVIEW_AVAILABLE_UNTIL = "available until"
    PREVIEW_MORE_TEMPLATE = "and {count} more, join to see all"
    PREVIEW_EMPTY = "This UTub has no URLs yet. Join to add the first one."
    PREVIEW_BAR_HEADING = "Want to add your own links?"
    PREVIEW_BAR_TEMPLATE = "Create a free account to join {utub_name}."
    PREVIEW_BAR_LABEL = "Join this UTub"
    PREVIEW_NEW_TAB = "(opens in a new tab)"
    PREVIEW_SKIP_LINK = "Skip to join options"


# Legal copy about the invite link preview (rendered by Jinja into the Terms and the
# Privacy Policy; Python tests assert it via ui_testing_strs). Not bridged to TypeScript.
class INVITE_LINK_LEGAL:
    TERMS_PREVIEW = (
        "UTub owners and co-owners can turn on a time-limited preview that lets "
        "anyone with the UTub's invite link view its name, description, URLs, titles "
        "and tags without an account; member names are never shown."
    )
    PRIVACY_PREVIEW = (
        "If a UTub's owner or co-owner turns on an invite link preview, anyone with "
        "that link can view the UTub's name, description, URLs, titles and tags, "
        "without an account, until the preview ends; member usernames and other "
        "personal information are never included."
    )


# Copy the Members-deck invite link panel renders from TypeScript. Bridged to
# APP_CONFIG.strings with an INVITE_LINK_PANEL_ key prefix (see STRINGS /
# generate_strings_js()). "{name}" placeholders are filled client-side.
class INVITE_LINK_PANEL:
    HEADING = "Invite link"
    LOADING = "Loading invite link…"
    LOAD_FAILED = "Couldn't load the invite link."
    TRY_AGAIN = "Try again"
    EMPTY_HINT = "Anyone with the link can join this UTub as a member."
    EXPIRES_LABEL = "Expires"
    USES_LABEL = "Uses"
    EXPIRES_IN_1 = "in 1 day"
    EXPIRES_IN_7 = "in 7 days"
    EXPIRES_IN_30 = "in 30 days"
    EXPIRES_FROM_NOW_1 = "1 day from now"
    EXPIRES_FROM_NOW_7 = "7 days from now"
    EXPIRES_FROM_NOW_30 = "30 days from now"
    USES_UNLIMITED = "Unlimited"
    USES_ONE = "1 use"
    USES_MANY = "{count} uses"
    CREATE_LINK = "Create link"
    COPY = "Copy"
    LINK_LABEL = "Invite link URL"
    NEW_LINK = "New link"
    REVOKE = "Revoke"
    META_CREATED_BY = "Created by {user}"
    META_EXPIRES = "expires {date}"
    META_JOINED = "{count} joined"
    USES_FLOOR_HINT_ONE = "1 person has joined, so the limit can't go below 1."
    USES_FLOOR_HINT = "{count} people have joined, so the limit can't go below {count}."
    DEAD_EXPIRED = "This link expired on {date}."
    DEAD_USED_UP = "This link reached its limit of {uses}."
    DEAD_CREATOR_DEMOTED = (
        "This link stopped working because the person who made it is no longer "
        "an owner or co-owner."
    )
    DEAD_CREATOR_NOT_ALLOWED = (
        "This link stopped working because its creator is no longer allowed "
        "to create invite links."
    )
    DEAD_UNKNOWN = "This invite link no longer works."
    CREATE_NOT_ALLOWED = "You can no longer create invite links in this UTub."
    PREVIEW_OWNER_ONLY_HINT = (
        "Only the UTub owner can turn on previews or change their length."
    )
    FORCED_CLOSE = (
        "The invite link panel closed because you can no longer manage this "
        "UTub's invite link."
    )
    MANAGE_LOST = "You can no longer manage this UTub's invite link."
    ERROR_GENERIC = "Something went wrong. Try again."
    CANCEL = "Cancel"
    CREATED = "Invite link created."
    REPLACED = "New invite link created. The old link no longer works."
    REVOKED = "Invite link revoked."
    RESYNC_REVOKED = "This invite link was already revoked."
    RESYNC_LIVE_EXISTS = "This UTub already has a live invite link."
    CONFIRM_GROUP_LABEL = "Confirm invite link action"
    CONFIRM_REVOKE_QUESTION = (
        "Revoke this link? It stops working right away. "
        "People who already joined stay in the UTub."
    )
    CONFIRM_REVOKE_ACTION = "Revoke link"
    CONFIRM_NEW_QUESTION = (
        "Make a new link? The current link stops working. "
        "People who already joined stay in the UTub."
    )
    CONFIRM_NEW_ACTION = "Make new link"
    COPIED = "Copied"
    COPY_SUCCESS = "Invite link copied."
    COPY_FALLBACK = (
        "Couldn't copy automatically. The link is selected: press Ctrl+C (⌘C on Mac)."
    )
    SAVING = "Saving…"
    EXPIRES_SET = "Link now expires {date}."
    USES_SET = "Use limit set to {label}."
    RESYNC_DEAD_UPDATE = "This invite link no longer works."
    USES_BELOW_JOINED_ONE = "1 person has already joined. Choose a limit of at least 1."
    USES_BELOW_JOINED = (
        "{count} people have already joined. Choose a limit of at least {count}."
    )
    PREVIEW_WINDOW_OFF_HINT = "It applies when you turn the preview on."
    PREVIEW_LABEL = "Preview for visitors without an account"
    PREVIEW_DESC = (
        "Shows this UTub's name, description, URLs, titles and tags, read-only."
    )
    PREVIEW_WINDOW_LABEL = "Preview length"
    PREVIEW_WINDOW_DAYS_ONE = "1 day"
    PREVIEW_WINDOW_DAYS = "{days} days"
    PREVIEW_WINDOW_CAPPED_OPTION = "Until {date} (link expiry)"
    PREVIEW_WINDOW_LIMIT_HINT = (
        "Lengths longer than the time left on the link are unavailable."
    )
    PREVIEW_WINDOW_CAPPED_HINT = (
        "The preview can't outlast the link. You chose {label}; "
        "lengthening Expires brings that back."
    )
    PREVIEW_WARNING = (
        "Anyone with this link can view this UTub's name, description, URLs, "
        "titles and tags without an account until {date}. "
        "Member names are never shown."
    )
    PREVIEW_ON = "Preview on until {date}."
    PREVIEW_OFF = "Preview off."
    PREVIEW_WINDOW_SET = "Preview length set to {label}. " + PREVIEW_WINDOW_OFF_HINT
    PREVIEW_ENDS_SET = "Preview now ends {date}."
    PREVIEW_CAPPED = "Preview now ends {date}, when the link expires."


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
CREATE_NOT_ALLOWED_MESSAGE = "You can't create or change invite links in this UTub."
PREVIEW_NOT_ALLOWED_MESSAGE = "Only the UTub owner can turn on previews."


class INVITE_LINK_FAILURE(FAILURE_GENERAL):
    INVITE_LINK_NOT_FOUND = INVITE_LINK_NOT_FOUND_MESSAGE
    INVALID_FORM_INPUT = INVALID_INVITE_LINK_INPUT
    UTUB_IS_LOCKED = UTUB_IS_LOCKED_MESSAGE
    LIVE_LINK_EXISTS = LIVE_LINK_EXISTS_MESSAGE
    DEAD_LINK_UPDATE = DEAD_LINK_UPDATE_MESSAGE
    USES_BELOW_JOINED = USES_BELOW_JOINED_MESSAGE
    CREATE_NOT_ALLOWED = CREATE_NOT_ALLOWED_MESSAGE
    PREVIEW_NOT_ALLOWED = PREVIEW_NOT_ALLOWED_MESSAGE
