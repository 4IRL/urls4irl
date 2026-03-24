from enum import IntEnum


class EmailValidationErrorCodes(IntEnum):
    UNKNOWN_EXCEPTION = 0
    MAX_TOTAL_EMAIL_VALIDATION_ATTEMPTS = 1
    MAX_TIME_EMAIL_VALIDATION_ATTEMPTS = 2
    EMAIL_SEND_FAILURE = 3
    MAILJET_SERVER_FAILURE = 4


class ForgotPasswordErrorCodes(IntEnum):
    INVALID_FORM_INPUT = 1
    # Value 2 intentionally skipped to preserve backward compatibility with legacy error codes
    EMAIL_SEND_FAILURE = 3


class LoginErrorCodes(IntEnum):
    ACCOUNT_NOT_EMAIL_VALIDATED = 1
    INVALID_FORM_INPUT = 2


class RegisterErrorCodes(IntEnum):
    ACCOUNT_NOT_EMAIL_VALIDATED = 1
    INVALID_FORM_INPUT = 2


class ResetPasswordErrorCodes(IntEnum):
    INVALID_FORM_INPUT = 1
