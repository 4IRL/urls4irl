from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_serializer

from backend.schemas.base import BaseSchema
from backend.schemas.tags import UtubTagSchema
from backend.schemas.urls import UtubUrlSchema
from backend.utils.strings.model_strs import MODELS, TAG_COUNTS_MODIFIED
from backend.utils.strings.utub_strs import UTUB_ID, UTUB_NAME


class TrashedUrlItemSchema(BaseSchema):
    """One URL row in the current user's Trash (trashed on its own or with its UTub)"""

    utub_url_id: int = Field(
        alias=MODELS.UTUB_URL_ID,
        description="ID of the trashed UTub-URL row",
    )
    url_string: str = Field(
        alias=MODELS.URL_STRING,
        description="The URL string",
    )
    url_title: str = Field(
        alias=MODELS.URL_TITLE,
        description="Title of the URL in its origin UTub",
    )
    utub_id: int = Field(
        alias=UTUB_ID,
        description="ID of the origin UTub",
    )
    utub_name: str = Field(
        alias=UTUB_NAME,
        description="Name of the origin UTub",
    )
    origin_utub_trashed: bool = Field(
        alias=MODELS.ORIGIN_UTUB_TRASHED,
        description="Whether the origin UTub is itself in Trash",
    )
    origin_utub_locked: bool = Field(
        alias=MODELS.ORIGIN_UTUB_LOCKED,
        description="Whether the origin UTub is locked (frozen to mutations)",
    )
    trashed_with_utub: bool = Field(
        alias=MODELS.TRASHED_WITH_UTUB,
        description="Whether the URL was trashed only because its UTub was trashed",
    )
    deleted_at: datetime = Field(
        alias=MODELS.DELETED_AT,
        description="Effective time the URL entered Trash (ISO 8601)",
    )
    expires_at: datetime = Field(
        alias=MODELS.EXPIRES_AT,
        description="When the URL is permanently deleted (ISO 8601)",
    )
    deleted_by_user_id: int = Field(
        alias=MODELS.DELETED_BY,
        description="User ID of whoever put the URL in Trash (effective)",
    )
    deleted_by_username: str = Field(
        alias=MODELS.DELETED_BY_USERNAME,
        description="Username of whoever put the URL in Trash (effective)",
    )
    added_by_user_id: int = Field(
        alias=MODELS.ADDED_BY,
        description="User ID of the member who added the URL",
    )
    added_by_username: str = Field(
        alias=MODELS.ADDED_BY_USERNAME,
        description="Username of the member who added the URL",
    )
    can_restore: bool = Field(
        alias=MODELS.CAN_RESTORE,
        description="Whether the current user can restore this URL right now",
    )
    can_delete: bool = Field(
        alias=MODELS.CAN_DELETE,
        description="Whether the current user can permanently delete this URL right now",
    )

    @field_serializer("deleted_at", "expires_at")
    def serialize_datetimes(self, value: datetime) -> str:
        return value.isoformat()


class TrashedUtubItemSchema(BaseSchema):
    """One trashed UTub in the current creator's Trash"""

    utub_id: int = Field(
        alias=UTUB_ID,
        description="ID of the trashed UTub",
    )
    utub_name: str = Field(
        alias=UTUB_NAME,
        description="Name of the trashed UTub",
    )
    utub_description: str | None = Field(
        alias=MODELS.UTUB_DESCRIPTION,
        description="Description of the trashed UTub",
    )
    deleted_at: datetime = Field(
        alias=MODELS.DELETED_AT,
        description="When the UTub entered Trash (ISO 8601)",
    )
    expires_at: datetime = Field(
        alias=MODELS.EXPIRES_AT,
        description="When the UTub is permanently deleted (ISO 8601)",
    )
    deleted_by_user_id: int = Field(
        alias=MODELS.DELETED_BY,
        description="User ID of whoever put the UTub in Trash",
    )
    deleted_by_username: str = Field(
        alias=MODELS.DELETED_BY_USERNAME,
        description="Username of whoever put the UTub in Trash",
    )
    url_count: int = Field(
        alias=MODELS.URL_COUNT,
        description="Number of live URLs a restore would bring back",
    )
    member_count: int = Field(
        alias=MODELS.MEMBER_COUNT,
        description="Number of members in the UTub",
    )
    is_locked: bool = Field(
        alias=MODELS.IS_LOCKED,
        description="Whether the UTub is locked (frozen to mutations)",
    )
    can_restore: bool = Field(
        alias=MODELS.CAN_RESTORE,
        description="Whether the current user can restore this UTub right now",
    )
    can_delete: bool = Field(
        alias=MODELS.CAN_DELETE,
        description="Whether the current user can permanently delete this UTub right now",
    )

    @field_serializer("deleted_at", "expires_at")
    def serialize_datetimes(self, value: datetime) -> str:
        return value.isoformat()


