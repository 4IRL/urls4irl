from __future__ import annotations

from pydantic import Field

from backend.schemas.base import BaseSchema
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON


class HealthResponseSchema(BaseSchema):
    status: str = Field(alias=STD_JSON.STATUS)
