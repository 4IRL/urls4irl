from enum import IntEnum, StrEnum


class UTubTagErrorCodes(IntEnum):
    UNKNOWN_EXCEPTION = 1
    INVALID_FORM_INPUT = 2
    UTUB_IS_LOCKED = 3
    TAGGING_NOT_ALLOWED = 4
    TAG_DELETE_NOT_ALLOWED = 5


class URLTagErrorCodes(IntEnum):
    UNKNOWN_EXCEPTION = 1
    INVALID_FORM_INPUT = 2
    UTUB_IS_LOCKED = 3
    TAGGING_NOT_ALLOWED = 4


class BulkTagSkipReason(StrEnum):
    OVER_LIMIT = "overLimit"
