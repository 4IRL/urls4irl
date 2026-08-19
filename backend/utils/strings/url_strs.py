from backend.utils.strings.json_strs import FAILURE_GENERAL, REDIRECT
from backend.utils.strings.model_strs import (
    ADDED_BY,
    URL_ID,
    URL_STRING,
    URL_TITLE,
    UTUB_URL_TAG_IDS,
    URL_TAGS,
    UTUB_URL_ID,
    TAG_COUNTS_MODIFIED,
)
from backend.utils.strings.utub_strs import UTUB_GENERAL

# Strings for URL success
URLS = "urls"
URL = "URL"
URL_CREATED_ADDED = "New URL created and added to UTub."
URL_ADDED = "URL added to UTub."
URL_REMOVED = "URL removed from this UTub."
URL_TITLE_MODIFIED = "URL title was modified."
URL_OR_TITLE_MODIFIED = "URL and/or URL title modified."
URL_MODIFIED = "URL modified."
URL_FOUND_IN_UTUB = "URL found in UTub."
TAG_IN_UTUB = "tagInUTub"
DELETE_URL_WARNING = "You can always add it back again!"
COPY_URL_TOOLTIP = "Copy URL"
COPIED_URL_TOOLTIP = "Copied!"
COPIED_URL_FAILURE_TOOLIP = "Copy failed!"
ACCESS_URL_TOOLTIP = "Access URL"
EDIT_URL_TOOLTIP = "Edit URL"
EDIT_URL_TITLE_TOOLTIP = "Edit URL title"
DELETE_URL_TOOLTIP = "Delete URL"
ACCESS_URL_WARNING = "This URL is a bit unusual — it could launch an app, not a webpage. Still want to access?"
URL_SEARCH_NO_RESULTS = "No URLs found"
UTUB_NO_URLS = "No URLs yet"
ADD_URL_BUTTON = "Add URL"

# Bulk copy-to-UTub success / banner / per-card cue strings.
URLS_COPIED = "URLs copied to UTub."
URLS_COPIED_PARTIAL = "{copied} copied; {skipped} already in the UTub."
URLS_COPY_NONE_NEW = "All selected URLs are already in the UTub."
URL_BULK_CARD_COPIED = "Copied"
URL_BULK_CARD_ALREADY_THERE = "Already there"
URL_BULK_COPY_LABEL = "Copy to UTub"
URL_BULK_COPY_SUBMITTING = "Copying…"
URL_BULK_COPY_ALL_LOCKED = "All other UTubs are locked."

# Multi-select bulk-action bar screen-reader announcements. TS composes the live
# announcement in bulk-actions/bulk-bar.ts from these templates ({n} is replaced
# with the selected / hidden count); the singular form mirrors the
# TAGS_MATCH_COUNT / TAGS_MATCH_COUNT_ONE plural-vs-one pattern.
URL_BULK_SELECTED_COUNT = "{n} URLs selected"
URL_BULK_SELECTED_COUNT_ONE = "1 URL selected"
URL_BULK_NONE_SELECTED = "No URLs selected"
URL_BULK_N_HIDDEN = "{n} hidden by filter"

# Static label words for the URL card's date-added attribution badge
# (frontend/home/urls/cards/cards.ts `createURLDateAddedBadge`). The dynamic
# username/date are composed in TS; these supply the fixed connective words so
# the rendered strings live in the backend source of truth. Rendered forms:
#   visible w/ adder : "Added by <user> · <date>"   (URL_ADDED_BY + " · ")
#   visible date-only: "Added: <date>"              (URL_DATE_ADDED_LABEL)
#   aria    w/ adder : "Added by <user> on <date>"  (URL_ADDED_BY + URL_ADDED_ON)
#   aria    date-only: "Added <date>"               (URL_DATE_ADDED_ARIA)
URL_ADDED_BY = "Added by"
URL_ADDED_ON = "on"
URL_DATE_ADDED_LABEL = "Added:"
URL_DATE_ADDED_ARIA = "Added"


class URL_GENERAL:
    URL = URL
    REDIRECT = REDIRECT
    UTUB_URL_TAG_IDS = UTUB_URL_TAG_IDS
    URL_ID = URL_ID
    TAG_IN_UTUB = TAG_IN_UTUB


