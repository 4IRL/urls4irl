from backend.utils.strings.json_strs import FAILURE_GENERAL
from backend.utils.strings.model_strs import UTUB_DESCRIPTION
from backend.utils.strings.user_settings_strs import USER_SETTINGS_STRINGS

# Strings for utub success
UTUB_ID = "utubID"
UTUB_ID_QUERY_PARAM = "UTubID"
UTUB_NO_LONGER_AVAILABLE = "The UTub you tried to open is no longer available"
MOBILE_PANEL_QUERY_PARAM = "panel"
MOBILE_PANEL_ANNOUNCEMENT_UTUBS = "Now showing UTub list"
MOBILE_PANEL_ANNOUNCEMENT_URLS = "Now showing URLs"
MOBILE_PANEL_ANNOUNCEMENT_MEMBERS = "Now showing Members"
MOBILE_PANEL_ANNOUNCEMENT_TRASH = "Now showing Trash"
UTUB_NAME = "utubName"
UTUB_USERS = "utubUsers"
UTUB_CREATOR_ID = "utubCreatorID"
UTUB_DELETED = "UTub deleted."
UTUB_CREATE_SAME_NAME = "You already have a UTub with a similar name."
UTUB_UPDATE_SAME_NAME = "You are a member of a UTub with an identical name."
UTUB_DELETE_WARNING = "This action is irreversible!"
UTUB_CREATE_MSG = "Create a UTub"
UTUB_SELECT = "Select a UTub"
UTUB_SEARCH_NO_RESULTS = "No UTubs found"
UTUB_SEARCH_PLACEHOLDER = "Filter UTubs"
UTUB_SEARCH_COUNT_TEMPLATE = "{{ visible }} of {{ total }} UTubs shown"
# Visually-hidden text placed inside the selected UTub row so assistive tech
# announces the selection (rendered by Jinja as data-selected-label).
UTUB_SELECTED_ANNOUNCEMENT = "selected"
# Transient "Saved ✓" acknowledgment shown next to a field after a successful
# per-field save on the mobile consolidated edit panels (UTub header + URL card).
# Shared across all four fields; the "✓" glyph is decorative markup, not bridged.
FIELD_SAVED = "Saved"
# Per-field labels prepended to FIELD_SAVED in the polite aria-live announcer
# (e.g. "UTub name Saved") so assistive tech states which field was saved.
FIELD_SAVED_LABEL_UTUB_NAME = "UTub name"
FIELD_SAVED_LABEL_UTUB_DESCRIPTION = "UTub description"
FIELD_SAVED_LABEL_URL_TITLE = "URL title"
FIELD_SAVED_LABEL_URL = "URL"
# Polite aria-live announcement written to #fieldSavedAnnouncement when a
# newly-created URL card is re-sorted away from its top-of-list insertion point
# (create-time default-sort visual exception) so assistive tech states the add.
URL_ADDED_ANNOUNCEMENT = "URL added"
# Desktop hover-tooltip titles (and matching aria-labels) for the icon-only UTub
# deck-header and create-form buttons. Jinja-rendered, so these are backend
# constants only — they are never bridged through generate_strings_js().
DELETE_UTUB_TOOLTIP = "Delete UTub"
LEAVE_UTUB_TOOLTIP = "Leave UTub"
FILTER_UTUB_NAMES_TOOLTIP = "Filter UTub names"
CREATE_UTUB_TOOLTIP = "Create UTub"
CREATE_UTUB_CANCEL_TOOLTIP = "Cancel"
# aria-label only — #utubBtnCreate is an onboarding-nudge anchor and deliberately
# gets NO tooltip (a shared Bootstrap instance would break the nudge sequence).
CREATE_UTUB_ARIA_LABEL = "Create UTub"
# Panel settings shell: status text, live-region announcements, scope labels and
# read-only notes. All are written by TS, so all are bridged.
PANEL_SETTINGS_SAVING = "Saving…"
PANEL_SETTINGS_SAVED = "Saved"
PANEL_SETTINGS_REVERTED = "Couldn't save — reverted"
PANEL_SETTINGS_SAVE_FAILED = "Couldn't save"
PANEL_SETTINGS_CLOSED = "Settings closed"
PANEL_SETTINGS_UTUB_LOCKED = "UTub is locked"
PANEL_SETTINGS_MANAGERS_ONLY = "Only UTub managers can change this"
PANEL_SETTINGS_SCOPE_UTUB = "Shared with this UTub"
PANEL_SETTINGS_SCOPE_USER = "Just for you"
PANEL_SETTINGS_EMPTY = "No settings available"
# URLs panel "New URLs" settings section: written by TS, so all are bridged.
URLS_SETTINGS_SECTION_TITLE = "New URLs"
URLS_SETTINGS_DEFAULT_SCHEME_LABEL = "Default scheme"
URLS_SETTINGS_DEFAULT_SCHEME_DESC = "New URLs start with this scheme."
URLS_SETTINGS_HIDE_LABEL = "Hide scheme selector"
URLS_SETTINGS_HIDE_DESC = "Members see the scheme as a note under the URL field."
URLS_SETTINGS_HIDE_REQUIRES_HTTPS = "Only available when the default is https."
URLS_SETTINGS_SELECTOR_RESTORED = (
    "Scheme selector shown again because the default is no longer https."
)
URLS_SETTINGS_ALLOW_SHORT_LINKS_LABEL = "Allow short links"
URLS_SETTINGS_ALLOW_SHORT_LINKS_DESC = (
    "Turning this off removes Copy short link for every member. "
    "Existing short links keep working until they expire or are revoked."
)
URLS_SETTINGS_SHORT_LINKS_OFF_NOTICE = "Short links turned off"
URLS_SETTINGS_SHORT_LINKS_ON_NOTICE = "Short links turned on"
# URLs panel "Your view of this UTub" section: written by TS, so all are bridged.
URLS_PERSONAL_SETTINGS_SECTION_TITLE = "Your view of this UTub"
URLS_PERSONAL_SETTINGS_SORT_LABEL = "Sort URLs"
URLS_PERSONAL_SETTINGS_VIEW_LABEL = "Layout"
URLS_PERSONAL_SETTINGS_DENSITY_LABEL = "Density"
URLS_PERSONAL_SETTINGS_DENSITY_DESC = (
    "Compact spacing applies with a mouse or trackpad."
)
URLS_PERSONAL_SETTINGS_DEFAULT_OPTION_PREFIX = "Default: "
URLS_PERSONAL_SETTINGS_SORT_OPTION_NEWEST = (
    USER_SETTINGS_STRINGS.UI_SETTINGS_SORT_OPTION_NEWEST
)
URLS_PERSONAL_SETTINGS_SORT_OPTION_OLDEST = (
    USER_SETTINGS_STRINGS.UI_SETTINGS_SORT_OPTION_OLDEST
)
URLS_PERSONAL_SETTINGS_SORT_OPTION_TITLE_AZ = (
    USER_SETTINGS_STRINGS.UI_SETTINGS_SORT_OPTION_TITLE_AZ
)
URLS_PERSONAL_SETTINGS_VIEW_OPTION_LIST = (
    USER_SETTINGS_STRINGS.UI_SETTINGS_VIEW_OPTION_LIST
)
URLS_PERSONAL_SETTINGS_VIEW_OPTION_TITLE_LINE = "Title line"
URLS_PERSONAL_SETTINGS_VIEW_OPTION_URL_LINE = "URL line"
URLS_PERSONAL_SETTINGS_VIEW_OPTION_CARDS = (
    USER_SETTINGS_STRINGS.UI_SETTINGS_VIEW_OPTION_CARDS
)
URLS_PERSONAL_SETTINGS_DENSITY_OPTION_COMFORTABLE = (
    USER_SETTINGS_STRINGS.UI_SETTINGS_DENSITY_OPTION_COMFORTABLE
)
URLS_PERSONAL_SETTINGS_DENSITY_OPTION_COMPACT = "Compact"
URLS_PERSONAL_SETTINGS_HIDE_COPY_LABEL = "Hide Copy button"
URLS_PERSONAL_SETTINGS_HIDE_COPY_DESC = "Selecting several URLs can still copy them."
URLS_PERSONAL_SETTINGS_HIDE_SHORT_LINK_LABEL = "Hide Copy short link button"
URLS_PERSONAL_SETTINGS_HIDE_SHORT_LINK_DESC = "Existing short links and Revoke stay."
URLS_PERSONAL_SETTINGS_HIDE_DATE_LABEL = "Hide date added"
URLS_PERSONAL_SETTINGS_HIDE_DATE_DESC = '"Added by" names stay.'
URLS_PERSONAL_SETTINGS_DISABLE_SWIPE_LABEL = "Turn off swipe to delete"
URLS_PERSONAL_SETTINGS_DISABLE_SWIPE_DESC = (
    "On touch screens. The Delete button still works."
)
URLS_PERSONAL_SETTINGS_SHORT_LINKS_OFF_HINT = (
    "Short links are turned off for everyone in this UTub."
)
URLS_PERSONAL_SETTINGS_COPY_HIDDEN_NOTICE = "Copy button hidden"
URLS_PERSONAL_SETTINGS_COPY_SHOWN_NOTICE = "Copy button shown"
URLS_PERSONAL_SETTINGS_SHORT_LINK_HIDDEN_NOTICE = "Copy short link button hidden"
URLS_PERSONAL_SETTINGS_SHORT_LINK_SHOWN_NOTICE = "Copy short link button shown"
URLS_PERSONAL_SETTINGS_DATE_HIDDEN_NOTICE = "Date added hidden"
URLS_PERSONAL_SETTINGS_DATE_SHOWN_NOTICE = "Date added shown"
URLS_PERSONAL_SETTINGS_SWIPE_OFF_NOTICE = "Swipe to delete turned off"
URLS_PERSONAL_SETTINGS_SWIPE_ON_NOTICE = "Swipe to delete turned on"
URLS_PERSONAL_SETTINGS_SORT_ORDER_PENDING_NOTICE = "Order will update on next refresh"
URLS_PERSONAL_SETTINGS_SORT_SET_NOTICE_PREFIX = "Sort set to "
URLS_PERSONAL_SETTINGS_SORT_DEFAULT_NOTICE = "Sort uses your default"
URLS_PERSONAL_SETTINGS_VIEW_SET_NOTICE_PREFIX = "Layout set to "
URLS_PERSONAL_SETTINGS_VIEW_DEFAULT_NOTICE = "Layout uses your default"
URLS_PERSONAL_SETTINGS_DENSITY_SET_NOTICE_PREFIX = "Density set to "
URLS_PERSONAL_SETTINGS_DENSITY_DEFAULT_NOTICE = "Density uses your default"
# Gear aria-label/tooltip text: Jinja-only, asserted by a Python integration test, so
# backend constants only (not bridged to TS).
PANEL_SETTINGS_GEAR_UTUBS = "UTubs settings"
PANEL_SETTINGS_GEAR_MEMBERS = "Members settings"
PANEL_SETTINGS_GEAR_TAGS = "Tags settings"
PANEL_SETTINGS_GEAR_URLS = "URLs settings"
# Mobile sheet close button aria-label: Jinja-only, asserted by tests (not bridged).
PANEL_SETTINGS_CLOSE = "Close settings"


