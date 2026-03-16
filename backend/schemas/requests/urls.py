from __future__ import annotations
from pydantic import BaseModel, Field, field_validator
from backend.utils.constants import URL_CONSTANTS
from backend.utils.strings.url_strs import URL_FAILURE
from ._sanitize import SanitizedStr


class CreateURLRequest(BaseModel):
    urlString: str = Field(
        min_length=URL_CONSTANTS.MIN_URL_LENGTH,
        max_length=URL_CONSTANTS.MAX_URL_LENGTH,
    )
    urlTitle: SanitizedStr = Field(
        min_length=URL_CONSTANTS.MIN_URL_TITLE_LENGTH,
        max_length=URL_CONSTANTS.MAX_URL_TITLE_LENGTH,
    )

    @field_validator("urlTitle", mode="after")
    @classmethod
    def title_not_empty_after_sanitize(cls, value: str) -> str:
        if not value or value.strip() == "":
            raise ValueError(URL_FAILURE.INVALID_INPUT)
        return value


class UpdateURLStringRequest(BaseModel):
    urlString: str = Field(
        min_length=URL_CONSTANTS.MIN_URL_LENGTH,
        max_length=URL_CONSTANTS.MAX_URL_LENGTH,
    )


class UpdateURLTitleRequest(BaseModel):
    urlTitle: SanitizedStr = Field(
        min_length=URL_CONSTANTS.MIN_URL_TITLE_LENGTH,
        max_length=URL_CONSTANTS.MAX_URL_TITLE_LENGTH,
    )

    @field_validator("urlTitle", mode="after")
    @classmethod
    def title_not_empty_after_sanitize(cls, value: str) -> str:
        if not value or value.strip() == "":
            raise ValueError(URL_FAILURE.INVALID_INPUT)
        return value
