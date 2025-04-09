from src.models.utub_members import Member_Role
from src.utils.strings.utub_strs import UTUB_ID_QUERY_PARAM


class EMAIL_CONSTANTS:
    MAX_EMAIL_ATTEMPTS_IN_HOUR = 5
    WAIT_TO_RETRY_BEFORE_MAX_ATTEMPTS = 60
    WAIT_TO_ATTEMPT_AFTER_MAX_ATTEMPTS = 3600


class USER_CONSTANTS:
    MIN_USERNAME_LENGTH = 3
    MAX_USERNAME_LENGTH_ACTUAL = 25
    MAX_USERNAME_LENGTH = MAX_USERNAME_LENGTH_ACTUAL - 5
    MAX_EMAIL_LENGTH = 320
    MIN_PASSWORD_LENGTH = 12
    MAX_PASSWORD_LENGTH = 166
    PASSWORD_RESET_ATTEMPTS = 5
    WAIT_TO_RETRY_FORGOT_PASSWORD_MIN = 60
    WAIT_TO_RETRY_FORGOT_PASSWORD_MAX = 3600


class UTUB_CONSTANTS:
    MAX_NAME_LENGTH = 30
    MIN_NAME_LENGTH = 1
    MAX_DESCRIPTION_LENGTH = 500
    MEMBER_ROLES = Member_Role


class URL_CONSTANTS:
    MIN_URL_TITLE_LENGTH = 1
    MIN_URL_LENGTH = 1
    MAX_URL_TITLE_LENGTH = 100
    MAX_URL_LENGTH = 8000
    MAX_NUM_OF_URLS_TO_ACCESS = 3


class TAG_CONSTANTS:
    MIN_TAG_LENGTH = 1
    MAX_TAG_LENGTH = 30
    MAX_URL_TAGS = 5


class CONFIG_CONSTANTS:
    SESSION_LIFETIME = 31 * 86400  # 31 days before session and CSRF expiration


class STRINGS:
    UTUB_QUERY_PARAM = UTUB_ID_QUERY_PARAM


class CONSTANTS:
    EMAILS = EMAIL_CONSTANTS()
    USERS = USER_CONSTANTS()
    UTUBS = UTUB_CONSTANTS()
    URLS = URL_CONSTANTS()
    TAGS = TAG_CONSTANTS()
    CONFIG = CONFIG_CONSTANTS()
    STRINGS = STRINGS()
