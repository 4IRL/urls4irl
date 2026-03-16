from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import Field

from backend.schemas.base import BaseSchema
from backend.utils.strings.model_strs import MODELS as M, TAG_COUNTS_MODIFIED
from backend.utils.strings.tag_strs import UTUB_URL_IDS

if TYPE_CHECKING:
    from backend.models.utub_tags import Utub_Tags


class UtubTagSchema(BaseSchema):
    id: int = Field(alias=M.ID)
    tag_string: str = Field(alias=M.TAG_STRING)
    tag_applied: int = Field(default=0, alias=M.TAG_APPLIED)


class UtubTagOnAddDeleteSchema(BaseSchema):
    utub_tag_id: int = Field(alias=M.UTUB_TAG_ID)
    tag_string: str = Field(alias=M.TAG_STRING)

    @classmethod
    def from_orm_tag(cls, tag: Utub_Tags) -> UtubTagOnAddDeleteSchema:
        return cls(utub_tag_id=tag.id, tag_string=tag.tag_string)


UtubTagOnAddDeleteSchema.model_rebuild()


class UtubTagAddedToUtubResponseSchema(BaseSchema):
    utub_tag: UtubTagOnAddDeleteSchema = Field(alias=M.TAG)
    tag_counts_modified: int = Field(alias=TAG_COUNTS_MODIFIED)


class UtubTagDeletedFromUtubResponseSchema(BaseSchema):
    utub_tag: UtubTagOnAddDeleteSchema = Field(alias=M.TAG)
    utub_url_ids: list[int] = Field(alias=UTUB_URL_IDS)


class UrlTagModifiedResponseSchema(BaseSchema):
    utub_url_tag_ids: list[int] = Field(alias=M.URL_TAG_IDS)
    utub_tag: UtubTagOnAddDeleteSchema = Field(alias=M.TAG)
    tag_counts_modified: int = Field(alias=TAG_COUNTS_MODIFIED)
