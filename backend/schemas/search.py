from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import Field

from backend.schemas.base import BaseSchema
from backend.schemas.tags import UtubTagOnAddDeleteSchema
from backend.search.constants import MatchedField
from backend.utils.strings.model_strs import MODELS as M
from backend.utils.strings.utub_strs import UTUB_ID, UTUB_NAME

if TYPE_CHECKING:
    from backend.models.utub_urls import Utub_Urls
    from backend.models.utubs import Utubs


class SearchHitSchema(BaseSchema):
    utub_url_id: int = Field(
        alias=M.UTUB_URL_ID,
        description="Utub_Urls association id (the .urlRow[utuburlid] DOM key)",
    )
    url_string: str = Field(alias=M.URL_STRING, description="The URL string")
    url_title: str = Field(
        alias=M.URL_TITLE, description="Per-UTub display title for the URL"
    )
    url_tags: list[UtubTagOnAddDeleteSchema] = Field(
        alias=M.URL_TAGS, description="Tags applied to this URL in its UTub"
    )
    matched_fields: list[MatchedField] = Field(
        alias=M.MATCHED_FIELDS,
        description="Which fields the query matched (title/url/tag) — Phase 2 highlights these",
    )

    @classmethod
    def from_orm_url(
        cls, utub_url: Utub_Urls, matched_fields: list[MatchedField]
    ) -> SearchHitSchema:
        return cls(
            utub_url_id=utub_url.id,
            url_string=utub_url.standalone_url.url_string,
            url_title=utub_url.url_title,
            url_tags=[
                UtubTagOnAddDeleteSchema(
                    utub_tag_id=tag[M.UTUB_TAG_ID], tag_string=tag[M.TAG_STRING]
                )
                for tag in utub_url.associated_tags
            ],
            matched_fields=matched_fields,
        )


class SearchUtubGroupSchema(BaseSchema):
    utub_id: int = Field(
        alias=UTUB_ID, description="Source UTub id — Phase 2 calls selectUTub(utub_id)"
    )
    utub_name: str = Field(
        alias=UTUB_NAME, description="Source UTub name for the group label"
    )
    urls: list[SearchHitSchema] = Field(
        alias=M.URLS, description="Matching URLs within this UTub, ranked best-first"
    )

    @classmethod
    def from_utub_urls(
        cls, utub: Utubs, utub_urls: list[tuple[Utub_Urls, list[MatchedField]]]
    ) -> SearchUtubGroupSchema:
        return cls(
            utub_id=utub.id,
            utub_name=utub.name,
            urls=[
                SearchHitSchema.from_orm_url(utub_url, matched_fields)
                for utub_url, matched_fields in utub_urls
            ],
        )


class SearchResultsSchema(BaseSchema):
    results: list[SearchUtubGroupSchema] = Field(
        alias=M.SEARCH_RESULTS,
        description="Groups ranked best-first; one group per source UTub with ≥1 matching URL",
    )


SearchHitSchema.model_rebuild()
SearchUtubGroupSchema.model_rebuild()
