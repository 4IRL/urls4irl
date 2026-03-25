from __future__ import annotations
from pydantic import BaseModel, Field, field_validator
from backend.utils.constants import TAG_CONSTANTS
from backend.utils.strings.tag_strs import TAGS_FAILURE
from backend.schemas.requests._sanitize import SanitizedStr


class AddTagRequest(BaseModel):
    tagString: SanitizedStr = Field(
        min_length=TAG_CONSTANTS.MIN_TAG_LENGTH,
        max_length=TAG_CONSTANTS.MAX_TAG_LENGTH,
    )

    @field_validator("tagString", mode="after")
    @classmethod
    def tag_not_whitespace_only(cls, value: str) -> str:
        if value.replace(" ", "") == "":
            raise ValueError(TAGS_FAILURE.TAG_EMPTY)
        return value
