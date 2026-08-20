from __future__ import annotations
from pydantic import BaseModel, Field, field_validator
from backend.utils.constants import TAG_CONSTANTS, URL_CONSTANTS
from backend.utils.strings.url_strs import URL_FAILURE
from backend.schemas.requests._sanitize import SanitizedStr
from backend.schemas.requests.tags import TagStringItem, validate_tag_strings


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
    tagStrings: list[TagStringItem] = Field(
        default_factory=list,
        max_length=TAG_CONSTANTS.MAX_URL_TAGS,
        description="Optional tags to apply to the URL on creation",
        examples=[["python", "web"]],
    )

    @field_validator("urlTitle", mode="after")
    @classmethod
    def title_not_empty_after_sanitize(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError(URL_FAILURE.INVALID_INPUT)
        return stripped

    @field_validator("tagStrings", mode="after")
    @classmethod
    def tag_strings_valid(cls, tag_strings: list[str]) -> list[str]:
        return validate_tag_strings(tag_strings)


class CopyUrlsRequest(BaseModel):
    sourceUtubId: int = Field(
        gt=0, description="Source UTub to copy URLs from", examples=[1]
    )
    utubUrlIds: list[int] = Field(
        min_length=1,
        max_length=URL_CONSTANTS.MAX_BULK_COPY_URLS,
        description="UTub-URL ids in the source UTub to copy",
        examples=[[1, 2, 3]],
    )
    destUtubIds: list[int] = Field(
        min_length=1,
        max_length=URL_CONSTANTS.MAX_BULK_COPY_DESTINATIONS,
        description="Destination UTub ids to copy the selected URLs into",
        examples=[[2, 3]],
    )

    @field_validator("utubUrlIds", mode="after")
    @classmethod
    def utub_url_ids_valid(cls, utub_url_ids: list[int]) -> list[int]:
        deduped = list(dict.fromkeys(utub_url_ids))
        if any(url_id <= 0 for url_id in deduped):
            raise ValueError(URL_FAILURE.INVALID_URL_ID)
        return deduped

    @field_validator("destUtubIds", mode="after")
    @classmethod
    def dest_utub_ids_valid(cls, dest_utub_ids: list[int]) -> list[int]:
        deduped = list(dict.fromkeys(dest_utub_ids))
        if any(dest_id <= 0 for dest_id in deduped):
            raise ValueError(URL_FAILURE.INVALID_URL_ID)
        return deduped


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
