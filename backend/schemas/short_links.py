from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_serializer

from backend.schemas.base import BaseSchema
from backend.utils.strings.model_strs import MODELS


class ShortLinkResponseSchema(BaseSchema):
    """An active share short link for one UTub URL (just created, or reused)."""

    short_url: str = Field(
        alias=MODELS.SHORT_URL,
        description="Absolute share URL (https://<host>/s/<code>)",
    )
    expires_at: datetime = Field(
        alias=MODELS.EXPIRES_AT,
        description="UTC ISO-8601 timestamp after which the link stops working",
    )
    can_revoke: bool = Field(
        alias=MODELS.CAN_REVOKE,
        description="Whether the current user may revoke this link",
    )
    created: bool = Field(
        alias=MODELS.CREATED,
        description="True when this request made the link, false when an active one was reused",
    )

    @field_serializer("expires_at")
    def serialize_expires_at(self, value: datetime) -> str:
        return value.isoformat()


class ShortLinkRevokedResponseSchema(BaseSchema):
    """A short link revoked (hard-deleted)."""

    utub_url_id: int = Field(
        alias=MODELS.UTUB_URL_ID,
        description="ID of the UTub-URL whose short link was revoked",
    )
