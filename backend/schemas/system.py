from __future__ import annotations

from pydantic import Field

from backend.schemas.base import BaseSchema
from backend.utils.strings.health_strs import HEALTH_STRS
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON


class HealthResponseSchema(BaseSchema):
    status: str = Field(alias=STD_JSON.STATUS, description="Service health status")


class DeepHealthComponentsSchema(BaseSchema):
    postgres: str = Field(
        alias=HEALTH_STRS.POSTGRES, description="up, down or not configured"
    )
    session_redis: str = Field(
        alias=HEALTH_STRS.SESSION_REDIS, description="up, down or not configured"
    )
    metrics_redis: str = Field(
        alias=HEALTH_STRS.METRICS_REDIS, description="up, down or not configured"
    )


class DeepHealthResponseSchema(BaseSchema):
    status: str = Field(alias=STD_JSON.STATUS, description="Overall health status")
    message: str | None = Field(
        default=None,
        alias=STD_JSON.MESSAGE,
        description="Names the unhealthy components (503 only)",
    )
    components: DeepHealthComponentsSchema = Field(
        alias=HEALTH_STRS.COMPONENTS, description="Per-component status"
    )
