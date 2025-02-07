# Internal libraries
from src.cli.mock_constants import (
    USERNAME_BASE,
    MOCK_UTUB_NAME_BASE,
    EMAIL_SUFFIX,
    MOCK_URL_STRINGS,
)


class UI_TEST_STRINGS:
    BASE_URL = "http://127.0.0.1:"

    TEST_USERNAME_1 = USERNAME_BASE + "1"
    # Using password as email
    TEST_PASSWORD_1 = TEST_USERNAME_1 + EMAIL_SUFFIX

    TEST_USERNAME_UNLISTED = USERNAME_BASE + "_UNLISTED"
    TEST_PASSWORD_UNLISTED = TEST_USERNAME_UNLISTED + EMAIL_SUFFIX

    # Register
    HEADER_MODAL_EMAIL_VALIDATION = "Validate Your Email!"
    PASSWORD_EQUALITY_FAILED = "Field must be equal to password."
    EMAIL_EQUALITY_FAILED = "Field must be equal to email."

    # UTubs
    TEST_UTUB_NAME_1 = MOCK_UTUB_NAME_BASE + "1"
    TEST_UTUB_NAME_2 = MOCK_UTUB_NAME_BASE + "2"
    BODY_MODAL_UTUB_CREATE_SAME_NAME = "You already have a UTub with a similar name."
    BODY_MODAL_UTUB_UPDATE_SAME_NAME = (
        "You are a member of a UTub with an identical name."
    )
    BODY_MODAL_UTUB_DELETE = "This action is irreversible!"

    MESSAGE_NO_UTUBS = "Create a UTub"

    # Members
    BODY_MODAL_MEMBER_DELETE = (
        "This member will no longer have access to the URLs in this UTub."
    )
    BODY_MODAL_LEAVE_UTUB = "You will no longer have access to the URLs in this UTub."

    # Tags
    TEST_TAG_NAME_1 = "Terrible"

    # URLs
    BODY_MODAL_URL_DELETE = "You can always add it back again!"

    TEST_URL_STRING_CREATE = MOCK_URL_STRINGS[0]
    TEST_URL_STRING_UPDATE = "https://support.microsoft.com/en-us/microsoft-edge"
    TEST_URL_TITLE_1 = "This is " + MOCK_URL_STRINGS[0] + "."
    # TEST_URL_TITLE_1 = MOCK_URL_TITLES[0]
    TEST_URL_TITLE_UPDATE = "MS Support"

    MAX_CHAR_LIM_URL_STRING = "Lorem ipsum dolor sit amet consectetur adipisicing elit. Obcaecati necessitatibus suscipit labore sapiente dignissimos hic voluptatem modi vero ipsam cupiditate?"

    MESSAGE_NO_URLS = "No URLs here - add one!"
