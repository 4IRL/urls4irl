from __future__ import annotations

from pydantic import BaseModel, Field, ValidationInfo, field_validator

from backend.schemas.requests._sanitize import SanitizedStr
from backend.schemas.requests.splash import _UsernameStripMixin
from backend.utils.constants import USER_CONSTANTS
from backend.utils.strings.reset_password_strs import RESET_PASSWORD


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


class ChangePasswordRequest(BaseModel):
    # Aliases are mandatory (no populate_by_name), so the JS client sends
    # currentPassword / newPassword / confirmNewPassword.
    password: str = Field(
        min_length=USER_CONSTANTS.MIN_REQUIRED_FIELD_LENGTH,
        alias="currentPassword",
        description=(
            "Current account password, re-authenticated before the change. "
            "Length is validated against the stored hash in the service (min 1, "
            "like LoginRequest), not against the new-password policy"
        ),
    )
    new_password: str = Field(
        min_length=USER_CONSTANTS.MIN_PASSWORD_LENGTH,
        max_length=USER_CONSTANTS.MAX_PASSWORD_INPUT_LENGTH,
        alias="newPassword",
        description="New password for the account",
    )
    confirm_new_password: str = Field(
        min_length=USER_CONSTANTS.MIN_REQUIRED_FIELD_LENGTH,
        alias="confirmNewPassword",
        description="New password confirmation, must match new password",
    )

    @field_validator("confirm_new_password", mode="after")
    @classmethod
    def passwords_must_match(cls, value: str, info: ValidationInfo) -> str:
        if "new_password" not in info.data:
            return value
        if value != info.data.get("new_password"):
            raise ValueError(RESET_PASSWORD.PASSWORDS_NOT_IDENTICAL)
        return value


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