class UTUB_GENERAL:
    UTUB_ID = UTUB_ID
    UTUB_NAME = UTUB_NAME
    UTUB_USERS = UTUB_USERS
    UTUB_DESCRIPTION = UTUB_DESCRIPTION
    UTUB_ID_QUERY_PARAM = UTUB_ID_QUERY_PARAM


class UTUB_SUCCESS(UTUB_GENERAL):
    UTUB_CREATOR_ID = UTUB_CREATOR_ID
    UTUB_DELETED = UTUB_DELETED


# Strings for utub failure
UTUB_IS_LOCKED = "This UTub is locked and cannot be modified."
UTUB_UNLOCKED_ANNOUNCEMENT = "This UTub has been unlocked."
UNABLE_TO_MAKE_UTUB = "Unable to make a UTub with that information."
UNABLE_TO_MODIFY_UTUB_NAME = "Unable to modify UTub name."
UNABLE_TO_MODIFY_UTUB_DESC = "Unable to modify UTub description."
UNABLE_TO_MODIFY_UTUB_SETTINGS = "Unable to modify UTub settings."
HIDE_SCHEME_SELECTOR_REQUIRES_HTTPS = (
    "The scheme selector can only be hidden when the default scheme is https."
)
UTUB_DESC_TOO_LONG = "UTub description is too long."
UTUB_DESC_FIELD_TOO_LONG = ["Field cannot be longer than 500 characters."]
UTUB_NAME_FIELD_INVALID = ["Field must be between 1 and 30 characters long."]
UTUB_NAME_EMPTY = "Name cannot contain only spaces or be empty."


class UTUB_FAILURE(UTUB_GENERAL, FAILURE_GENERAL):
    UTUB_IS_LOCKED = UTUB_IS_LOCKED
    UNABLE_TO_MODIFY_UTUB_NAME = UNABLE_TO_MODIFY_UTUB_NAME
    UNABLE_TO_MAKE_UTUB = UNABLE_TO_MAKE_UTUB
    UNABLE_TO_MODIFY_UTUB_DESC = UNABLE_TO_MODIFY_UTUB_DESC
    UNABLE_TO_MODIFY_UTUB_SETTINGS = UNABLE_TO_MODIFY_UTUB_SETTINGS
    UTUB_DESC_TOO_LONG = UTUB_DESC_TOO_LONG
    UTUB_DESC_FIELD_TOO_LONG = UTUB_DESC_FIELD_TOO_LONG
    UTUB_NAME_FIELD_INVALID = UTUB_NAME_FIELD_INVALID
    UTUB_NAME_EMPTY = UTUB_NAME_EMPTY
