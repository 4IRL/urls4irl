from __future__ import annotations
from pydantic import BaseModel, Field, field_validator
from backend.utils.constants import UTUB_CONSTANTS
from backend.utils.strings.utub_strs import UTUB_FAILURE
from backend.schemas.requests._sanitize import SanitizedStr, OptionalSanitizedStr


class CreateUTubRequest(BaseModel):
    utubName: SanitizedStr = Field(
        min_length=UTUB_CONSTANTS.MIN_NAME_LENGTH,
        max_length=UTUB_CONSTANTS.MAX_NAME_LENGTH,
        description="Name of the UTub to create",
    )
    utubDescription: OptionalSanitizedStr = Field(
        default=None,
        description="Optional description for the UTub",
    )

    @field_validator("utubName", mode="after")
    @classmethod
    def name_not_whitespace_only(cls, value: str) -> str:
        if value.replace(" ", "") == "":
            raise ValueError(UTUB_FAILURE.UTUB_NAME_EMPTY)
        return value

    @field_validator("utubDescription", mode="after")
    @classmethod
    def description_max_length(cls, value: str | None) -> str | None:
        if value is not None and len(value) > UTUB_CONSTANTS.MAX_DESCRIPTION_LENGTH:
            raise ValueError(
                f"String should have at most {UTUB_CONSTANTS.MAX_DESCRIPTION_LENGTH} characters"
            )
        return value


class UpdateUTubNameRequest(BaseModel):
    utubName: SanitizedStr = Field(
        min_length=UTUB_CONSTANTS.MIN_NAME_LENGTH,
        max_length=UTUB_CONSTANTS.MAX_NAME_LENGTH,
        description="New name for the UTub",
    )

    @field_validator("utubName", mode="after")
    @classmethod
    def name_not_whitespace_only(cls, value: str) -> str:
        if value.replace(" ", "") == "":
            raise ValueError(UTUB_FAILURE.UTUB_NAME_EMPTY)
        return value


class UpdateUTubDescriptionRequest(BaseModel):
    utubDescription: OptionalSanitizedStr = Field(
        default=None,
        description="New description for the UTub, or empty to clear",
    )

    @field_validator("utubDescription", mode="after")
    @classmethod
    def description_max_length(cls, value: str | None) -> str | None:
        if value is not None and len(value) > UTUB_CONSTANTS.MAX_DESCRIPTION_LENGTH:
            raise ValueError(
                f"String should have at most {UTUB_CONSTANTS.MAX_DESCRIPTION_LENGTH} characters"
            )
        return value
