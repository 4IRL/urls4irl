from __future__ import annotations

from typing import Literal

from pydantic import Field

from backend.schemas.base import BaseSchema
from backend.utils.strings.model_strs import MODELS


class ApiUserProfileSchema(BaseSchema):
    """Authenticated user's profile for the mobile /api/v1 surface."""

    id: int = Field(alias=MODELS.ID, description="Unique user ID")
    username: str = Field(alias=MODELS.USERNAME, description="Username of the user")
    email: str = Field(alias=MODELS.EMAIL, description="Email address of the user")
    email_validated: bool = Field(
        alias=MODELS.EMAIL_VALIDATED,
        description="Whether the user's email address has been validated",
    )


class ApiTokenPairResponseSchema(BaseSchema):
    """Access + refresh token pair issued by the /api/v1/auth endpoints."""

    access_token: str = Field(
        alias="accessToken",
        description="Short-lived HS256 JWT for Authorization: Bearer",
    )
    refresh_token: str = Field(
        alias="refreshToken",
        description="Opaque rotating refresh token; revoked server-side on logout",
    )
    token_type: Literal["Bearer"] = Field(
        alias="tokenType", description="Always 'Bearer'"
    )
    expires_in: int = Field(
        alias="expiresIn",
        description="Access token lifetime in seconds",
    )
    user: ApiUserProfileSchema = Field(
        description="Profile of the authenticated user, including emailValidated"
    )
