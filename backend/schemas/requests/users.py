from __future__ import annotations

from pydantic import BaseModel, Field

from backend.schemas.requests._sanitize import SanitizedStr
from backend.schemas.requests.splash import _UsernameStripMixin
from backend.utils.constants import USER_CONSTANTS


class ChangeUsernameRequest(_UsernameStripMixin):
    # Field is literally named ``username`` so ``_UsernameStripMixin``'s
    # before-strip validator applies. The wire key is the field name (no
    # ``populate_by_name``/alias), so the JS client sends ``{ "username": ... }``.
    username: SanitizedStr = Field(
        min_length=USER_CONSTANTS.MIN_USERNAME_LENGTH,
        max_length=USER_CONSTANTS.MAX_USERNAME_LENGTH,
        description="The new username for the authenticated account",
        examples=["john_doe"],
    )


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
