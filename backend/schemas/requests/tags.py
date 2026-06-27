from __future__ import annotations
from typing import Annotated

from pydantic import BaseModel, Field, field_validator

from backend.utils.constants import TAG_CONSTANTS
from backend.utils.strings.tag_strs import TAGS_FAILURE
from backend.schemas.requests._sanitize import SanitizedStr

TagStringItem = Annotated[
    SanitizedStr,
    Field(
        min_length=TAG_CONSTANTS.MIN_TAG_LENGTH,
        max_length=TAG_CONSTANTS.MAX_TAG_LENGTH,
    ),
]


def validate_tag_strings(tag_strings: list[str]) -> list[str]:
    """Strip, reject empties, and case-insensitively dedup a list of tag strings.

    Dedup is first-seen: the first casing encountered for a given lowercased
    value is kept, later differently-cased duplicates are dropped.

    Examples:
        >>> validate_tag_strings(["python", "Python", "web"])
        ['python', 'web']
        >>> validate_tag_strings(["  spaced  ", "Web"])
        ['spaced', 'Web']
    """
    deduplicated: list[str] = []
    seen_lowercased: set[str] = set()
    for tag_string in tag_strings:
        stripped = tag_string.strip()
        if stripped == "":
            raise ValueError(TAGS_FAILURE.TAG_EMPTY)
        lowercased = stripped.lower()
        if lowercased in seen_lowercased:
            continue
        seen_lowercased.add(lowercased)
        deduplicated.append(stripped)
    return deduplicated


class AddTagRequest(BaseModel):
    tagString: SanitizedStr = Field(
        min_length=TAG_CONSTANTS.MIN_TAG_LENGTH,
        max_length=TAG_CONSTANTS.MAX_TAG_LENGTH,
        description="Tag label to add",
        examples=["python"],
    )

    @field_validator("tagString", mode="after")
    @classmethod
    def tag_not_whitespace_only(cls, value: str) -> str:
        if value.replace(" ", "") == "":
            raise ValueError(TAGS_FAILURE.TAG_EMPTY)
        return value


class AddTagsRequest(BaseModel):
    tagStrings: list[TagStringItem] = Field(
        min_length=1,
        max_length=TAG_CONSTANTS.MAX_URL_TAGS,
        description="Tags to apply to the URL",
        examples=[["python", "web"]],
    )

    @field_validator("tagStrings", mode="after")
    @classmethod
    def tag_strings_valid(cls, tag_strings: list[str]) -> list[str]:
        return validate_tag_strings(tag_strings)
