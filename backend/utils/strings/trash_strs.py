from backend.utils.strings.json_strs import FAILURE_GENERAL

# Server-side messages for the Trash API (restore / delete forever / empty trash).
# These are server messages only: no APP_CONFIG.strings bridge until a TypeScript
# consumer renders them.

# Query param that opens the Trash destination on /home (``/home?view=trash``)
VIEW_QUERY_PARAM = "view"

# Strings for Trash success
URL_RESTORED = "URL restored from Trash."
UTUB_RESTORED = "UTub restored from Trash."
URL_PURGED = "URL permanently deleted."
UTUB_PURGED = "UTub permanently deleted."
TRASH_EMPTIED = "Trash emptied."


class TRASH_SUCCESS:
    URL_RESTORED = URL_RESTORED
    UTUB_RESTORED = UTUB_RESTORED
    URL_PURGED = URL_PURGED
    UTUB_PURGED = UTUB_PURGED
    TRASH_EMPTIED = TRASH_EMPTIED


# Strings for Trash failure
NOT_IN_TRASH = "This item is no longer in Trash."
DESTINATION_REQUIRED = "Choose a UTub to restore this URL into."
INVALID_DESTINATION = "This URL can only be restored into its own UTub."
URL_ALREADY_IN_DESTINATION = "That UTub already contains this URL."
UNABLE_TO_RESTORE_URL = "Unable to restore this URL."
UNABLE_TO_EMPTY_TRASH = "Unable to empty Trash."


class TRASH_FAILURE(FAILURE_GENERAL):
    NOT_IN_TRASH = NOT_IN_TRASH
    DESTINATION_REQUIRED = DESTINATION_REQUIRED
    INVALID_DESTINATION = INVALID_DESTINATION
    URL_ALREADY_IN_DESTINATION = URL_ALREADY_IN_DESTINATION
    UNABLE_TO_RESTORE_URL = UNABLE_TO_RESTORE_URL
    UNABLE_TO_EMPTY_TRASH = UNABLE_TO_EMPTY_TRASH
