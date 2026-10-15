from __future__ import annotations

from pydantic import AwareDatetime, BaseModel, Field

from backend.utubs.constants import TrashScope

MAX_POSTGRES_INTEGER_ID: int = 2147483647


class RestoreUrlRequest(BaseModel):
    destUtubId: int | None = Field(
        default=None,
        gt=0,
        le=MAX_POSTGRES_INTEGER_ID,
        description=(
            "Live UTub to restore into; required only when the origin UTub is trashed. "
            "The body itself is mandatory, so send {} when restoring in place."
        ),
        examples=[2],
    )


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
