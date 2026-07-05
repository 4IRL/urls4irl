from __future__ import annotations

from pydantic import Field

from backend.schemas.base import BaseSchema
from backend.utils.strings.model_strs import MODELS as M


class ApiUserProfileSchema(BaseSchema):
    """Authenticated user's profile for the mobile /api/v1 surface."""

    id: int = Field(alias=M.ID, description="Unique user ID")
    username: str = Field(alias=M.USERNAME, description="Username of the user")
    email: str = Field(alias=M.EMAIL, description="Email address of the user")
    email_validated: bool = Field(
        alias=M.EMAIL_VALIDATED,
        description="Whether the user's email address has been validated",
    )
