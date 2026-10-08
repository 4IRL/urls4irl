from backend.utils.strings.json_strs import FAILURE_GENERAL, REDIRECT
from backend.utils.strings.model_strs import (
    ADDED_BY,
    TAG_COUNTS_MODIFIED,
    URL_ID,
    URL_STRING,
    URL_TAGS,
    URL_TITLE,
    UTUB_URL_ID,
    UTUB_URL_TAG_IDS,
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
# Desktop hover-tooltip titles (and matching aria-labels) for the TS-rendered
# URL-card confirm/cancel buttons. Read from TypeScript, so they must also be
# added to generate_strings_js() and frontend/test-setup.ts — plan Steps 5/6.
CONFIRM_URL_TITLE_EDIT_TOOLTIP = "Confirm title edit"
CANCEL_URL_TITLE_EDIT_TOOLTIP = "Cancel title edit"
CONFIRM_URL_EDIT_TOOLTIP = "Confirm URL edit"
CANCEL_URL_EDIT_TOOLTIP = "Cancel URL edit"
ACCESS_URL_WARNING = "This URL is a bit unusual — it could launch an app, not a webpage. Still want to access?"
URL_SEARCH_NO_RESULTS = "No URLs found"
UTUB_NO_URLS = "No URLs yet"
ADD_URL_BUTTON = "Add URL"

# Bulk delete-from-UTub success string.
URLS_DELETED = "URLs deleted from this UTub."

# Bulk copy-to-UTub success / banner / per-card cue strings.
URLS_COPIED = "URLs copied to UTub."
URLS_COPIED_PARTIAL = "{copied} copied; {skipped} already in the UTub."
URLS_COPY_NONE_NEW = "All selected URLs are already in the UTub."
# Multi-destination bulk-copy banner strings (n >= 2 destinations succeeded). The
# frontend selects singular (URLS_COPIED/_PARTIAL) vs these _MULTI forms by the
# destination success count, avoiding ungrammatical "Copied to 1 UTubs".
URLS_COPIED_MULTI = "Copied to {n} UTubs."
URLS_COPIED_MULTI_PARTIAL = "Copied to {n} UTubs; {skipped} already present."
URLS_COPY_MULTI_NONE_NEW = "All selected URLs were already in the chosen UTubs."
URLS_COPIED_MULTI_SOME_LOCKED = "Copied to {n} UTubs; {locked} skipped (locked)."
# Singular locked-skip fallback (exactly one destination succeeded); "1" is a
# literal, only {locked} is interpolated in TS.
URLS_COPIED_SOME_LOCKED = "Copied to 1 UTub; {locked} skipped (locked)."
# In-picker hint shown when no destination is staged.
URL_BULK_COPY_SELECT_DESTINATION = "Select at least one UTub to copy into."
# Picker footer live-region staged-count message (singular vs plural).
URL_BULK_COPY_ONE_SELECTED = "1 UTub selected."
URL_BULK_COPY_N_SELECTED = "{n} UTubs selected."
# Per-row role-badge aria-label template ({role} interpolated in TS with the row's
# raw memberRole value) and the per-row locked text label.
URL_BULK_COPY_ROLE_ARIA = "Role: {role}"
URL_BULK_COPY_LOCKED_LABEL = "🔒 locked"
URL_BULK_CARD_COPIED = "Copied"
URL_BULK_CARD_ALREADY_THERE = "Already there"
URL_BULK_COPY_LABEL = "Copy to UTub"
URL_BULK_COPY_SUBMITTING = "Copying…"
URL_BULK_COPY_ALL_LOCKED = "All other UTubs are locked."
# Picker listbox aria-label ({n} = selected-URL count); mirrors the
# URL_BULK_ADD_TAGS_ARIA precedent for the tag picker.
URL_BULK_COPY_ARIA = "Copy {n} selected URLs to…"
# Destination-picker filter box: placeholder / aria-label, and the no-results
# message shown inside the listbox when the typed filter matches no UTubs.
URL_BULK_COPY_FILTER_PLACEHOLDER = "Filter UTubs…"
URL_BULK_COPY_NO_MATCHES = "No UTubs match your filter."

# Bulk delete-from-UTub confirm + banner + per-card cue strings — read by
# bulk-actions/bulk-delete.ts. The confirm reuses the shared #confirmModal; the
# result banner + card cue reuse the shared .bulkTagBanner / .bulkCardResultCue
# styling. Every banner/cue string is count-only (XSS-safe): a URL title is never
# interpolated. Singular vs plural forms are selected in TS by the relevant count.
URL_BULK_DELETE_LABEL = "Delete"
URL_BULK_DELETE_DISABLED_REASON = (
    "You can delete only URLs you added, or any URL in a UTub you created."
)
URL_BULK_DELETE_CONFIRM_TITLE = "Delete {n} URLs from this UTub?"
URL_BULK_DELETE_CONFIRM_TITLE_ONE = "Delete 1 URL from this UTub?"
URL_BULK_DELETE_CONFIRM_BODY = (
    "This permanently removes them from this UTub for everyone. It can't be undone."
)
URL_BULK_DELETE_HIDDEN_WARNING = (
    "{n} selected URLs are hidden by your filter and will still be deleted."
)
URL_BULK_DELETE_HIDDEN_WARNING_ONE = (
    "1 selected URL is hidden by your filter and will still be deleted."
)
URL_BULK_DELETE_SKIPPED_WARNING = (
    "{n} selected URLs were added by another member and will be skipped."
)
URL_BULK_DELETE_SKIPPED_WARNING_ONE = (
    "1 selected URL was added by another member and will be skipped."
)
URL_BULK_DELETE_SUBMIT = "Delete {n} URLs"
URL_BULK_DELETE_SUBMIT_ONE = "Delete 1 URL"
URL_BULK_DELETE_CANCEL = "Just kidding"
URL_BULK_DELETED = "Deleted {n} URLs."
URL_BULK_DELETED_ONE = "Deleted 1 URL."
# Partial-outcome suffix appended after the deleted-count clause when some
# selected URLs were skipped (not deletable by this user).
URL_BULK_DELETE_SKIPPED_SUFFIX = "{n} skipped because you can't delete them."
URL_BULK_DELETE_SKIPPED_SUFFIX_ONE = "1 skipped because you can't delete it."
# Shown when nothing was deleted (every selected URL was skipped as non-deletable).
URL_BULK_DELETE_NONE = "No URLs were deleted — you can't delete the selected URLs."
URL_BULK_CARD_CANT_DELETE = "Can't delete"

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

# Opt-in query-parameter trim control (frontend/home/urls/trim/param-trim-block.ts).
# Every string is rendered by TypeScript, so each takes the full bridge
# (STRINGS -> generate_strings_js() -> test-setup.ts). Single-brace {n}-style
# placeholders are interpolated in TS; the _ONE forms are the singular companions.
# URL_TRIM_CONFLICT is a client-side substitution for the server's generic 409
# message (the server cannot tell a user trim apart: the request body arrives
# already trimmed), so it is Tier 1, unlike the server-rendered
# URL_IN_UTUB_TRACKING_PARAMS_STRIPPED.
URL_TRIM_PARAMS_LABEL = "Query parameters ({n})"
URL_TRIM_PARAMS_LABEL_ONE = "Query parameter (1)"
URL_TRIM_WARNING = "Warning: removing parameters may break this link."
URL_TRIM_WARNING_ONE = "Warning: removing this parameter may break this link."
URL_TRIM_GROUP_ARIA = "Query parameters to keep or drop"
URL_TRIM_DROP_ALL = "Drop all"
URL_TRIM_KEEP_ALL = "Keep all"
URL_TRIM_KEPT_COUNT = "{kept} of {total} kept"
URL_TRIM_PREVIEW_LABEL = "Saves as"
URL_TRIM_HEADER_DROPPED = "{n} dropped"
URL_TRIM_CHIP_KEEP_ARIA = "Keep parameter {param}"
URL_TRIM_CHIP_DROP_ARIA = "Drop parameter {param}"
URL_TRIM_CHIP_AUTO_ARIA = "Parameter {param} is removed automatically"
URL_TRIM_AUTO_TAG = "auto"
URL_TRIM_ANNOUNCE = "{verb} {param}. {kept} of {total} parameters kept."
URL_TRIM_BULK_ANNOUNCE = "{kept} of {total} parameters kept."
URL_TRIM_SAVED_BANNER = "Saved without {n} parameters."
URL_TRIM_SAVED_BANNER_ONE = "Saved without 1 parameter."
URL_TRIM_UNDO = "Undo"
URL_TRIM_DISMISS_ARIA = "Dismiss"
URL_TRIM_UNDO_NOOP = (
    "Nothing to undo — those parameters are always removed automatically."
)
URL_TRIM_UNDO_CONFLICT = "Cannot undo — the original URL is already in this UTub."
URL_TRIM_CONFLICT = (
    "That URL is already in this UTub once the parameters you removed are dropped."
)
URL_TRIM_DROPS_RESET = "URL changed — all parameters are kept again."
# `{verb}` values for URL_TRIM_ANNOUNCE (single chip toggle).
URL_TRIM_VERB_DROPPED = "Dropped"
URL_TRIM_VERB_KEPT = "Kept"


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
    URLS_DELETED = URLS_DELETED
    URLS_COPIED = URLS_COPIED
    URLS_COPIED_PARTIAL = URLS_COPIED_PARTIAL
    URLS_COPY_NONE_NEW = URLS_COPY_NONE_NEW
    URLS_COPIED_MULTI = URLS_COPIED_MULTI
    URLS_COPIED_MULTI_PARTIAL = URLS_COPIED_MULTI_PARTIAL
    URLS_COPY_MULTI_NONE_NEW = URLS_COPY_MULTI_NONE_NEW
    URLS_COPIED_MULTI_SOME_LOCKED = URLS_COPIED_MULTI_SOME_LOCKED
    URLS_COPIED_SOME_LOCKED = URLS_COPIED_SOME_LOCKED
    URL_BULK_COPY_SELECT_DESTINATION = URL_BULK_COPY_SELECT_DESTINATION
    URL_BULK_COPY_ONE_SELECTED = URL_BULK_COPY_ONE_SELECTED
    URL_BULK_COPY_N_SELECTED = URL_BULK_COPY_N_SELECTED
    URL_BULK_COPY_ROLE_ARIA = URL_BULK_COPY_ROLE_ARIA
    URL_BULK_COPY_LOCKED_LABEL = URL_BULK_COPY_LOCKED_LABEL
    URL_BULK_CARD_COPIED = URL_BULK_CARD_COPIED
    URL_BULK_CARD_ALREADY_THERE = URL_BULK_CARD_ALREADY_THERE
    URL_BULK_COPY_LABEL = URL_BULK_COPY_LABEL
    URL_BULK_COPY_SUBMITTING = URL_BULK_COPY_SUBMITTING
    URL_BULK_COPY_ALL_LOCKED = URL_BULK_COPY_ALL_LOCKED
    URL_BULK_COPY_ARIA = URL_BULK_COPY_ARIA
    URL_BULK_COPY_FILTER_PLACEHOLDER = URL_BULK_COPY_FILTER_PLACEHOLDER
    URL_BULK_COPY_NO_MATCHES = URL_BULK_COPY_NO_MATCHES
    URL_BULK_DELETE_LABEL = URL_BULK_DELETE_LABEL
    URL_BULK_DELETE_DISABLED_REASON = URL_BULK_DELETE_DISABLED_REASON
    URL_BULK_DELETE_CONFIRM_TITLE = URL_BULK_DELETE_CONFIRM_TITLE
    URL_BULK_DELETE_CONFIRM_TITLE_ONE = URL_BULK_DELETE_CONFIRM_TITLE_ONE
    URL_BULK_DELETE_CONFIRM_BODY = URL_BULK_DELETE_CONFIRM_BODY
    URL_BULK_DELETE_HIDDEN_WARNING = URL_BULK_DELETE_HIDDEN_WARNING
    URL_BULK_DELETE_HIDDEN_WARNING_ONE = URL_BULK_DELETE_HIDDEN_WARNING_ONE
    URL_BULK_DELETE_SKIPPED_WARNING = URL_BULK_DELETE_SKIPPED_WARNING
    URL_BULK_DELETE_SKIPPED_WARNING_ONE = URL_BULK_DELETE_SKIPPED_WARNING_ONE
    URL_BULK_DELETE_SUBMIT = URL_BULK_DELETE_SUBMIT
    URL_BULK_DELETE_SUBMIT_ONE = URL_BULK_DELETE_SUBMIT_ONE
    URL_BULK_DELETE_CANCEL = URL_BULK_DELETE_CANCEL
    URL_BULK_DELETED = URL_BULK_DELETED
    URL_BULK_DELETED_ONE = URL_BULK_DELETED_ONE
    URL_BULK_DELETE_SKIPPED_SUFFIX = URL_BULK_DELETE_SKIPPED_SUFFIX
    URL_BULK_DELETE_SKIPPED_SUFFIX_ONE = URL_BULK_DELETE_SKIPPED_SUFFIX_ONE
    URL_BULK_DELETE_NONE = URL_BULK_DELETE_NONE
    URL_BULK_CARD_CANT_DELETE = URL_BULK_CARD_CANT_DELETE


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
UNABLE_TO_DELETE_URLS = "Unable to delete these URLs."
URL_NOT_IN_UTUB = "URL not found in the source UTub."
URLS_NOT_IN_UTUB = "One or more URLs are not in this UTub."
INVALID_URL_ID = "Invalid URL ID."
INVALID_UTUB_ID = "Invalid UTub ID."
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
    UNABLE_TO_DELETE_URLS = UNABLE_TO_DELETE_URLS
    URL_NOT_IN_UTUB = URL_NOT_IN_UTUB
    URLS_NOT_IN_UTUB = URLS_NOT_IN_UTUB
    INVALID_URL_ID = INVALID_URL_ID
    INVALID_UTUB_ID = INVALID_UTUB_ID
    CANNOT_COPY_TO_SAME_UTUB = CANNOT_COPY_TO_SAME_UTUB


# Strings for URL no change
URL_AND_TITLE_NOT_MODIFIED = "URL and URL title were not modified."
URL_NOT_MODIFIED = "URL not modified."
URL_TITLE_NOT_MODIFIED = "URL title not modified."


class URL_NO_CHANGE:
    URL_AND_TITLE_NOT_MODIFIED = URL_AND_TITLE_NOT_MODIFIED
    URL_NOT_MODIFIED = URL_NOT_MODIFIED
    URL_TITLE_NOT_MODIFIED = URL_TITLE_NOT_MODIFIED
