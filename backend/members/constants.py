from enum import IntEnum


class UTubMembersErrorCodes(IntEnum):
    UNKNOWN_EXCEPTION = 1
    INVALID_FORM_INPUT = 2
    UTUB_IS_LOCKED = 3
