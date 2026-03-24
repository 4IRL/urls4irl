from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, field_validator

from backend.utils.constants import USER_CONSTANTS
from backend.utils.strings.reset_password_strs import RESET_PASSWORD
from backend.utils.strings.splash_form_strs import EMAILS_NOT_IDENTICAL

from ._sanitize import SanitizedStr


class _UsernameStripMixin(BaseModel):
    @field_validator("username", mode="before", check_fields=False)
    @classmethod
    def strip_username_whitespace(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value


class LoginRequest(_UsernameStripMixin):
    username: SanitizedStr = Field(min_length=3, max_length=20)
    password: str = Field(min_length=1)


class RegisterRequest(_UsernameStripMixin):
    username: SanitizedStr = Field(min_length=3, max_length=20)
    email: EmailStr
    confirmEmail: str = Field(min_length=1)
    password: str = Field(
        min_length=USER_CONSTANTS.MIN_PASSWORD_LENGTH,
        max_length=USER_CONSTANTS.MAX_PASSWORD_LENGTH,
    )
    confirmPassword: str = Field(min_length=1)

    @field_validator("confirmEmail", mode="after")
    @classmethod
    def emails_must_match(cls, value: str, info: object) -> str:
        if "email" not in info.data:
            return value
        if value != info.data.get("email"):
            raise ValueError(EMAILS_NOT_IDENTICAL)
        return value

    @field_validator("confirmPassword", mode="after")
    @classmethod
    def passwords_must_match(cls, value: str, info: object) -> str:
        if "password" not in info.data:
            return value
        if value != info.data.get("password"):
            raise ValueError(RESET_PASSWORD.PASSWORDS_NOT_IDENTICAL)
        return value


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    newPassword: str = Field(min_length=12, max_length=64)
    confirmNewPassword: str = Field(min_length=1)

    @field_validator("confirmNewPassword", mode="after")
    @classmethod
    def passwords_must_match(cls, value: str, info: object) -> str:
        if "newPassword" not in info.data:
            return value
        if value != info.data.get("newPassword"):
            raise ValueError(RESET_PASSWORD.PASSWORDS_NOT_IDENTICAL)
        return value
