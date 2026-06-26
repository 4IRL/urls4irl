from __future__ import annotations
from typing import Annotated

from pydantic import BaseModel, Field, field_validator

from backend.utils.constants import TAG_CONSTANTS
from backend.utils.strings.tag_strs import TAGS_FAILURE
from backend.schemas.requests._sanitize import SanitizedStr


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
    tagStrings: list[
        Annotated[
            SanitizedStr,
            Field(
                min_length=TAG_CONSTANTS.MIN_TAG_LENGTH,
                max_length=TAG_CONSTANTS.MAX_TAG_LENGTH,
            ),
        ]
    ] = Field(
        min_length=1,
        max_length=TAG_CONSTANTS.MAX_URL_TAGS,
        description="Tags to apply to the URL",
        examples=[["python", "web"]],
    )

    @field_validator("tagStrings", mode="after")
    @classmethod
    def tag_strings_valid(cls, tag_strings: list[str]) -> list[str]:
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
