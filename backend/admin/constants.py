from enum import IntEnum
from typing import Final


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
    TARGET_ERASED = 10
    METRIC_FLOW_LIMIT_REACHED = 11


# Key for the transaction-scoped Postgres advisory lock (`pg_advisory_xact_lock`)
# that serializes custom metric flow creation, so the count-then-insert cap check
# cannot be raced past FLOW_LIMITS.MAX_CUSTOM. A fixed 64-bit constant (ASCII
# "MFLOWCAP"); it must not collide with any other advisory lock key in the app.
METRIC_FLOW_CAP_LOCK_KEY: Final[int] = 0x4D464C4F57434150
