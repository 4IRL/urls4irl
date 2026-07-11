from enum import IntEnum


class AdminActionErrorCodes(IntEnum):
    """Error codes carried in the JSON error envelope of admin mutation routes."""

    UNKNOWN_ERROR = 1
    INVALID_FORM_INPUT = 2
    SELF_ACTION_FORBIDDEN = 3
