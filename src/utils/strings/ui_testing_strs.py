# Internal libraries
from src.mocks.mock_constants import USERNAME_BASE, MOCK_UTUB_NAME_BASE, EMAIL_SUFFIX


class UI_TEST_STRINGS:
    BASE_URL = "http://127.0.0.1:"

    TEST_USER_1 = USERNAME_BASE + "1"
    # Using password as email
    TEST_PASSWORD_1 = TEST_USER_1 + EMAIL_SUFFIX

    TEST_USER_UNLISTED = USERNAME_BASE + "_UNLISTED"
    TEST_PASSWORD_UNLISTED = TEST_USER_UNLISTED + EMAIL_SUFFIX

    # Register
    HEADER_MODAL_EMAIL_VALIDATION = "Validate Your Email!"

    MESSAGE_USERNAME_TAKEN = "That username is already taken. Please choose another."
    MESSAGE_EMAIL_UNVALIDATED = "An account already exists with that information but the email has not been validated."
    MESSAGE_EMAIL_TAKEN = (
        "That email is already associated with a username. Forgot password?"
    )

    # UTubs
    TEST_UTUB_1 = MOCK_UTUB_NAME_BASE + "1"
    BODY_MODAL_UTUB_SAME_NAME = "You already have a UTub with a similar name."
    BODY_MODAL_UTUB_DELETE = "This action is irreverisible!"

    MAX_CHAR_LIM_UTUB_NAME = "Lorem ipsum dolor sit amet consectetur adipisicing elit. Obcaecati necessitatibus suscipit labore sapiente dignissimos hic voluptatem modi vero ipsam cupiditate?"

    # Members
    BODY_MODAL_MEMBER_DELETE = (
        "This member will no longer have access to the URLs in this UTub."
    )
    BODY_MODAL_LEAVE_UTUB = "You will no longer have access to the URLs in this UTub."

    # Tags

    # URLs
    BODY_MODAL_URL_DELETE = (
        "This member will no longer have access to the URLs in this UTub."
    )

    MAX_CHAR_LIM_URL_STRING = "Lorem ipsum dolor sit amet consectetur adipisicing elit. Obcaecati necessitatibus suscipit labore sapiente dignissimos hic voluptatem modi vero ipsam cupiditate?"
    MAX_CHAR_LIM_URL_TITLE = "Lorem ipsum dolor sit amet consectetur adipisicing elit. Obcaecati necessitatibus suscipit labore sapiente dignissimos hic voluptatem modi vero ipsam cupiditate?"
