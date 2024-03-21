from src.utils.strings.model_strs import (
    DESCRIPTION,
    EMAIL,
    NAME,
    PASSWORD,
    TAG_STRING,
    URL_STRING,
    URL_TITLE,
    USERNAME,
    UTUB_DESCRIPTION,
)

# Strings for all forms
CSRF_TOKEN = "csrf_token"


class GENERAL_FORM:
    CSRF_TOKEN = CSRF_TOKEN
    EMAIL = EMAIL
    PASSWORD = PASSWORD


class TAG_FORM(GENERAL_FORM):
    TAG_STRING = TAG_STRING


class URL_FORM(GENERAL_FORM):
    URL_STRING = URL_STRING
    URL_TITLE = URL_TITLE


class ADD_USER_FORM(GENERAL_FORM):
    USERNAME = USERNAME


class UTUB_FORM(GENERAL_FORM):
    NAME = NAME
    DESCRIPTION = DESCRIPTION


UTUB_DESCRIPTION_FOR_FORM = "utub_description"


class UTUB_DESCRIPTION_FORM(GENERAL_FORM):
    UTUB_DESCRIPTION = UTUB_DESCRIPTION
    UTUB_DESCRIPTION_FOR_FORM = UTUB_DESCRIPTION_FOR_FORM
