from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.search.constants import DEFAULT_SEARCH_FIELDS, MatchedField
from backend.utils.constants import SEARCH_CONSTANTS


class SearchQuerySchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    q: str = Field(
        min_length=SEARCH_CONSTANTS.MIN_QUERY_LENGTH,
        max_length=SEARCH_CONSTANTS.MAX_QUERY_LENGTH,
        description="Case-insensitive search term matched against URL strings, titles, and tags.",
        examples=["python"],
    )
    fields: list[MatchedField] = Field(
        default_factory=lambda: list(DEFAULT_SEARCH_FIELDS),
        max_length=len(MatchedField),
        description=(
            "Ordered subset of fields to search (membership restricts which of "
            "title/url/tag match; order sets ranking priority, first = highest). "
            "Omitted/empty = all fields in default priority."
        ),
        examples=[["title", "url", "tag"]],
    )

    @field_validator("q", mode="before")
    @classmethod
    def _strip_query(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def _default_and_dedupe_fields(self) -> Self:
        if not self.fields:
            self.fields = list(DEFAULT_SEARCH_FIELDS)
        elif len(set(self.fields)) != len(self.fields):
            raise ValueError(
                "Each search field (title/url/tag) may appear at most once."
            )
        return self
