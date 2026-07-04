from enum import IntEnum

LOGIN_FAILURE_REASON_UNKNOWN_USER = "unknown_user"
LOGIN_FAILURE_REASON_BAD_PASSWORD = "bad_password"
LOGIN_FAILURE_REASON_EMAIL_UNVERIFIED = "email_unverified"
LOGIN_FAILURE_REASON_OAUTH_ONLY = "oauth_only"
LOGIN_FAILURE_REASON_OAUTH_EMAIL_COLLISION = "oauth_email_collision"
LOGIN_FAILURE_REASON_OAUTH_CONSENT_DECLINED = "oauth_consent_declined"
LOGIN_FAILURE_REASON_OAUTH_GENERIC_FAILURE = "oauth_generic_failure"
LOGIN_FAILURE_REASON_OAUTH_UNVERIFIED_EMAIL = "oauth_unverified_email"


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


class OAuthErrorCodes(IntEnum):
    INVALID_FORM_INPUT = 1


class RegisterErrorCodes(IntEnum):
    ACCOUNT_NOT_EMAIL_VALIDATED = 1
    INVALID_FORM_INPUT = 2


class ResetPasswordErrorCodes(IntEnum):
    INVALID_FORM_INPUT = 1
