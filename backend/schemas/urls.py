from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import ConfigDict, Field, field_serializer

from backend.schemas.base import BaseSchema
from backend.schemas.tags import UtubTagOnAddDeleteSchema, UtubTagSchema
from backend.utils.strings.model_strs import ADDED_BY, TAG_COUNTS_MODIFIED
from backend.utils.strings.model_strs import MODELS as M
from backend.utils.strings.utub_strs import UTUB_ID, UTUB_NAME

if TYPE_CHECKING:
    from backend.models.utub_urls import Utub_Urls


class UtubUrlSchema(BaseSchema):
    utub_url_id: int = Field(
        alias=M.UTUB_URL_ID, description="Unique ID of the URL within the UTub"
    )
    url_string: str = Field(alias=M.URL_STRING, description="The URL string")
    utub_url_tag_ids: list[int] = Field(
        alias=M.URL_TAG_IDS, description="List of tag IDs applied to this URL"
    )
    url_title: str = Field(alias=M.URL_TITLE, description="Display title for the URL")
    can_delete: bool = Field(
        alias=M.CAN_DELETE,
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
        cls, utub_url: Utub_Urls, current_user_id: int, utub_creator: int
    ) -> UtubUrlSchema:
        return cls(
            utub_url_id=utub_url.id,
            url_string=utub_url.standalone_url.url_string,
            utub_url_tag_ids=utub_url.associated_tag_ids,
            url_title=utub_url.url_title,
            can_delete=current_user_id == utub_url.user_id
            or current_user_id == utub_creator,
            added_at=utub_url.added_at,
            added_by_user_id=utub_url.user_id,
        )

    @field_serializer("added_at")
    def serialize_added_at(self, value: datetime) -> str:
        return value.isoformat()


class UtubUrlDetailSchema(BaseSchema):
    utub_url_id: int = Field(
        alias=M.UTUB_URL_ID, description="Unique ID of the URL within the UTub"
    )
    url_title: str = Field(alias=M.URL_TITLE, description="Display title for the URL")
    url_string: str = Field(alias=M.URL_STRING, description="The URL string")
    url_tags: list[UtubTagOnAddDeleteSchema] = Field(
        alias=M.URL_TAGS, description="List of tags applied to this URL"
    )

    @classmethod
    def from_orm_url(cls, utub_url: Utub_Urls) -> UtubUrlDetailSchema:
        return cls(
            utub_url_id=utub_url.id,
            url_title=utub_url.url_title,
            url_string=utub_url.standalone_url.url_string,
            url_tags=[
                UtubTagOnAddDeleteSchema(
                    utub_tag_id=t[M.UTUB_TAG_ID], tag_string=t[M.TAG_STRING]
                )
                for t in utub_url.associated_tags
            ],
        )


class UtubUrlDeleteSchema(BaseSchema):
    utub_url_id: int = Field(
        alias=M.UTUB_URL_ID, description="Unique ID of the URL within the UTub"
    )
    url_string: str = Field(alias=M.URL_STRING, description="The URL string")
    url_title: str = Field(alias=M.URL_TITLE, description="Display title for the URL")

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
        alias=M.URL_TAG_IDS,
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
        alias=M.URL, description="URL item that was created"
    )
    applied_tags: list[UtubTagSchema] = Field(
        default_factory=list,
        alias=M.APPLIED_TAGS,
        description="Tags applied to the URL on creation, with UTub-wide counts",
    )


class UrlDeletedResponseSchema(BaseSchema):
    utub_id: int = Field(
        alias=UTUB_ID, description="ID of the UTub the URL was deleted from"
    )
    url: UtubUrlDeleteSchema = Field(
        alias=M.URL, description="URL item that was deleted"
    )
    tag_counts_modified: dict[int, int] = Field(
        alias=TAG_COUNTS_MODIFIED,
        description="Map of tag ID to new applied count after deletion",
    )


# Kept distinct from UrlTitleUpdatedResponseSchema for OpenAPI schema generation.
class UrlReadResponseSchema(BaseSchema):
    url: UtubUrlDetailSchema = Field(
        alias=M.URL, description="Detailed URL item retrieved"
    )


class UrlTitleUpdatedResponseSchema(BaseSchema):
    url: UtubUrlDetailSchema = Field(
        alias=M.URL, description="Detailed URL item with updated title"
    )


class UrlUpdatedResponseSchema(BaseSchema):
    utub_id: int = Field(alias=UTUB_ID, description="ID of the UTub containing the URL")
    utub_name: str = Field(
        alias=UTUB_NAME, description="Name of the UTub containing the URL"
    )
    url: UtubUrlDetailSchema = Field(
        alias=M.URL, description="Detailed URL item with updated URL string"
    )


class UrlCopiedItemSchema(BaseSchema):
    source_utub_url_id: int = Field(
        alias=M.SOURCE_UTUB_URL_ID,
        description="Source Utub_Urls id the copy originated from (for per-card cues)",
    )
    utub_url_id: int = Field(
        alias=M.UTUB_URL_ID,
        description="New destination Utub_Urls id created by the copy",
    )
    url_string: str = Field(alias=M.URL_STRING, description="The copied URL string")
    url_title: str = Field(
        alias=M.URL_TITLE, description="Display title carried over to the copy"
    )


class UrlCopySkippedSchema(BaseSchema):
    utub_url_id: int = Field(
        alias=M.UTUB_URL_ID,
        description="Source Utub_Urls id skipped because it is already in the destination",
    )
    reason: str = Field(
        alias=M.SKIP_REASON,
        description="Machine-readable skip reason (BulkCopySkipReason value, e.g. 'duplicate')",
    )


class PerDestinationCopyResultSchema(BaseSchema):
    dest_utub_id: int = Field(alias=M.DEST_UTUB_ID, description="Destination UTub id")
    status: str = Field(
        alias=M.STATUS, description="DestCopyStatus value: 'ok' or 'locked'"
    )
    copied: list[UrlCopiedItemSchema] = Field(alias=M.COPIED)
    skipped: list[UrlCopySkippedSchema] = Field(alias=M.SKIPPED)


class CopyUrlsResponseSchema(BaseSchema):
    results: list[PerDestinationCopyResultSchema] = Field(alias=M.SEARCH_RESULTS)
    total_copied: int = Field(alias=M.TOTAL_COPIED)
    total_skipped: int = Field(alias=M.TOTAL_SKIPPED)


UtubUrlSchema.model_rebuild()
UtubUrlDetailSchema.model_rebuild()
