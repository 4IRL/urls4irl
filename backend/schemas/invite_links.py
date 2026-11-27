from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, field_serializer

from backend.invite_links.constants import InviteLinkStatus
from backend.schemas.base import BaseSchema
from backend.utils.strings.json_strs import MESSAGE
from backend.utils.strings.model_strs import MODELS
from backend.utils.strings.utub_strs import UTUB_ID


class InviteLinkSchema(BaseSchema):
    """One UTub's current invite link as shown to its managers."""

    token: str = Field(alias=MODELS.TOKEN, description="The 22-character invite token")
    status: InviteLinkStatus = Field(
        alias=MODELS.STATUS,
        description="live, expired, used_up, creator_demoted or creator_not_allowed",
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

    preview_enabled: bool = Field(
        alias=MODELS.PREVIEW_ENABLED,
        description="Stored manager choice: show logged-out visitors a read-only preview",
    )
    preview_window_days: int = Field(
        alias=MODELS.PREVIEW_WINDOW_DAYS,
        description="Stored preview window in days: 1, 3 or 7",
    )
    preview_ends_at: datetime | None = Field(
        alias=MODELS.PREVIEW_ENDS_AT,
        description="Stored UTC ISO-8601 window end; null while the preview is off",
    )
    preview_effective_enabled: bool = Field(
        alias=MODELS.PREVIEW_EFFECTIVE_ENABLED,
        description="True when visitors can see the preview right now",
    )
    preview_effective_ends_at: datetime | None = Field(
        alias=MODELS.PREVIEW_EFFECTIVE_ENDS_AT,
        description="UTC ISO-8601 end of the preview, capped at the link's expiry; "
        "null while the preview is off",
    )

    @field_serializer("expires_at", "created_at")
    def serialize_datetimes(self, value: datetime) -> str:
        return value.isoformat()

    @field_serializer("preview_ends_at", "preview_effective_ends_at")
    def serialize_optional_datetimes(self, value: datetime | None) -> str | None:
        return None if value is None else value.isoformat()


class JoinViaInviteResponseSchema(BaseSchema):
    """Successful join (or already a member) through an invite link."""

    status: Literal["Success"] = Field(
        alias=MODELS.STATUS, description="Response status"
    )
    message: str = Field(alias=MESSAGE, description="Joined or already member")
    utub_id: int = Field(alias=UTUB_ID, description="ID of the UTub that was joined")
    already_member: bool = Field(
        alias=MODELS.ALREADY_MEMBER,
        description="True when the caller was already a member (nothing was consumed)",
    )


class InviteLinkResponseSchema(BaseSchema):
    """Envelope for the invite link routes; ``inviteLink`` is null when none exists."""

    status: Literal["Success"] = Field(
        alias=MODELS.STATUS, description="Response status"
    )
    invite_link: InviteLinkSchema | None = Field(
        alias=MODELS.INVITE_LINK,
        description="The current invite link, or null when the UTub has none",
    )
