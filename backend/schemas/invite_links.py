from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, field_serializer

from backend.invite_links.constants import InviteLinkStatus
from backend.schemas.base import BaseSchema
from backend.utils.strings.model_strs import MODELS


class InviteLinkSchema(BaseSchema):
    """One UTub's current invite link as shown to its managers."""

    token: str = Field(alias=MODELS.TOKEN, description="The 22-character invite token")
    status: InviteLinkStatus = Field(
        alias=MODELS.STATUS,
        description="live, expired, used_up or creator_demoted",
    )
    expires_at: datetime = Field(
        alias=MODELS.EXPIRES_AT,
        description="UTC ISO-8601 timestamp after which the link stops working",
    )
    max_uses: int | None = Field(
        alias=MODELS.MAX_USES, description="Use limit; null means unlimited"
    )
    use_count: int = Field(
        alias=MODELS.USE_COUNT, description="How many people joined with this link"
    )
    created_at: datetime = Field(
        alias=MODELS.CREATED_AT, description="UTC ISO-8601 creation timestamp"
    )
    creator_username: str | None = Field(
        alias=MODELS.CREATOR_USERNAME,
        description="Username of the link's creator; null when that account was erased",
    )

    @field_serializer("expires_at", "created_at")
    def serialize_datetimes(self, value: datetime) -> str:
        return value.isoformat()


class InviteLinkResponseSchema(BaseSchema):
    """Envelope for the invite link routes; ``inviteLink`` is null when none exists."""

    status: Literal["Success"] = Field(
        alias=MODELS.STATUS, description="Response status"
    )
    invite_link: InviteLinkSchema | None = Field(
        alias=MODELS.INVITE_LINK,
        description="The current invite link, or null when the UTub has none",
    )