class URL_SUCCESS(URL_GENERAL, UTUB_GENERAL):
    URL_ADDED = URL_ADDED
    URL_STRING = URL_STRING
    URL_TITLE = URL_TITLE
    ADDED_BY = ADDED_BY
    URL_REMOVED = URL_REMOVED
    URL_CREATED_ADDED = URL_CREATED_ADDED
    URL_TITLE_MODIFIED = URL_TITLE_MODIFIED
    URL_OR_TITLE_MODIFIED = URL_OR_TITLE_MODIFIED
    URL_MODIFIED = URL_MODIFIED
    UTUB_URL_ID = UTUB_URL_ID
    URL_FOUND_IN_UTUB = URL_FOUND_IN_UTUB
    URL_TAGS = URL_TAGS
    TAG_COUNTS_MODIFIED = TAG_COUNTS_MODIFIED
    URLS_COPIED = URLS_COPIED
    URLS_COPIED_PARTIAL = URLS_COPIED_PARTIAL
    URLS_COPY_NONE_NEW = URLS_COPY_NONE_NEW
    URL_BULK_CARD_COPIED = URL_BULK_CARD_COPIED
    URL_BULK_CARD_ALREADY_THERE = URL_BULK_CARD_ALREADY_THERE
    URL_BULK_COPY_LABEL = URL_BULK_COPY_LABEL
    URL_BULK_COPY_SUBMITTING = URL_BULK_COPY_SUBMITTING
    URL_BULK_COPY_ALL_LOCKED = URL_BULK_COPY_ALL_LOCKED


# Strings for URL failure
UNABLE_TO_DELETE_URL = "Unable to remove this URL."
UNABLE_TO_ADD_URL = "Unable to add this URL."
UNABLE_TO_VALIDATE_THIS_URL = "This is not a valid URL."
URL_IN_UTUB = "URL already in UTub."
URL_IN_UTUB_TRACKING_PARAMS_STRIPPED = (
    "URL already in UTub (tracking parameters were removed before checking)."
)
UNABLE_TO_ADD_URL_FORM = "Unable to add this URL, please check inputs."
UNABLE_TO_MODIFY_URL_FORM = "Unable to update, please check inputs."
UNABLE_TO_MODIFY_URL = "Unable to modify this URL."
UNABLE_TO_RETRIEVE_URL = "Unable to retrieve this URL."
EMPTY_URL = "URL cannot be empty."
TOO_MANY_WAYBACK_ATTEMPTS = "Too many attempts, please try again in one minute."
UNEXPECTED_VALIDATION_EXCEPTION = "Unexpected exception while validating the URL."
URLS_WITH_CREDENTIALS_EXCEPTION = "URLs with credentials not allowed."
UNABLE_TO_COPY_URLS = "Unable to copy the selected URLs."
URL_NOT_IN_UTUB = "URL not found in the source UTub."
INVALID_URL_ID = "Invalid URL ID."
CANNOT_COPY_TO_SAME_UTUB = "Cannot copy URLs into the same UTub."


class URL_FAILURE(FAILURE_GENERAL):
    UNABLE_TO_VALIDATE_THIS_URL = UNABLE_TO_VALIDATE_THIS_URL
    UNABLE_TO_ADD_URL = UNABLE_TO_ADD_URL
    UNABLE_TO_DELETE_URL = UNABLE_TO_DELETE_URL
    URL_IN_UTUB = URL_IN_UTUB
    URL_IN_UTUB_TRACKING_PARAMS_STRIPPED = URL_IN_UTUB_TRACKING_PARAMS_STRIPPED
    UNABLE_TO_ADD_URL_FORM = UNABLE_TO_ADD_URL_FORM
    UNABLE_TO_MODIFY_URL = UNABLE_TO_MODIFY_URL
    UNABLE_TO_RETRIEVE_URL = UNABLE_TO_RETRIEVE_URL
    EMPTY_URL = EMPTY_URL
    UNABLE_TO_MODIFY_URL_FORM = UNABLE_TO_MODIFY_URL_FORM
    URL_TITLE = URL_TITLE
    URL_STRING = URL_STRING
    TOO_MANY_WAYBACK_ATTEMPTS = TOO_MANY_WAYBACK_ATTEMPTS
    UNEXPECTED_VALIDATION_EXCEPTION = UNEXPECTED_VALIDATION_EXCEPTION
    URLS_WITH_CREDENTIALS_EXCEPTION = URLS_WITH_CREDENTIALS_EXCEPTION
    UNABLE_TO_COPY_URLS = UNABLE_TO_COPY_URLS
    URL_NOT_IN_UTUB = URL_NOT_IN_UTUB
    INVALID_URL_ID = INVALID_URL_ID
    CANNOT_COPY_TO_SAME_UTUB = CANNOT_COPY_TO_SAME_UTUB


# Strings for URL no change
URL_AND_TITLE_NOT_MODIFIED = "URL and URL title were not modified."
URL_NOT_MODIFIED = "URL not modified."
URL_TITLE_NOT_MODIFIED = "URL title not modified."


class URL_NO_CHANGE:
    URL_AND_TITLE_NOT_MODIFIED = URL_AND_TITLE_NOT_MODIFIED
    URL_NOT_MODIFIED = URL_NOT_MODIFIED
    URL_TITLE_NOT_MODIFIED = URL_TITLE_NOT_MODIFIED
