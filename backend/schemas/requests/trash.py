from __future__ import annotations

from pydantic import BaseModel, Field

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
