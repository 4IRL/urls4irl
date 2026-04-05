from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import Field

from backend.schemas.base import BaseSchema
from backend.schemas.tags import UtubTagSchema
from backend.schemas.urls import UtubUrlSchema
from backend.schemas.users import UserSchema
from backend.utils.strings.model_strs import MODELS as M, UTUB_DESCRIPTION
from backend.utils.strings.utub_strs import UTUB_ID, UTUB_NAME, UTUB_CREATOR_ID

if TYPE_CHECKING:
    from backend.models.utubs import Utubs


class UtubDetailSchema(BaseSchema):
    id: int = Field(
        alias=M.ID,
        description="Unique UTub ID",
    )
    name: str = Field(
        alias=M.NAME,
        description="Name of the UTub",
    )
    created_by: int = Field(
        alias=M.CREATED_BY,
        description="User ID of the UTub creator",
    )
    created_at: str = Field(
        alias=M.CREATED_AT,
        description="Creation timestamp of the UTub",
    )
    description: str = Field(
        alias=M.DESCRIPTION,
        description="Description of the UTub",
    )
    members: list[UserSchema] = Field(
        alias=M.MEMBERS,
        description="List of members in the UTub",
    )
    urls: list[UtubUrlSchema] = Field(
        alias=M.URLS,
        description="List of URLs in the UTub",
    )
    tags: list[UtubTagSchema] = Field(
        alias=M.TAGS,
        description="List of tags used in the UTub",
    )
    is_creator: bool = Field(
        alias=M.IS_CREATOR,
        description="Whether the current user is the creator of the UTub",
    )
    current_user: str = Field(
        alias=M.CURRENT_USER,
        description="ID of the currently authenticated user",
    )

    @classmethod
    def from_utub(cls, utub: Utubs, current_user_id: int) -> UtubDetailSchema:
        urls = [
            UtubUrlSchema.from_orm_url(u, current_user_id, utub.utub_creator)
            for u in utub.utub_urls
        ]
        tags = [UtubTagSchema(id=t.id, tag_string=t.tag_string) for t in utub.utub_tags]
        # Replicate the tag_applied count loop from Utubs.serialized()
        tag_map = {t.id: t for t in tags}
        for url in urls:
            for tag_id in url.utub_url_tag_ids:
                if tag_id in tag_map:
                    tag_map[tag_id].tag_applied += 1
        return cls(
            id=utub.id,
            name=utub.name,
            created_by=utub.utub_creator,
            created_at=utub.created_at.strftime("%m/%d/%Y %H:%M:%S"),
            description=(
                utub.utub_description if utub.utub_description is not None else ""
            ),
            members=[
                UserSchema(id=m.to_user.id, username=m.to_user.username)
                for m in utub.members
            ],
            urls=urls,
            tags=tags,
            is_creator=utub.utub_creator == current_user_id,
            current_user=str(current_user_id),
        )


UtubDetailSchema.model_rebuild()


class UtubCreatedResponseSchema(BaseSchema):
    utub_id: int = Field(
        alias=UTUB_ID,
        description="Unique ID of the newly created UTub",
    )
    utub_name: str = Field(
        alias=UTUB_NAME,
        description="Name of the newly created UTub",
    )
    utub_description: str | None = Field(
        alias=UTUB_DESCRIPTION,
        description="Description of the newly created UTub, or null if not set",
    )
    utub_creator_id: int = Field(
        alias=UTUB_CREATOR_ID,
        description="User ID of the UTub creator",
    )


class UtubDeletedResponseSchema(BaseSchema):
    utub_id: int = Field(
        alias=UTUB_ID,
        description="ID of the deleted UTub",
    )
    utub_name: str = Field(
        alias=UTUB_NAME,
        description="Name of the deleted UTub",
    )
    utub_description: str | None = Field(
        alias=UTUB_DESCRIPTION,
        description="Description of the deleted UTub, or null if not set",
    )


class UtubNameUpdatedResponseSchema(BaseSchema):
    utub_id: int = Field(
        alias=UTUB_ID,
        description="ID of the UTub whose name was updated",
    )
    utub_name: str = Field(
        alias=UTUB_NAME,
        description="New name of the UTub",
    )


class UtubDescUpdatedResponseSchema(BaseSchema):
    utub_id: int = Field(
        alias=UTUB_ID,
        description="ID of the UTub whose description was updated",
    )
    utub_description: str | None = Field(
        alias=UTUB_DESCRIPTION,
        description="New description of the UTub, or null if cleared",
    )
