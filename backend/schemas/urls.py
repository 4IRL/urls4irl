from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import ConfigDict, Field, field_serializer

from backend.schemas.base import BaseSchema
from backend.schemas.tags import UtubTagOnAddDeleteSchema, UtubTagSchema
from backend.utils.strings.model_strs import ADDED_BY, MODELS, TAG_COUNTS_MODIFIED
from backend.utils.strings.utub_strs import UTUB_ID, UTUB_NAME

if TYPE_CHECKING:
    from backend.models.utub_urls import Utub_Urls


class UtubUrlSchema(BaseSchema):
    utub_url_id: int = Field(
        alias=MODELS.UTUB_URL_ID, description="Unique ID of the URL within the UTub"
    )
    url_string: str = Field(alias=MODELS.URL_STRING, description="The URL string")
    utub_url_tag_ids: list[int] = Field(
        alias=MODELS.URL_TAG_IDS, description="List of tag IDs applied to this URL"
    )
    url_title: str = Field(
        alias=MODELS.URL_TITLE, description="Display title for the URL"
    )
    can_delete: bool = Field(
        alias=MODELS.CAN_DELETE,
        description="Whether the current user can delete this URL",
    )
    added_at: datetime = Field(
        alias="addedAt", description="Timestamp the URL was added to the UTub"
    )
    added_by_user_id: int = Field(
        alias=ADDED_BY,
        description="User ID of the member who added this URL to the UTub "
        "(resolved to a username on the frontend via the UTub member list)",
    )

    @classmethod
    def from_orm_url(
        cls, utub_url: Utub_Urls, current_user_id: int, viewer_is_manager: bool
    ) -> UtubUrlSchema:
        return cls(
            utub_url_id=utub_url.id,
            url_string=utub_url.standalone_url.url_string,
            utub_url_tag_ids=utub_url.associated_tag_ids,
            url_title=utub_url.url_title,
            can_delete=current_user_id == utub_url.user_id or viewer_is_manager,
            added_at=utub_url.added_at,
            added_by_user_id=utub_url.user_id,
        )

    @field_serializer("added_at")
    def serialize_added_at(self, value: datetime) -> str:
        return value.isoformat()


class UtubUrlDetailSchema(BaseSchema):
    utub_url_id: int = Field(
        alias=MODELS.UTUB_URL_ID, description="Unique ID of the URL within the UTub"
    )
    url_title: str = Field(
        alias=MODELS.URL_TITLE, description="Display title for the URL"
    )
    url_string: str = Field(alias=MODELS.URL_STRING, description="The URL string")
    url_tags: list[UtubTagOnAddDeleteSchema] = Field(
        alias=MODELS.URL_TAGS, description="List of tags applied to this URL"
    )

    @classmethod
    def from_orm_url(cls, utub_url: Utub_Urls) -> UtubUrlDetailSchema:
        return cls(
            utub_url_id=utub_url.id,
            url_title=utub_url.url_title,
            url_string=utub_url.standalone_url.url_string,
            url_tags=[
                UtubTagOnAddDeleteSchema(
                    utub_tag_id=associated_tag[MODELS.UTUB_TAG_ID],
                    tag_string=associated_tag[MODELS.TAG_STRING],
                )
                for associated_tag in utub_url.associated_tags
            ],
        )


class UtubUrlDeleteSchema(BaseSchema):
    utub_url_id: int = Field(
        alias=MODELS.UTUB_URL_ID, description="Unique ID of the URL within the UTub"
    )
    url_string: str = Field(alias=MODELS.URL_STRING, description="The URL string")
    url_title: str = Field(
        alias=MODELS.URL_TITLE, description="Display title for the URL"
    )

    @classmethod
    def from_orm_url(cls, utub_url: Utub_Urls) -> UtubUrlDeleteSchema:
        return cls(
            utub_url_id=utub_url.id,
            url_string=utub_url.standalone_url.url_string,
            url_title=utub_url.url_title,
        )


