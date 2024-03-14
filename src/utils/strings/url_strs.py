from src.utils.strings.json_strs import FAILURE_GENERAL, REDIRECT
from src.utils.strings.model_strs import ADDED_BY, URL_ID, URL_STRING, URL_TITLE
from src.utils.strings.utub_strs import UTUB_GENERAL

# Strings for URL success
URLS = "urls"
URL = "URL"
URL_CREATED_ADDED = "New URL created and added to UTub."
URL_ADDED = "URL added to UTub."
URL_REMOVED = "URL removed from this UTub."
URL_TITLE_MODIFIED = "URL title was modified."
URL_OR_TITLE_MODIFIED = "URL and/or URL title modified."
URL_MODIFIED = "URL modified."
URL = "URL"

class URL_GENERAL:
    URL = URL
    REDIRECT = REDIRECT

class URL_SUCCESS(URL_GENERAL, UTUB_GENERAL):
    URL_ADDED = URL_ADDED
    URL_STRING = URL_STRING
    URL_ID = URL_ID
    URL_TITLE = URL_TITLE
    ADDED_BY = ADDED_BY
    URL_REMOVED = URL_REMOVED
    URL_CREATED_ADDED = URL_CREATED_ADDED
    URL_TITLE_MODIFIED = URL_TITLE_MODIFIED
    URL_OR_TITLE_MODIFIED = URL_OR_TITLE_MODIFIED
    URL_MODIFIED = URL_MODIFIED


# Strings for URL failure
UNABLE_TO_REMOVE_URL = "Unable to remove this URL."
UNABLE_TO_ADD_URL = "Unable to add this URL."
URL_IN_UTUB = "URL already in UTub."
UNABLE_TO_ADD_URL_FORM = "Unable to add this URL, please check inputs."
UNABLE_TO_MODIFY_URL_FORM = "Unable to update, please check inputs."
UNABLE_TO_MODIFY_URL = "Unable to modify this URL."
EMPTY_URL = "URL cannot be empty."


class URL_FAILURE(FAILURE_GENERAL):
    UNABLE_TO_ADD_URL = UNABLE_TO_ADD_URL
    UNABLE_TO_REMOVE_URL = UNABLE_TO_REMOVE_URL
    URL_IN_UTUB = URL_IN_UTUB
    UNABLE_TO_ADD_URL_FORM = UNABLE_TO_ADD_URL_FORM
    UNABLE_TO_MODIFY_URL = UNABLE_TO_MODIFY_URL
    EMPTY_URL = EMPTY_URL
    UNABLE_TO_MODIFY_URL_FORM = UNABLE_TO_MODIFY_URL_FORM
    URL_TITLE = URL_TITLE


# Strings for URL no change
URL_AND_TITLE_NOT_MODIFIED = "URL and URL title were not modified."
URL_NOT_MODIFIED = "URL not modified."
URL_TITLE_NOT_MODIFIED = "URL title not modified."


class URL_NO_CHANGE:
    URL_AND_TITLE_NOT_MODIFIED = URL_AND_TITLE_NOT_MODIFIED
    URL_NOT_MODIFIED = URL_NOT_MODIFIED
    URL_TITLE_NOT_MODIFIED = URL_TITLE_NOT_MODIFIED