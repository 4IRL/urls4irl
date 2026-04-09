from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import Field

from backend.schemas.base import BaseSchema, StatusMessageResponseSchema
from backend.utils.strings.model_strs import MODELS as M
from backend.utils.strings.utub_strs import UTUB_ID
from backend.utils.strings.user_strs import MEMBER, REDIRECT_URL

if TYPE_CHECKING:
    from backend.models.users import Users


class UserSchema(BaseSchema):
    id: int = Field(alias=M.ID, description="Unique user ID")
    username: str = Field(alias=M.USERNAME, description="Username of the user")


MemberSchema = UserSchema


class UtubSummaryItemSchema(BaseSchema):
    id: int = Field(alias=M.ID, description="Unique UTub ID")
    name: str = Field(alias=M.NAME, description="Name of the UTub")
    member_role: str = Field(
        alias=M.MEMBER_ROLE,
        description="Role of the current user in the UTub",
    )


class UtubSummaryListSchema(BaseSchema):
    """List of UTub summaries"""

    utubs: list[UtubSummaryItemSchema] = Field(
        alias=M.UTUBS,
        description="List of UTubs the user is a member of",
    )

    @classmethod
    def from_user(cls, user: Users) -> UtubSummaryListSchema:
        sorted_utubs = sorted(
            user.utubs_is_member_of,
            key=lambda m: m.to_utub.last_updated,
            reverse=True,
        )
        return cls(
            utubs=[
                UtubSummaryItemSchema(
                    id=m.to_utub.id,
                    name=m.to_utub.name,
                    member_role=m.member_role.value,
                )
                for m in sorted_utubs
            ]
        )


UtubSummaryListSchema.model_rebuild()


class LoginRedirectResponseSchema(BaseSchema):
    """Login successful with redirect URL"""

    redirect_url: str = Field(
        alias=REDIRECT_URL,
        description="URL to redirect to after login",
    )


class MemberModifiedResponseSchema(BaseSchema):
    utub_id: int = Field(
        alias=UTUB_ID,
        description="ID of the UTub the member was added to or removed from",
    )
    member: UserSchema = Field(
        alias=MEMBER,
        description="User object for the member added or removed",
    )


class RegisterResponseSchema(StatusMessageResponseSchema):
    pass


class ForgotPasswordResponseSchema(StatusMessageResponseSchema):
    pass


class ResetPasswordResponseSchema(StatusMessageResponseSchema):
    pass


class EmailValidationResponseSchema(StatusMessageResponseSchema):
    pass
