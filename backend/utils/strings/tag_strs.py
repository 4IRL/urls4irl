from backend.utils.strings.json_strs import FAILURE_GENERAL
from backend.utils.strings.model_strs import UTUB_TAG, TAG_COUNTS_MODIFIED
from backend.utils.strings.url_strs import URL_GENERAL
from backend.utils.strings.utub_strs import UTUB_GENERAL

# Strings for tags success
TAG_ADDED_TO_URL = "Tag added to this URL."
TAGS_ADDED_TO_URL = "Tags added to this URL."
TAGS_ADDED_TO_URLS = "Tags added to selected URLs."
TAG_ADDED_TO_UTUB = "Tag added to this UTub."
TAG_REMOVED_FROM_URL = "Tag removed from this URL."
TAG_REMOVED_FROM_UTUB = "Tag removed from UTub and associated URLs."
TAG_MODIFIED_ON_URL = "Tag on this URL modified."
TAG_STILL_IN_UTUB = "tagInUTub"
PREVIOUS_TAG = "previousTag"
URL_IDS = "urlIDs"
UTUB_URL_IDS = "utubUrlIDs"
ADD_URL_TAG_TOOLTIP = "Add Tag"
DELETE_UTUB_TAG_WARNING = (
    "This will remove {{ tag_string }} from all associated URLs in this UTub!"
)
TAG_FILTER_NO_RESULTS = "No URLs match selected tags"
TAG_SEARCH_NO_RESULTS = "No tags found"
# Screen-reader announcements for the mobile tag-filter bottom sheet, fired only
# on a history-nav (Back/Forward) open/close — read dynamically by production
# TypeScript via APP_CONFIG.strings, so they go through the full bridge.
TAG_SHEET_ANNOUNCEMENT_OPEN = "Tag filter sheet opened"
TAG_SHEET_ANNOUNCEMENT_CLOSE = "Tag filter sheet closed"
TAG_SEARCH_PLACEHOLDER = "Filter tags"
TAG_SEARCH_COUNT_TEMPLATE = "{{ visible }} of {{ total }} tags shown"
TAG_DECK_NO_TAGS = "This UTub has no tags yet"

# Combobox (multi-tag apply) strings — read dynamically by production TypeScript
# via APP_CONFIG.strings, so they go through the full APP_CONFIG bridge
# (constants.STRINGS + generate_strings_js() + frontend/test-setup.ts mock).
ADD_TAGS_PLACEHOLDER = "Type to search or create tags…"
ADD_TAGS_SUBMIT = "Add tags"
ADD_TAGS_ARIA_LABEL = "Add tags"
TAGS_OPTIONAL_LABEL = "Tags (optional)"
TAG_CREATE_NEW = "Create tag"
TAGS_LIMIT_REACHED = "Maximum {max} tags reached — remove a tag to add more"
TAGS_NO_MATCHES = "No matching tags"
TAGS_MATCH_COUNT = "{n} matches"
TAGS_MATCH_COUNT_ONE = "1 match"
TAGS_EMPTY_HINT = "No tags yet — type to create one"

# Bulk multi-URL tag-apply strings (Phase 2). Read dynamically by production
# TypeScript (bulk-tag.ts / combobox.ts BULK mode) via APP_CONFIG.strings, so
# they go through the full APP_CONFIG bridge (constants.STRINGS +
# generate_strings_js() + frontend/test-setup.ts mock).
URL_BULK_ADD_TAGS_ARIA = "Add tags to {n} selected URLs"
URL_BULK_TAGS_APPLIED = "Tags added to {n} URLs."
URL_BULK_TAGS_APPLIED_ONE = "Tags added to 1 URL."
URL_BULK_TAGS_PARTIAL = (
    "Tags added to {applied} URLs; {skipped} skipped "
    "(already at the {max}-tag limit): {titles}"
)
URL_BULK_TAGS_NONE = "No tags added — all {n} selected URLs are at the {max}-tag limit."
URL_BULK_TAGS_NONE_SOME_SKIPPED = (
    "No new tags added — {skipped} skipped "
    "(already at the {max}-tag limit): {titles}"
)
URL_BULK_TAGS_NO_CHANGES = "No changes — the selected URLs already had those tags."
URL_BULK_TAGS_STALE_SELECTION = (
    "One or more selected URLs are no longer available — refresh your selection."
)
URL_BULK_TAGS_SUBMITTING = "Adding tags…"


class TAGS_SUCCESS(URL_GENERAL, UTUB_GENERAL):
    TAG_ADDED_TO_URL = TAG_ADDED_TO_URL
    TAGS_ADDED_TO_URL = TAGS_ADDED_TO_URL
    TAGS_ADDED_TO_URLS = TAGS_ADDED_TO_URLS
    TAG_ADDED_TO_UTUB = TAG_ADDED_TO_UTUB
    TAG_REMOVED_FROM_URL = TAG_REMOVED_FROM_URL
    TAG_REMOVED_FROM_UTUB = TAG_REMOVED_FROM_UTUB
    UTUB_TAG = UTUB_TAG
    TAG_STILL_IN_UTUB = TAG_STILL_IN_UTUB
    TAG_MODIFIED_ON_URL = TAG_MODIFIED_ON_URL
    PREVIOUS_TAG = PREVIOUS_TAG
    URL_IDS = URL_IDS
    UTUB_URL_IDS = UTUB_URL_IDS
    TAG_COUNTS_MODIFIED = TAG_COUNTS_MODIFIED


# Strings for tags failure
UNABLE_TO_ADD_TAG_TO_URL = "Unable to add tag to URL."
UNABLE_TO_ADD_TAG_TO_UTUB = "Unable to add tag to UTub."
MAX_URL_TAGS_REACHED = "URLs can only have up to {max_tags} tags."
TAG_ALREADY_ON_URL = "URL already has this tag."
TAG_ALREADY_IN_UTUB = "UTub already contains this tag."
ONLY_UTUB_MEMBERS_DELETE_TAGS = "Only UTub members can delete tags."
ONLY_UTUB_MEMBERS_UPDATE_TAGS = "Only UTub members can update tags."
TAG_EMPTY = "Tag must not be empty."
INVALID_URL_ID = "Invalid URL id."
URL_NOT_IN_UTUB = "One or more URLs are not in this UTub."


class TAGS_FAILURE(FAILURE_GENERAL):
    UNABLE_TO_ADD_TAG_TO_URL = UNABLE_TO_ADD_TAG_TO_URL
    UNABLE_TO_ADD_TAG_TO_UTUB = UNABLE_TO_ADD_TAG_TO_UTUB
    MAX_URL_TAGS_REACHED = MAX_URL_TAGS_REACHED
    TAG_ALREADY_ON_URL = TAG_ALREADY_ON_URL
    ONLY_UTUB_MEMBERS_UPDATE_TAGS = ONLY_UTUB_MEMBERS_UPDATE_TAGS
    ONLY_UTUB_MEMBERS_DELETE_TAGS = ONLY_UTUB_MEMBERS_DELETE_TAGS
    TAG_ALREADY_IN_UTUB = TAG_ALREADY_IN_UTUB
    TAG_EMPTY = TAG_EMPTY
    INVALID_URL_ID = INVALID_URL_ID
    URL_NOT_IN_UTUB = URL_NOT_IN_UTUB


# Strings for tags no change
TAG_NOT_MODIFIED = "Tag was not updated on this URL."


class TAGS_NO_CHANGE:
    TAG_NOT_MODIFIED = TAG_NOT_MODIFIED