class UrlCreatedItemSchema(UtubUrlDeleteSchema):
    """URL item shape for creation responses (UtubUrlDeleteSchema fields + tag IDs)."""

    model_config = ConfigDict(title="UrlCreatedItemSchema")

    utub_url_tag_ids: list[int] = Field(
        default_factory=list,
        alias=MODELS.URL_TAG_IDS,
        description="Tag IDs applied to the URL on creation",
    )
    added_at: datetime = Field(
        alias="addedAt", description="Timestamp the URL was added to the UTub"
    )

    @field_serializer("added_at")
    def serialize_added_at(self, value: datetime) -> str:
        return value.isoformat()


class UrlCreatedResponseSchema(BaseSchema):
    utub_id: int = Field(
        alias=UTUB_ID, description="ID of the UTub the URL was added to"
    )
    added_by: int = Field(
        alias=ADDED_BY, description="User ID of the user who added the URL"
    )
    url: UrlCreatedItemSchema = Field(
        alias=MODELS.URL, description="URL item that was created"
    )
    applied_tags: list[UtubTagSchema] = Field(
        default_factory=list,
        alias=MODELS.APPLIED_TAGS,
        description="Tags applied to the URL on creation, with UTub-wide counts",
    )
    revived_from_trash: bool = Field(
        default=False,
        alias=MODELS.REVIVED_FROM_TRASH,
        description="True when the add revived this UTub's trashed row for the URL instead of inserting a new one.",
    )
    lost_tag_count: int = Field(
        default=0,
        alias=MODELS.LOST_TAG_COUNT,
        description="On a revive, how many of the URL's tags were deleted from the UTub while it was trashed.",
    )


class UrlDeletedResponseSchema(BaseSchema):
    utub_id: int = Field(
        alias=UTUB_ID, description="ID of the UTub the URL was deleted from"
    )
    url: UtubUrlDeleteSchema = Field(
        alias=MODELS.URL, description="URL item that was deleted"
    )
    tag_counts_modified: dict[int, int] = Field(
        alias=TAG_COUNTS_MODIFIED,
        description="Map of tag ID to new applied count after deletion",
    )


# Kept distinct from UrlTitleUpdatedResponseSchema for OpenAPI schema generation.
class UrlReadResponseSchema(BaseSchema):
    url: UtubUrlDetailSchema = Field(
        alias=MODELS.URL, description="Detailed URL item retrieved"
    )


class UrlTitleUpdatedResponseSchema(BaseSchema):
    url: UtubUrlDetailSchema = Field(
        alias=MODELS.URL, description="Detailed URL item with updated title"
    )


class UrlUpdatedResponseSchema(BaseSchema):
    utub_id: int = Field(alias=UTUB_ID, description="ID of the UTub containing the URL")
    utub_name: str = Field(
        alias=UTUB_NAME, description="Name of the UTub containing the URL"
    )
    url: UtubUrlDetailSchema = Field(
        alias=MODELS.URL,
        description="Detailed URL item with updated URL string. On a revive-on-edit this is the revived row, not the edited one.",
    )
    revived_from_trash: bool = Field(
        default=False,
        alias=MODELS.REVIVED_FROM_TRASH,
        description="True when the edit revived this UTub's trashed row for the new URL and trashed the edited row.",
    )
    lost_tag_count: int = Field(
        default=0,
        alias=MODELS.LOST_TAG_COUNT,
        description="On a revive, how many of the trashed row's tags were deleted from the UTub while it was trashed.",
    )
    replaced_utub_url_id: int | None = Field(
        default=None,
        alias=MODELS.REPLACED_UTUB_URL_ID,
        description="On a revive, the id of the edited row that was trashed in favour of the revived one; null otherwise.",
    )
    applied_tags: list[UtubTagSchema] = Field(
        default_factory=list,
        alias=MODELS.APPLIED_TAGS,
        description="On a revive, every tag on the revived row with its UTub-wide count; empty otherwise.",
    )
    tag_counts_modified: dict[int, int] = Field(
        default_factory=dict,
        alias=TAG_COUNTS_MODIFIED,
        description="On a revive, map of tag ID to new UTub-wide applied count for the trashed row's tags; empty otherwise.",
    )


