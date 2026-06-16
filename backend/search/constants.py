from __future__ import annotations

from enum import IntEnum, StrEnum


class SearchErrorCodes(IntEnum):
    INVALID_QUERY_PARAM = 1


class SearchFailureMessages:
    INVALID_QUERY = "Invalid search query."


class MatchedField(StrEnum):
    URL_STRING = "url"
    URL_TITLE = "title"
    TAG = "tag"
