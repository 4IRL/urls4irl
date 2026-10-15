from __future__ import annotations

from pydantic import BaseModel, Field


class RestoreUrlRequest(BaseModel):
    destUtubId: int | None = Field(
        default=None,
        gt=0,
        description=(
            "Live UTub to restore into; required only when the origin UTub is trashed. "
            "The body itself is mandatory, so send {} when restoring in place."
        ),
        examples=[2],
    )
