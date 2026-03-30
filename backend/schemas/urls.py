from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import Field

from backend.schemas.base import BaseSchema
from backend.schemas.tags import UtubTagOnAddDeleteSchema
from backend.utils.strings.model_strs import ADDED_BY, TAG_COUNTS_MODIFIED
from backend.utils.strings.model_strs import MODELS as M
from backend.utils.strings.utub_strs import UTUB_ID, UTUB_NAME

if TYPE_CHECKING:
    from backend.models.utub_urls import Utub_Urls


class UtubUrlSchema(BaseSchema):
    utub_url_id: int = Field(alias=M.UTUB_URL_ID)
    url_string: str = Field(alias=M.URL_STRING)
    utub_url_tag_ids: list[int] = Field(alias=M.URL_TAG_IDS)
    url_title: str = Field(alias=M.URL_TITLE)
    can_delete: bool = Field(alias=M.CAN_DELETE)

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
        )


class UtubUrlDetailSchema(BaseSchema):
    utub_url_id: int = Field(alias=M.UTUB_URL_ID)
    url_title: str = Field(alias=M.URL_TITLE)
    url_string: str = Field(alias=M.URL_STRING)
    url_tags: list[UtubTagOnAddDeleteSchema] = Field(alias=M.URL_TAGS)

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
    utub_url_id: int = Field(alias=M.UTUB_URL_ID)
    url_string: str = Field(alias=M.URL_STRING)
    url_title: str = Field(alias=M.URL_TITLE)

    @classmethod
    def from_orm_url(cls, utub_url: Utub_Urls) -> UtubUrlDeleteSchema:
        return cls(
            utub_url_id=utub_url.id,
            url_string=utub_url.standalone_url.url_string,
            url_title=utub_url.url_title,
        )


# Same 3-field shape as UtubUrlDeleteSchema: utubUrlID, urlString, urlTitle
UrlCreatedItemSchema = UtubUrlDeleteSchema


class UrlCreatedResponseSchema(BaseSchema):
    utub_id: int = Field(alias=UTUB_ID)
    added_by: int = Field(alias=ADDED_BY)
    url: UrlCreatedItemSchema = Field(alias=M.URL)


class UrlDeletedResponseSchema(BaseSchema):
    utub_id: int = Field(alias=UTUB_ID)
    url: UtubUrlDeleteSchema = Field(alias=M.URL)
    tag_counts_modified: dict[int, int] = Field(alias=TAG_COUNTS_MODIFIED)


class UrlReadResponseSchema(BaseSchema):
    url: UtubUrlDetailSchema = Field(alias=M.URL)


class UrlTitleUpdatedResponseSchema(BaseSchema):
    url: UtubUrlDetailSchema = Field(alias=M.URL)


class UrlUpdatedResponseSchema(BaseSchema):
    utub_id: int = Field(alias=UTUB_ID)
    utub_name: str = Field(alias=UTUB_NAME)
    url: UtubUrlDetailSchema = Field(alias=M.URL)


UtubUrlSchema.model_rebuild()
UtubUrlDetailSchema.model_rebuild()
