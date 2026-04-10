from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON


class BaseSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class StatusMessageResponseSchema(BaseSchema):
    """Status and message response"""

    status: Literal["Success", "Failure", "No change"] = Field(
        alias=STD_JSON.STATUS,
        description="Response status: Success, Failure, or No change",
    )
    message: str = Field(
        alias=STD_JSON.MESSAGE,
        description="Human-readable response message",
    )
