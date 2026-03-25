from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, ValidationInfo, field_validator

from backend.utils.constants import USER_CONSTANTS
from backend.utils.strings.reset_password_strs import RESET_PASSWORD
from backend.utils.strings.splash_form_strs import EMAILS_NOT_IDENTICAL

from backend.schemas.requests._sanitize import SanitizedStr


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
    confirm_email: str = Field(min_length=1, alias="confirmEmail")
    password: str = Field(
        min_length=USER_CONSTANTS.MIN_PASSWORD_LENGTH,
        max_length=USER_CONSTANTS.MAX_PASSWORD_LENGTH,
    )
    confirm_password: str = Field(min_length=1, alias="confirmPassword")

    @field_validator("confirm_email", mode="after")
    @classmethod
    def emails_must_match(cls, value: str, info: ValidationInfo) -> str:
        if "email" not in info.data:
            return value
        if value != info.data.get("email"):
            raise ValueError(EMAILS_NOT_IDENTICAL)
        return value

    @field_validator("confirm_password", mode="after")
    @classmethod
    def passwords_must_match(cls, value: str, info: ValidationInfo) -> str:
        if "password" not in info.data:
            return value
        if value != info.data.get("password"):
            raise ValueError(RESET_PASSWORD.PASSWORDS_NOT_IDENTICAL)
        return value


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=12, max_length=64, alias="newPassword")
    confirm_new_password: str = Field(min_length=1, alias="confirmNewPassword")

    @field_validator("confirm_new_password", mode="after")
    @classmethod
    def passwords_must_match(cls, value: str, info: ValidationInfo) -> str:
        if "new_password" not in info.data:
            return value
        if value != info.data.get("new_password"):
            raise ValueError(RESET_PASSWORD.PASSWORDS_NOT_IDENTICAL)
        return value
