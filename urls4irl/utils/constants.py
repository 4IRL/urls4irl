class EmailConstants:
    MAX_EMAIL_ATTEMPTS_IN_HOUR = 5
    WAIT_TO_RETRY_BEFORE_MAX_ATTEMPTS = 60
    WAIT_TO_ATTEMPT_AFTER_MAX_ATTEMPTS = 3600


class UserConstants:
    MAX_USERNAME_LENGTH_ACTUAL = 25
    MAX_USERNAME_LENGTH = MAX_USERNAME_LENGTH_ACTUAL - 5
    PASSWORD_RESET_ATTEMPTS = 5
    WAIT_TO_RETRY_PASSWORD_RESET_MIN = 60
    WAIT_TO_RETRY_PASSWORD_RESET_MAX = 3600