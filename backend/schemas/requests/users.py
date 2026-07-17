from __future__ import annotations

from pydantic import BaseModel, Field


class ProviderLinkRequest(BaseModel):
    password: str | None = Field(
        default=None,
        description=(
            "Current account password, re-authenticated before linking a new "
            "OAuth provider. Required for accounts that have a password; "
            "password-less (OAuth-only) accounts omit it and prove ownership "
            "via an OAuth round-trip to an already-linked provider instead"
        ),
    )
