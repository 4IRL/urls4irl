from src.utils.strings.json_strs import FAILURE_GENERAL
from src.utils.strings.model_strs import UTUB_DESCRIPTION

# Strings for utub success
UTUB_ID = "utubID"
UTUB_ID_QUERY_PARAM = "UTubID"
UTUB_NAME = "utubName"
UTUB_USERS = "utubUsers"
UTUB_CREATOR_ID = "utubCreatorID"
UTUB_DELETED = "UTub deleted."
UTUB_CREATE_SAME_NAME = "You already have a UTub with a similar name."
UTUB_UPDATE_SAME_NAME = "You are a member of a UTub with an identical name."
UTUB_DELETE_WARNING = "This action is irreversible!"
UTUB_CREATE_MSG = "Create a UTub"
UTUB_SELECT = "Select a UTub"


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
UNABLE_TO_MAKE_UTUB = "Unable to make a UTub with that information."
UNABLE_TO_MODIFY_UTUB_NAME = "Unable to modify UTub name."
UNABLE_TO_MODIFY_UTUB_DESC = "Unable to modify UTub description."
UTUB_DESC_TOO_LONG = "UTub description is too long."
UTUB_DESC_FIELD_TOO_LONG = ["Field cannot be longer than 500 characters."]
UTUB_NAME_FIELD_INVALID = ["Field must be between 1 and 30 characters long."]
UTUB_NAME_EMPTY = "Name cannot contain only spaces or be empty."


class UTUB_FAILURE(UTUB_GENERAL, FAILURE_GENERAL):
    UNABLE_TO_MODIFY_UTUB_NAME = UNABLE_TO_MODIFY_UTUB_NAME
    UNABLE_TO_MAKE_UTUB = UNABLE_TO_MAKE_UTUB
    UNABLE_TO_MODIFY_UTUB_DESC = UNABLE_TO_MODIFY_UTUB_DESC
    UTUB_DESC_TOO_LONG = UTUB_DESC_TOO_LONG
    UTUB_DESC_FIELD_TOO_LONG = UTUB_DESC_FIELD_TOO_LONG
    UTUB_NAME_FIELD_INVALID = UTUB_NAME_FIELD_INVALID
    UTUB_NAME_EMPTY = UTUB_NAME_EMPTY
