# Internal libraries
from src.cli.mock_constants import (
    USERNAME_BASE,
    MOCK_UTUB_NAME_BASE,
    EMAIL_SUFFIX,
    MOCK_URL_STRINGS,
)


class UI_TEST_STRINGS:
    BASE_URL = "http://127.0.0.1:"
    DOCKER_BASE_URL = "http://web:"

    TEST_USERNAME_1 = USERNAME_BASE + "1"
    # Using password as email
    TEST_PASSWORD_1 = TEST_USERNAME_1 + EMAIL_SUFFIX

    TEST_USERNAME_UNLISTED = USERNAME_BASE + "_UNLISTED"
    TEST_PASSWORD_UNLISTED = TEST_USERNAME_UNLISTED + EMAIL_SUFFIX

    # Register
    PASSWORD_EQUALITY_FAILED = "Field must be equal to password."
    EMAIL_EQUALITY_FAILED = "Field must be equal to email."

    # UTubs
    TEST_UTUB_NAME_1 = MOCK_UTUB_NAME_BASE + "1"
    TEST_UTUB_NAME_2 = MOCK_UTUB_NAME_BASE + "2"

    # Tags
    TEST_TAG_NAME_1 = "Terrible"

    TEST_URL_STRING_CREATE = MOCK_URL_STRINGS[0]
    TEST_URL_TITLE_1 = "This is " + MOCK_URL_STRINGS[0] + "."
    TEST_URL_TITLE_UPDATE = "MS Support"

    UTUB_SEARCH_NAMES = (
        "A1",
        "B1",
        "C1",
        "D1",
    )
