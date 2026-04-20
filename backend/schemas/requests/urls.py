from __future__ import annotations
from pydantic import BaseModel, Field, field_validator
from backend.utils.constants import URL_CONSTANTS
from backend.utils.strings.url_strs import URL_FAILURE
from backend.schemas.requests._sanitize import SanitizedStr


class CreateURLRequest(BaseModel):
    urlString: str = Field(
        min_length=URL_CONSTANTS.MIN_URL_LENGTH,
        max_length=URL_CONSTANTS.MAX_URL_LENGTH,
        description="URL string to add",
        examples=["https://example.com"],
    )
    urlTitle: SanitizedStr = Field(
        min_length=URL_CONSTANTS.MIN_URL_TITLE_LENGTH,
        max_length=URL_CONSTANTS.MAX_URL_TITLE_LENGTH,
        description="Display title for the URL",
    )

    @field_validator("urlTitle", mode="after")
    @classmethod
    def title_not_empty_after_sanitize(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError(URL_FAILURE.INVALID_INPUT)
        return stripped


class UpdateURLStringRequest(BaseModel):
    urlString: str = Field(
        min_length=URL_CONSTANTS.MIN_URL_LENGTH,
        max_length=URL_CONSTANTS.MAX_URL_LENGTH,
        description="New URL string to replace the existing one",
        examples=["https://example.com"],
    )


class UpdateURLTitleRequest(BaseModel):
    urlTitle: SanitizedStr = Field(
        min_length=URL_CONSTANTS.MIN_URL_TITLE_LENGTH,
        max_length=URL_CONSTANTS.MAX_URL_TITLE_LENGTH,
        description="New display title for the URL",
    )

    @field_validator("urlTitle", mode="after")
    @classmethod
    def title_not_empty_after_sanitize(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError(URL_FAILURE.INVALID_INPUT)
        return stripped
