from __future__ import annotations

from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

from backend.schemas.requests._sanitize import SanitizedStr
from backend.utils.constants import USER_CONSTANTS
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.reset_password_strs import RESET_PASSWORD
from backend.utils.strings.splash_form_strs import EMAILS_NOT_IDENTICAL, INVITE_NEXT


class _UsernameStripMixin(BaseModel):
    @field_validator("username", mode="before", check_fields=False)
    @classmethod
    def strip_username_whitespace(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value


class LoginRequest(_UsernameStripMixin):
    username: SanitizedStr = Field(
        min_length=USER_CONSTANTS.MIN_USERNAME_LENGTH,
        max_length=USER_CONSTANTS.MAX_USERNAME_LENGTH,
        description="Username for login",
        examples=["john_doe"],
    )
    password: str = Field(
        min_length=USER_CONSTANTS.MIN_REQUIRED_FIELD_LENGTH,
        description="Password for login",
    )


class RegisterRequest(_UsernameStripMixin):
    username: SanitizedStr = Field(
        min_length=USER_CONSTANTS.MIN_USERNAME_LENGTH,
        max_length=USER_CONSTANTS.MAX_USERNAME_LENGTH,
        description="Username for the new account",
        examples=["john_doe"],
    )
    email: EmailStr = Field(
        description="Email address for the new account",
        examples=["user@example.com"],
    )
    confirm_email: str = Field(
        min_length=USER_CONSTANTS.MIN_EMAIL_LENGTH,
        alias="confirmEmail",
        description="Email confirmation, must match email",
    )
    password: str = Field(
        min_length=USER_CONSTANTS.MIN_PASSWORD_LENGTH,
        max_length=USER_CONSTANTS.MAX_PASSWORD_INPUT_LENGTH,
        description="Password for the new account",
    )
    confirm_password: str = Field(
        min_length=USER_CONSTANTS.MIN_REQUIRED_FIELD_LENGTH,
        alias="confirmPassword",
        description="Password confirmation, must match password",
    )
    invite_next: str | None = Field(
        default=None,
        alias=INVITE_NEXT,
        description=(
            "Invite path from the splash page's single next param, "
            "e.g. /invite/<token>/register; ignored unless valid"
        ),
    )

    @field_validator("invite_next", mode="before")
    @classmethod
    def non_string_invite_next_is_absent(cls, value: object) -> str | None:
        return value if isinstance(value, str) else None

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
    email: EmailStr = Field(
        description="Email address associated with the account",
        examples=["user@example.com"],
    )


class ResendRegistrationEmailRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    email: EmailStr | None = Field(
        default=None,
        description="Email address of the pending registration to resend confirmation for",
        examples=["user@example.com"],
    )
    resend_token: str | None = Field(
        default=None,
        alias=STD_JSON.RESEND_TOKEN,
        max_length=2000,
        description="Resend token returned by a login on an unconfirmed account",
    )

    @field_validator("resend_token", mode="after")
    @classmethod
    def empty_resend_token_is_unset(cls, value: str | None) -> str | None:
        return value or None

    @model_validator(mode="after")
    def exactly_one_of_email_or_token(self) -> Self:
        if (self.email is None) == (self.resend_token is None):
            raise ValueError("Provide exactly one of email or resendToken")
        return self


class GoogleOAuthCallbackQuerySchema(BaseModel):
    code: str | None = None
    state: str | None = None
    error: str | None = None


class GitHubOAuthCallbackQuerySchema(BaseModel):
    code: str | None = None
    state: str | None = None
    error: str | None = None


class ConfirmLinkRequest(BaseModel):
    password: str = Field(
        min_length=USER_CONSTANTS.MIN_REQUIRED_FIELD_LENGTH,
        description=(
            "Password of the existing account that owns the colliding email, "
            "re-authenticated before the pending OAuth identity is linked"
        ),
    )


class ResetPasswordRequest(BaseModel):
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
