from enum import IntEnum


class AdminActionErrorCodes(IntEnum):
    """Error codes carried in the JSON error envelope of admin mutation routes."""

    UNKNOWN_ERROR = 1
    INVALID_FORM_INPUT = 2
    SELF_ACTION_FORBIDDEN = 3
    ALREADY_IN_TARGET_STATE = 4
    TARGET_NOT_FOUND = 5
    OAUTH_ONLY_ACCOUNT = 6
    LAST_ADMIN_FORBIDDEN = 7
    EMAIL_SEND_FAILURE = 8
    LAST_CREDENTIAL_FORBIDDEN = 9
