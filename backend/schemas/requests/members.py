from __future__ import annotations
from pydantic import BaseModel, Field
from backend.utils.constants import USER_CONSTANTS


class AddMemberRequest(BaseModel):
    username: str = Field(
        min_length=USER_CONSTANTS.MIN_USERNAME_LENGTH,
        max_length=USER_CONSTANTS.MAX_USERNAME_LENGTH,
    )
