from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON


class BaseSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class StatusMessageResponseSchema(BaseSchema):
    status: str = Field(alias=STD_JSON.STATUS)
    message: str = Field(alias=STD_JSON.MESSAGE)
