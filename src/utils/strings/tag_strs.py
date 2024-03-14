from src.utils.strings.json_strs import FAILURE_GENERAL
from src.utils.strings.model_strs import TAG
from src.utils.strings.url_strs import URL_GENERAL
from src.utils.strings.utub_strs import UTUB_GENERAL

# Strings for tags success
TAG_ADDED_TO_URL = "Tag added to this URL."
TAG_REMOVED_FROM_URL = "Tag removed from this URL."
TAG_MODIFIED_ON_URL = "Tag on this URL modified."
COUNT_IN_UTUB = "Count_in_UTub"


class TAGS_SUCCESS(URL_GENERAL, UTUB_GENERAL):
    TAG_ADDED_TO_URL = TAG_ADDED_TO_URL
    TAG_REMOVED_FROM_URL = TAG_REMOVED_FROM_URL
    TAG = TAG
    COUNT_IN_UTUB = COUNT_IN_UTUB
    TAG_MODIFIED_ON_URL = TAG_MODIFIED_ON_URL


# Strings for tags failure
UNABLE_TO_ADD_TAG_TO_URL = "Unable to add tag to URL."
FIVE_TAGS_MAX = "URLs can only have up to 5 tags."
TAG_ALREADY_ON_URL = "URL already has this tag."
ONLY_UTUB_MEMBERS_REMOVE_TAGS = "Only UTub members can remove tags."
ONLY_UTUB_MEMBERS_MODIFY_TAGS = "Only UTub members can modify tags."


class TAGS_FAILURE(FAILURE_GENERAL):
    UNABLE_TO_ADD_TAG_TO_URL = UNABLE_TO_ADD_TAG_TO_URL
    FIVE_TAGS_MAX = FIVE_TAGS_MAX
    TAG_ALREADY_ON_URL = TAG_ALREADY_ON_URL
    ONLY_UTUB_MEMBERS_MODIFY_TAGS = ONLY_UTUB_MEMBERS_MODIFY_TAGS
    ONLY_UTUB_MEMBERS_REMOVE_TAGS = ONLY_UTUB_MEMBERS_REMOVE_TAGS


# Strings for tags no change
TAG_NOT_MODIFIED = "Tag was not modified on this URL."


class TAGS_NO_CHANGE:
    TAG_NOT_MODIFIED = TAG_NOT_MODIFIED