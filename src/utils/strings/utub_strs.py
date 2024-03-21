from src.utils.strings.json_strs import FAILURE_GENERAL
from src.utils.strings.model_strs import UTUB_DESCRIPTION

# Strings for utub success
UTUB_ID = "UTub_ID"
UTUB_NAME = "UTub_name"
UTUB_USERS = "UTub_users"
UTUB_CREATOR_ID = "UTub_creator_id"
UTUB_DELETED = "UTub deleted."


class UTUB_GENERAL:
    UTUB_ID = UTUB_ID
    UTUB_NAME = UTUB_NAME
    UTUB_USERS = UTUB_USERS
    UTUB_DESCRIPTION = UTUB_DESCRIPTION


class UTUB_SUCCESS(UTUB_GENERAL):
    UTUB_CREATOR_ID = UTUB_CREATOR_ID
    UTUB_DELETED = UTUB_DELETED


# Strings for utub failure
UNABLE_TO_MAKE_UTUB = "Unable to make a UTub with that information."
UNABLE_TO_MODIFY_UTUB_NAME = "Unable to modify this UTub's name."
UNABLE_TO_MODIFY_UTUB_DESC = "Unable to modify this UTub's description."
UTUB_DESC_TOO_LONG = "UTub description is too long."
UTUB_DESC_FIELD_TOO_LONG = ["Field cannot be longer than 500 characters."]
UTUB_NAME_FIELD_INVALID = ["Field must be between 1 and 30 characters long."]


class UTUB_FAILURE(UTUB_GENERAL, FAILURE_GENERAL):
    UNABLE_TO_MODIFY_UTUB_NAME = UNABLE_TO_MODIFY_UTUB_NAME
    UNABLE_TO_MAKE_UTUB = UNABLE_TO_MAKE_UTUB
    UNABLE_TO_MODIFY_UTUB_DESC = UNABLE_TO_MODIFY_UTUB_DESC
    UTUB_DESC_TOO_LONG = UTUB_DESC_TOO_LONG
    UTUB_DESC_FIELD_TOO_LONG = UTUB_DESC_FIELD_TOO_LONG
    UTUB_NAME_FIELD_INVALID = UTUB_NAME_FIELD_INVALID
