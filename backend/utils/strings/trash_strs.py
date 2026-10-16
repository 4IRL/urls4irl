from backend.utils.strings.json_strs import FAILURE_GENERAL

# Server-side messages for the Trash API (restore / delete forever / empty trash).
# The TRASH_SUCCESS / TRASH_FAILURE classes are server messages only. The TRASH_UI
# class holds the desktop Trash panel copy that TypeScript renders; it is bridged to
# APP_CONFIG.strings with a TRASH_ key prefix (see STRINGS / generate_strings_js()).

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


# Desktop Trash panel copy, read by TypeScript through APP_CONFIG.strings.TRASH_<NAME>
class TRASH_UI:
    TAB_URLS = "URLs ({n})"
    TAB_UTUBS = "UTubs ({n})"
    RETENTION_NOTICE = (
        "Items here are permanently deleted {n} days after they were removed."
    )
    EMPTY_STATE = "Nothing in Trash."
    DAYS_LEFT = "{n} days left"
    DAY_LEFT = "1 day left"
    EXPIRES_TODAY = "Expires today"
    FROM_UTUB = "from {utub}"
    ORIGIN_DELETED = "Origin UTub deleted · choose a UTub on restore"
    ORIGIN_LOCKED = "Origin UTub locked"
    UTUB_LOCKED = "UTub locked"
    DELETED_BY = "Deleted by {user} · {ago}"
    DELETED_BY_YOU = "Deleted by you · {ago}"
    AGO_TODAY = "today"
    AGO_ONE_DAY = "1 day ago"
    AGO_DAYS = "{n} days ago"
    UTUB_SUMMARY = "URLs: {urls} · Members: {members}"
    RESTORE = "Restore"
    RESTORE_TO = "Restore to…"
    DELETE_FOREVER = "Delete forever"
    PICK_DESTINATION = "Restore to which UTub?"
    PICKER_LOCKED = "Locked"
    NO_DESTINATION = "You have no unlocked UTub to restore into."
    RESTORED_TO = "Restored to {utub}."
    UTUB_RESTORED = "Restored {utub}."
    URL_PURGED = "Deleted forever."
    UTUB_PURGED = "Deleted {utub} forever."
    EMPTIED = "{n} items deleted forever."
    EMPTY_SKIPPED_LOCKED = "{n} locked items were kept."
    NOT_IN_TRASH = NOT_IN_TRASH
    ALREADY_IN_DESTINATION = "That UTub already has this URL."
    LOCKED = "That UTub is locked, so this item can't be changed."
    CONFIRM_PURGE_TITLE = "Delete forever?"
    CONFIRM_PURGE_URL_BODY = (
        "“{title}” will be permanently deleted. This can't be undone."
    )
    CONFIRM_PURGE_UTUB_BODY = (
        "“{utub}” and its {n} URLs will be permanently deleted. This can't be undone."
    )
    CONFIRM_EMPTY_TITLE = "Empty trash?"
    CONFIRM_EMPTY_URLS_BODY = "Permanently delete {n} URLs? This can't be undone."
    CONFIRM_EMPTY_UTUBS_BODY = (
        "Permanently delete {n} UTubs and their URLs? This can't be undone."
    )
    VIEW_QUERY_PARAM = VIEW_QUERY_PARAM
    TRASH_VIEW = "trash"
