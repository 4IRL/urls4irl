class EMAIL_CONSTANTS:
    MAX_EMAIL_ATTEMPTS_IN_HOUR = 5
    WAIT_TO_RETRY_BEFORE_MAX_ATTEMPTS = 60
    WAIT_TO_ATTEMPT_AFTER_MAX_ATTEMPTS = 3600


class USER_CONSTANTS:
    MIN_USERNAME_LENGTH = 3
    MAX_USERNAME_LENGTH_ACTUAL = 25
    MAX_USERNAME_LENGTH = MAX_USERNAME_LENGTH_ACTUAL - 5
    MAX_EMAIL_LENGTH = 320
    MAX_PASSWORD_LENGTH = 166
    PASSWORD_RESET_ATTEMPTS = 5
    WAIT_TO_RETRY_FORGOT_PASSWORD_MIN = 60
    WAIT_TO_RETRY_FORGOT_PASSWORD_MAX = 3600


class UTUB_CONSTANTS:
    MAX_NAME_LENGTH = 30
    MIN_NAME_LENGTH = 1
    MAX_DESCRIPTION_LENGTH = 500


class URL_CONSTANTS:
    MAX_URL_TITLE_LENGTH = 100
    MAX_URL_LENGTH = 8000


class CONFIG_CONSTANTS:
    CSRF_EXPIRATION_HOURS = 1
    CSRF_EXPIRATION_MINUTES = CSRF_EXPIRATION_HOURS * 60
    CSRF_EXPIRATION_SECONDS = CSRF_EXPIRATION_MINUTES * 60


class CONSTANTS:
    EMAILS = EMAIL_CONSTANTS()
    USERS = USER_CONSTANTS()
    UTUBS = UTUB_CONSTANTS()
    URLS = URL_CONSTANTS()
    CONFIG = CONFIG_CONSTANTS()