class TrashListResponseSchema(BaseSchema):
    """The current user's Trash: actionable URL rows and trashed UTubs"""

    urls: list[TrashedUrlItemSchema] = Field(
        alias=MODELS.URLS,
        description="Trashed URLs the user may act on, newest first",
    )
    utubs: list[TrashedUtubItemSchema] = Field(
        alias=MODELS.UTUBS,
        description="Trashed UTubs the user created, newest first",
    )
    current_user: int = Field(
        alias=MODELS.CURRENT_USER,
        description="ID of the currently authenticated user",
    )
    retention_days: int = Field(
        alias=MODELS.RETENTION_DAYS,
        description="Days an item stays in Trash before permanent deletion",
    )
    listed_at: datetime = Field(
        alias=MODELS.LISTED_AT,
        description="Server time the list was read (ISO 8601)",
    )

    @field_serializer("listed_at")
    def serialize_listed_at(self, value: datetime) -> str:
        return value.isoformat()


class UrlRestoredResponseSchema(BaseSchema):
    """A trashed URL restored, in place or into a destination UTub"""

    utub_id: int = Field(
        alias=UTUB_ID,
        description="ID of the UTub the URL is now live in",
    )
    utub_name: str = Field(
        alias=UTUB_NAME,
        description="Name of the UTub the URL is now live in",
    )
    url: UtubUrlSchema = Field(
        alias=MODELS.URL,
        description="The restored URL card, with its original adder and added-at time",
    )
    restored_to_destination: bool = Field(
        default=False,
        alias=MODELS.RESTORED_TO_DESTINATION,
        description="True when the URL was moved into a destination UTub instead of restored in place",
    )
    applied_tags: list[UtubTagSchema] = Field(
        default_factory=list,
        alias=MODELS.APPLIED_TAGS,
        description="Tags that survived on the restored URL, with UTub-wide applied counts",
    )
    tag_counts_modified: dict[int, int] = Field(
        default_factory=dict,
        alias=TAG_COUNTS_MODIFIED,
        description="Map of tag ID to new UTub-wide applied count after the restore",
    )
    lost_tag_count: int = Field(
        default=0,
        alias=MODELS.LOST_TAG_COUNT,
        description="How many of the URL's tags were deleted from the UTub while it sat in Trash",
    )


class UtubRestoredResponseSchema(BaseSchema):
    """A trashed UTub restored to the creator's live UTubs"""

    utub_id: int = Field(
        alias=UTUB_ID,
        description="ID of the restored UTub",
    )
    utub_name: str = Field(
        alias=UTUB_NAME,
        description="Name of the restored UTub",
    )
    utub_description: str | None = Field(
        alias=MODELS.UTUB_DESCRIPTION,
        description="Description of the restored UTub, or null if not set",
    )
    member_role: str = Field(
        alias=MODELS.MEMBER_ROLE,
        description="The restoring user's role in the UTub (always the creator role)",
    )
    is_locked: bool = Field(
        alias=MODELS.IS_LOCKED,
        description="Whether the UTub is locked (frozen to mutations)",
    )
    restored_url_count: int = Field(
        alias=MODELS.RESTORED_URL_COUNT,
        description="Number of live URLs that came back with the UTub",
    )


class UrlPurgedResponseSchema(BaseSchema):
    """A trashed URL permanently deleted. Live tag counts are unaffected: trashed rows never count."""

    utub_id: int = Field(
        alias=UTUB_ID,
        description="ID of the UTub the URL was deleted from",
    )
    utub_url_id: int = Field(
        alias=MODELS.UTUB_URL_ID,
        description="ID of the permanently deleted UTub-URL row",
    )


class UtubPurgedResponseSchema(BaseSchema):
    """A trashed UTub permanently deleted by its creator, with all of its children"""

    utub_id: int = Field(
        alias=UTUB_ID,
        description="ID of the permanently deleted UTub",
    )
    utub_name: str = Field(
        alias=UTUB_NAME,
        description="Name of the permanently deleted UTub",
    )
    purged_url_count: int = Field(
        alias=MODELS.PURGED_URL_COUNT,
        description="Number of URL rows (live and trashed) deleted with the UTub",
    )
