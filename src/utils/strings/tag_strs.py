from src.utils.strings.json_strs import FAILURE_GENERAL
from src.utils.strings.model_strs import UTUB_TAG
from src.utils.strings.url_strs import URL_GENERAL
from src.utils.strings.utub_strs import UTUB_GENERAL

# Strings for tags success
TAG_ADDED_TO_URL = "Tag added to this URL."
TAG_ADDED_TO_UTUB = "Tag added to this UTub."
TAG_REMOVED_FROM_URL = "Tag removed from this URL."
TAG_MODIFIED_ON_URL = "Tag on this URL modified."
TAG_STILL_IN_UTUB = "tagInUTub"
PREVIOUS_TAG = "previousTag"


class TAGS_SUCCESS(URL_GENERAL, UTUB_GENERAL):
    TAG_ADDED_TO_URL = TAG_ADDED_TO_URL
    TAG_ADDED_TO_UTUB = TAG_ADDED_TO_UTUB
    TAG_REMOVED_FROM_URL = TAG_REMOVED_FROM_URL
    UTUB_TAG = UTUB_TAG
    TAG_STILL_IN_UTUB = TAG_STILL_IN_UTUB
    TAG_MODIFIED_ON_URL = TAG_MODIFIED_ON_URL
    PREVIOUS_TAG = PREVIOUS_TAG


# Strings for tags failure
UNABLE_TO_ADD_TAG_TO_URL = "Unable to add tag to URL."
UNABLE_TO_ADD_TAG_TO_UTUB = "Unable to add tag to UTub."
FIVE_TAGS_MAX = "URLs can only have up to 5 tags."
TAG_ALREADY_ON_URL = "URL already has this tag."
TAG_ALREADY_IN_UTUB = "UTub already contains this tag."
ONLY_UTUB_MEMBERS_DELETE_TAGS = "Only UTub members can delete tags."
ONLY_UTUB_MEMBERS_UPDATE_TAGS = "Only UTub members can update tags."


class TAGS_FAILURE(FAILURE_GENERAL):
    UNABLE_TO_ADD_TAG_TO_URL = UNABLE_TO_ADD_TAG_TO_URL
    UNABLE_TO_ADD_TAG_TO_UTUB = UNABLE_TO_ADD_TAG_TO_UTUB
    FIVE_TAGS_MAX = FIVE_TAGS_MAX
    TAG_ALREADY_ON_URL = TAG_ALREADY_ON_URL
    ONLY_UTUB_MEMBERS_UPDATE_TAGS = ONLY_UTUB_MEMBERS_UPDATE_TAGS
    ONLY_UTUB_MEMBERS_DELETE_TAGS = ONLY_UTUB_MEMBERS_DELETE_TAGS
    TAG_ALREADY_IN_UTUB = TAG_ALREADY_IN_UTUB


# Strings for tags no change
TAG_NOT_MODIFIED = "Tag was not updated on this URL."


class TAGS_NO_CHANGE:
    TAG_NOT_MODIFIED = TAG_NOT_MODIFIED
