from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import Field

from backend.schemas.base import BaseSchema
from backend.utils.strings.model_strs import MODELS as M, TAG_COUNTS_MODIFIED
from backend.utils.strings.tag_strs import UTUB_URL_IDS

if TYPE_CHECKING:
    from backend.models.utub_tags import Utub_Tags


class UtubTagSchema(BaseSchema):
    id: int = Field(
        alias=M.ID,
        description="Unique tag ID within the UTub",
    )
    tag_string: str = Field(
        alias=M.TAG_STRING,
        description="Tag label text",
    )
    tag_applied: int = Field(
        default=0,
        alias=M.TAG_APPLIED,
        description="Number of URLs in the UTub this tag is applied to",
    )


class UtubTagOnAddDeleteSchema(BaseSchema):
    utub_tag_id: int = Field(
        alias=M.UTUB_TAG_ID,
        description="Unique tag ID within the UTub",
    )
    tag_string: str = Field(
        alias=M.TAG_STRING,
        description="Tag label text",
    )

    @classmethod
    def from_orm_tag(cls, tag: Utub_Tags) -> UtubTagOnAddDeleteSchema:
        return cls(utub_tag_id=tag.id, tag_string=tag.tag_string)


UtubTagOnAddDeleteSchema.model_rebuild()


class UtubTagAddedToUtubResponseSchema(BaseSchema):
    utub_tag: UtubTagOnAddDeleteSchema = Field(
        alias=M.TAG,
        description="Tag that was added to the UTub",
    )
    tag_counts_modified: int = Field(
        alias=TAG_COUNTS_MODIFIED,
        description="New count of URLs this tag is applied to after addition",
    )


class UtubTagDeletedFromUtubResponseSchema(BaseSchema):
    utub_tag: UtubTagOnAddDeleteSchema = Field(
        alias=M.TAG,
        description="Tag that was deleted from the UTub",
    )
    utub_url_ids: list[int] = Field(
        alias=UTUB_URL_IDS,
        description="List of URL IDs that had this tag removed",
    )


class UrlTagModifiedResponseSchema(BaseSchema):
    utub_url_tag_ids: list[int] = Field(
        alias=M.URL_TAG_IDS,
        description="Updated list of tag IDs applied to the URL",
    )
    utub_tag: UtubTagOnAddDeleteSchema = Field(
        alias=M.TAG,
        description="Tag that was added or removed from the URL",
    )
    tag_counts_modified: int = Field(
        alias=TAG_COUNTS_MODIFIED,
        description="New count of URLs this tag is applied to after modification",
    )


class UrlTagsModifiedResponseSchema(BaseSchema):
    utub_url_tag_ids: list[int] = Field(
        alias=M.URL_TAG_IDS,
        description="Full updated list of tag IDs on the URL",
    )
    applied_tags: list[UtubTagSchema] = Field(
        alias=M.APPLIED_TAGS,
        description="Tags newly applied in this batch, with refreshed UTub-wide counts",
    )


class UrlBatchTagAppliedSchema(BaseSchema):
    utub_url_id: int = Field(
        alias=M.UTUB_URL_ID,
        description="UTub-URL id that was (or already had) tags applied",
    )
    utub_url_tag_ids: list[int] = Field(
        alias=M.URL_TAG_IDS,
        description="Full updated list of tag IDs on this URL",
    )
    applied_tags: list[UtubTagSchema] = Field(
        alias=M.APPLIED_TAGS,
        description="Tags newly applied to this URL in this request, with refreshed UTub-wide counts",
    )


class UrlBatchTagSkippedSchema(BaseSchema):
    utub_url_id: int = Field(
        alias=M.UTUB_URL_ID,
        description="UTub-URL id skipped in this request",
    )
    reason: str = Field(
        alias=M.SKIP_REASON,
        description="Machine-readable skip reason (BulkTagSkipReason value, e.g. 'overLimit')",
    )


class AddTagsToUrlsResponseSchema(BaseSchema):
    applied: list[UrlBatchTagAppliedSchema] = Field(
        alias=M.APPLIED,
        description="Every non-skipped URL (appliedTags may be empty when all tags were already present)",
    )
    skipped: list[UrlBatchTagSkippedSchema] = Field(
        alias=M.SKIPPED,
        description="URLs skipped because they were at the per-URL tag limit",
    )
