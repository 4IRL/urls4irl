from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.utils.constants import SEARCH_CONSTANTS


class SearchQuerySchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    q: str = Field(
        min_length=SEARCH_CONSTANTS.MIN_QUERY_LENGTH,
        max_length=SEARCH_CONSTANTS.MAX_QUERY_LENGTH,
        description="Case-insensitive search term matched against URL strings, titles, and tags.",
        examples=["python"],
    )

    @field_validator("q", mode="before")
    @classmethod
    def _strip_query(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value