class UrlCopiedItemSchema(BaseSchema):
    source_utub_url_id: int = Field(
        alias=MODELS.SOURCE_UTUB_URL_ID,
        description="Source Utub_Urls id the copy originated from (for per-card cues)",
    )
    utub_url_id: int = Field(
        alias=MODELS.UTUB_URL_ID,
        description="New destination Utub_Urls id created by the copy",
    )
    url_string: str = Field(
        alias=MODELS.URL_STRING, description="The copied URL string"
    )
    url_title: str = Field(
        alias=MODELS.URL_TITLE, description="Display title carried over to the copy"
    )


class UrlCopySkippedSchema(BaseSchema):
    utub_url_id: int = Field(
        alias=MODELS.UTUB_URL_ID,
        description="Source Utub_Urls id skipped because it is already in the destination",
    )
    reason: str = Field(
        alias=MODELS.SKIP_REASON,
        description="Machine-readable skip reason (BulkCopySkipReason value, e.g. 'duplicate')",
    )


class PerDestinationCopyResultSchema(BaseSchema):
    dest_utub_id: int = Field(
        alias=MODELS.DEST_UTUB_ID, description="Destination UTub id"
    )
    status: str = Field(
        alias=MODELS.STATUS, description="DestCopyStatus value: 'ok' or 'locked'"
    )
    copied: list[UrlCopiedItemSchema] = Field(
        alias=MODELS.COPIED,
        description="URLs copied into this destination",
    )
    skipped: list[UrlCopySkippedSchema] = Field(
        alias=MODELS.SKIPPED,
        description="URLs skipped because they are already in this destination",
    )


class CopyUrlsResponseSchema(BaseSchema):
    results: list[PerDestinationCopyResultSchema] = Field(
        alias=MODELS.RESULTS,
        description="Per-destination copy results",
    )
    total_copied: int = Field(
        alias=MODELS.TOTAL_COPIED,
        description="Total number of URLs copied across all destinations",
    )
    total_skipped: int = Field(
        alias=MODELS.TOTAL_SKIPPED,
        description="Total number of URLs skipped across all destinations",
    )


class UrlDeleteSkippedSchema(BaseSchema):
    utub_url_id: int = Field(
        alias=MODELS.UTUB_URL_ID,
        description="Utub_Urls id skipped because the user may not delete it",
    )
    reason: str = Field(
        alias=MODELS.SKIP_REASON,
        description="Machine-readable skip reason (BulkDeleteSkipReason value, e.g. 'forbidden')",
    )


class DeleteUrlsResponseSchema(BaseSchema):
    deleted: list[UtubUrlDeleteSchema] = Field(
        alias=MODELS.DELETED,
        description="URLs deleted from the UTub",
    )
    skipped: list[UrlDeleteSkippedSchema] = Field(
        alias=MODELS.SKIPPED,
        description="URLs skipped because the user may not delete them",
    )
    tag_counts_modified: dict[int, int] = Field(
        alias=TAG_COUNTS_MODIFIED,
        description="Map of tag ID to new applied count after the bulk delete",
    )
    total_deleted: int = Field(
        alias=MODELS.TOTAL_DELETED,
        description="Total number of URLs deleted from the UTub",
    )
    total_skipped: int = Field(
        alias=MODELS.TOTAL_SKIPPED,
        description="Total number of URLs skipped during the bulk delete",
    )


UtubUrlSchema.model_rebuild()
UtubUrlDetailSchema.model_rebuild()
