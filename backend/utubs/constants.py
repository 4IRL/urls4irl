from enum import IntEnum, StrEnum


class UTubErrorCodes(IntEnum):
    UNKNOWN_ERROR = 1
    INVALID_FORM_INPUT = 2
    UTUB_IS_LOCKED = 3
    NOT_IN_TRASH = 4
    UNABLE_TO_EMPTY_TRASH_ERROR = 5
    PIN_LIMIT_REACHED = 6  # 409


# Most UTubs one user may have pinned (counted on live UTubs only).
MAX_PINNED_UTUBS = 5

# First key of the two-int ``pg_advisory_xact_lock(namespace, user_id)`` that
# serializes one user's pin writes. Must fit in int32; the second key is the
# (int4) user id.
PIN_CAP_ADVISORY_LOCK_NAMESPACE = 0x50494E53


class TrashScope(StrEnum):
    URLS = "urls"
    UTUBS = "utubs"
