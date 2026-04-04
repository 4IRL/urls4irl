from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import Field

from backend.schemas.base import BaseSchema
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.model_strs import MODELS as M
from backend.utils.strings.utub_strs import UTUB_ID
from backend.utils.strings.user_strs import MEMBER, REDIRECT_URL

if TYPE_CHECKING:
    from backend.models.users import Users


class UserSchema(BaseSchema):
    id: int = Field(alias=M.ID)
    username: str = Field(alias=M.USERNAME)


MemberSchema = UserSchema


class UtubSummaryItemSchema(BaseSchema):
    id: int = Field(alias=M.ID)
    name: str = Field(alias=M.NAME)
    member_role: str = Field(alias=M.MEMBER_ROLE)


class UtubSummaryListSchema(BaseSchema):
    utubs: list[UtubSummaryItemSchema] = Field(alias=M.UTUBS)

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
    redirect_url: str = Field(alias=REDIRECT_URL)


class MemberModifiedResponseSchema(BaseSchema):
    utub_id: int = Field(alias=UTUB_ID)
    member: UserSchema = Field(alias=MEMBER)


class RegisterResponseSchema(BaseSchema):
    status: str = Field(alias=STD_JSON.STATUS)
    message: str = Field(alias=STD_JSON.MESSAGE)


class ForgotPasswordResponseSchema(BaseSchema):
    status: str = Field(alias=STD_JSON.STATUS)
    message: str = Field(alias=STD_JSON.MESSAGE)


class ResetPasswordResponseSchema(BaseSchema):
    status: str = Field(alias=STD_JSON.STATUS)
    message: str = Field(alias=STD_JSON.MESSAGE)


class EmailValidationResponseSchema(BaseSchema):
    status: str = Field(alias=STD_JSON.STATUS)
    message: str = Field(alias=STD_JSON.MESSAGE)
