from __future__ import annotations

from pydantic import AwareDatetime, BaseModel, Field, field_validator

from backend.schemas.requests.urls import dedup_and_reject_non_positive
from backend.utils.constants import URL_CONSTANTS
from backend.utils.strings.url_strs import URL_FAILURE
from backend.utubs.constants import TrashScope


class RestoreUrlRequest(BaseModel):
    destUtubId: int | None = Field(
        default=None,
        gt=0,
        le=2147483647,
        description=(
            "Live UTub to restore into; required only when the origin UTub is trashed. "
            "The body itself is mandatory, so send {} when restoring in place."
        ),
        examples=[2],
    )


class RestoreUrlsRequest(BaseModel):
    utubUrlIds: list[int] = Field(
        min_length=1,
        max_length=URL_CONSTANTS.MAX_BULK_DELETE_URLS,
        description="Trashed UTub-URL ids of this UTub to restore in place",
        examples=[[1, 2, 3]],
    )

    @field_validator("utubUrlIds", mode="after")
    @classmethod
    def utub_url_ids_valid(cls, utub_url_ids: list[int]) -> list[int]:
        return dedup_and_reject_non_positive(utub_url_ids, URL_FAILURE.INVALID_URL_ID)


class EmptyTrashRequest(BaseModel):
    scope: TrashScope = Field(
        description="Which Trash tab to empty: 'urls' or 'utubs'",
        examples=["urls"],
    )
    listedAt: AwareDatetime = Field(
        description=(
            "The listedAt of the Trash list the user was looking at (timezone-aware "
            "ISO 8601). Only items that entered Trash at or before it are deleted, so "
            "an item trashed after the list was read is never swept."
        ),
        examples=["2026-10-15T12:00:00+00:00"],
    )
