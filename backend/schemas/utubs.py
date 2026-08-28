from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import Field, field_serializer

from backend.schemas.base import BaseSchema
from backend.schemas.tags import UtubTagSchema
from backend.schemas.urls import UtubUrlSchema
from backend.schemas.users import UtubMemberSchema
from backend.utils.strings.model_strs import MODELS as M, UTUB_DESCRIPTION
from backend.utils.strings.utub_strs import UTUB_ID, UTUB_NAME, UTUB_CREATOR_ID

if TYPE_CHECKING:
    from backend.models.utub_urls import Utub_Urls
    from backend.models.utubs import Utubs


class UtubDetailSchema(BaseSchema):
    """Full UTub detail with members, URLs, and tags"""

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
    created_at: datetime = Field(
        alias=M.CREATED_AT,
        description="Creation timestamp of the UTub (ISO 8601)",
    )
    description: str = Field(
        alias=M.DESCRIPTION,
        description="Description of the UTub",
    )
    members: list[UtubMemberSchema] = Field(
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
    is_co_creator: bool = Field(
        alias=M.IS_CO_CREATOR,
        description="Whether the current user is a co-creator (co-owner) of the UTub",
    )
    is_locked: bool = Field(
        alias=M.IS_LOCKED,
        description="Whether the UTub is locked (frozen to all user mutations)",
    )
    current_user: int = Field(
        alias=M.CURRENT_USER,
        description="ID of the currently authenticated user",
    )

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime) -> str:
        return value.isoformat()

    @classmethod
    def from_utub(
        cls,
        utub: Utubs,
        current_user_id: int,
        ordered_utub_urls: list[Utub_Urls],
    ) -> UtubDetailSchema:
        # ``Member_Role`` is imported locally to avoid a circular import: this
        # schema module is loaded during ``backend`` package init (via
        # ``backend.schemas.__init__``), before ``db.Model`` is ready, so a
        # top-level ``backend.models`` import would fail. Computed before the
        # ``urls`` comprehension so a later step (URL-delete widening) can reuse
        # ``is_co_creator`` to derive the viewer's manager rights ahead of that
        # same line.
        from backend.models.utub_members import Member_Role

        is_co_creator = any(
            member.to_user.id == current_user_id
            and member.member_role == Member_Role.CO_CREATOR
            for member in utub.members
        )
        # ``ordered_utub_urls`` is the UTub's URL rows pre-ordered by the viewing
        # user's ``default_sort`` preference (server-authoritative, resolved by
        # ``get_single_utub_for_user``) — the serialized ``urls`` list is emitted
        # in exactly this order.
        urls = [
            UtubUrlSchema.from_orm_url(u, current_user_id, utub.utub_creator)
            for u in ordered_utub_urls
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
            created_at=utub.created_at,
            description=(
                utub.utub_description if utub.utub_description is not None else ""
            ),
            members=[
                UtubMemberSchema(
                    id=member.to_user.id,
                    username=member.to_user.username,
                    member_role=member.member_role.value,
                )
                for member in utub.members
            ],
            urls=urls,
            tags=tags,
            is_creator=utub.utub_creator == current_user_id,
            is_co_creator=is_co_creator,
            is_locked=utub.is_locked,
            current_user=current_user_id,
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
    """UTub description updated"""

    utub_id: int = Field(
        alias=UTUB_ID,
        description="ID of the UTub whose description was updated",
    )
    utub_description: str | None = Field(
        alias=UTUB_DESCRIPTION,
        description="New description of the UTub, or null if cleared",
    )
