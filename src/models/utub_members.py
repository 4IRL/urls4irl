from enum import Enum

from sqlalchemy import Column, Enum as ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import ENUM as PostgresEnum

from src import db
from src.utils.strings.model_strs import MODELS


class Member_Role(str, Enum):
    MEMBER = "MEMBER"
    CREATOR = "CREATOR"
    CO_CREATOR = "CO_CREATOR"


member_role_enum = PostgresEnum(Member_Role, name="memberRole", create_type=False)


class Utub_Members(db.Model):
    __tablename__ = "UtubMembers"
    utub_id: int = Column(
        Integer, ForeignKey("Utubs.id"), primary_key=True, name="utubID"
    )
    user_id: int = Column(
        Integer, ForeignKey("Users.id"), primary_key=True, name="userID"
    )
    member_role = Column(
        member_role_enum, name="memberRole", nullable=False, default=Member_Role.MEMBER
    )
    # TODO: Add time when member was added

    to_user = db.relationship("Users", back_populates="utubs_is_member_of")
    to_utub = db.relationship("Utubs", back_populates="members")

    UniqueConstraint(utub_id, user_id, name="unique_member")

    @property
    def serialized(self) -> dict:
        from src.models.users import Users

        user: Users = self.to_user
        return user.serialized

    @property
    def serialized_on_initial_load(self):
        """Returns the serialized object on initial load for this member, including UTub name and id."""
        from src.models.utubs import Utubs

        utub: Utubs = self.to_utub
        return {MODELS.ID: utub.id, MODELS.NAME: utub.name}
