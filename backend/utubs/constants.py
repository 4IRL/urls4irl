from enum import IntEnum, StrEnum


class UTubErrorCodes(IntEnum):
    UNKNOWN_ERROR = 1
    INVALID_FORM_INPUT = 2
    UTUB_IS_LOCKED = 3
    NOT_IN_TRASH = 4
    UNABLE_TO_EMPTY_TRASH_ERROR = 5


class TrashScope(StrEnum):
    URLS = "urls"
    UTUBS = "utubs"
