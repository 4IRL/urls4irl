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
            "Comma-separated, ordered subset of fields to search (e.g. "
            "`title,url,tag`). Membership restricts which of title/url/tag match; "
            "order sets ranking priority, first = highest. Omitted/empty = all "
            "fields in default priority."
        ),
        examples=[["title", "url", "tag"]],
        json_schema_extra={"explode": False},
    )

    @field_validator("q", mode="before")
    @classmethod
    def _strip_query(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value

    @field_validator("fields", mode="before")
    @classmethod
    def _split_comma_delimited_fields(cls, value: object) -> object:
        """Split the comma-separated `fields` query string into an ordered list.

        The param is sent as a single comma-delimited string (e.g.
        `?fields=title,url,tag`) for URL readability. Whitespace around each
        token is stripped and empty tokens (from leading/trailing/double commas)
        are dropped, so `"title, url"` and `"title,,url"` both yield
        `["title", "url"]`. An empty/blank string yields `[]`, which the
        after-validator then normalizes to the default field priority.
        Non-string input (already a list) passes through unchanged.
        """
        if isinstance(value, str):
            return [token.strip() for token in value.split(",") if token.strip()]
        return value

    @model_validator(mode="after")
    def _default_and_dedupe_fields(self) -> Self:
        if not self.fields:
            self.fields = list(DEFAULT_SEARCH_FIELDS)
        elif len(set(self.fields)) != len(self.fields):
            raise ValueError(
                "Each search field (title/url/tag) may appear at most once."
            )
        return self
