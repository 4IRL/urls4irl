from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.invite_links.constants import (
    INVITE_LINK_EXPIRY_DAYS_VALUES,
    INVITE_LINK_MAX_USES_VALUES,
    INVITE_LINK_PREVIEW_WINDOW_DAYS_VALUES,
)

# The Literals are built from INVITE_LINK_EXPIRY_DAYS_VALUES / INVITE_LINK_MAX_USES_VALUES.
# Strict mode rejects "7", but pydantic still lets true and 7.0 match an int
# Literal, so the base class rejects them first.
ExpiryDaysLiteral = Literal[*INVITE_LINK_EXPIRY_DAYS_VALUES]  # type: ignore[valid-type]
MaxUsesLiteral = Literal[*INVITE_LINK_MAX_USES_VALUES]  # type: ignore[valid-type]
PreviewWindowDaysLiteral = Literal[*INVITE_LINK_PREVIEW_WINDOW_DAYS_VALUES]  # type: ignore[valid-type]
_PREVIEW_WINDOW_DESCRIPTION = "Days the preview stays available: 1, 3 or 7"
_EXPIRES_DESCRIPTION = "Days until the link expires: 1, 7 or 30"
_MAX_USES_DESCRIPTION = (
    "How many people may join with the link: 1, 5, 10 or 25; null means unlimited"
)


class _ExactIntChoicesRequest(BaseModel):
    model_config = ConfigDict(strict=True)

    @field_validator(
        "expires_in_days",
        "max_uses",
        "preview_window_days",
        mode="before",
        check_fields=False,
    )
    @classmethod
    def require_exact_int(cls, value: object) -> object:
        if value is not None and type(value) is not int:
            raise ValueError("Must be a whole number from the allowed values")
        return value


class InviteLinkSettingsRequest(_ExactIntChoicesRequest):
    expires_in_days: ExpiryDaysLiteral = Field(
        default=7, description=_EXPIRES_DESCRIPTION
    )
    max_uses: MaxUsesLiteral | None = Field(
        default=None, description=_MAX_USES_DESCRIPTION
    )


class UpdateInviteLinkRequest(_ExactIntChoicesRequest):
    """Partial update: an absent field is left unchanged; an explicit null
    ``max_uses`` sets the link to unlimited."""

    expires_in_days: ExpiryDaysLiteral | None = Field(
        default=None, description=_EXPIRES_DESCRIPTION
    )
    max_uses: MaxUsesLiteral | None = Field(
        default=None, description=_MAX_USES_DESCRIPTION
    )

    preview_enabled: bool | None = Field(
        default=None,
        description="Show logged-out visitors a read-only preview; absent is unchanged",
    )
    preview_window_days: PreviewWindowDaysLiteral | None = Field(
        default=None, description=_PREVIEW_WINDOW_DESCRIPTION
    )

    @model_validator(mode="after")
    def validate_update_fields(self) -> UpdateInviteLinkRequest:
        if not self.model_fields_set:
            raise ValueError(
                "Provide expires_in_days, max_uses, preview_enabled or preview_window_days"
            )
        for field_name in ("expires_in_days", "preview_enabled", "preview_window_days"):
            if (
                field_name in self.model_fields_set
                and getattr(self, field_name) is None
            ):
                raise ValueError(f"{field_name} cannot be null")
        return self
