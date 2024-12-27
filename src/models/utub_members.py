from enum import Enum

from sqlalchemy import Column, Enum as SQLEnum, ForeignKey, Integer, UniqueConstraint

from src import db
from src.utils.strings.model_strs import MODELS


class Member_Role(Enum):
    MEMBER = "member"
    CREATOR = "creator"
    CO_CREATOR = "cocreator"


class Utub_Members(db.Model):
    __tablename__ = "UtubMembers"
    utub_id: int = Column(
        Integer, ForeignKey("Utubs.id"), primary_key=True, name="utubID"
    )
    user_id: int = Column(
        Integer, ForeignKey("Users.id"), primary_key=True, name="userID"
    )
    member_role: Member_Role = Column(
        SQLEnum(Member_Role),
        nullable=False,
        default=Member_Role.MEMBER,
        name="memberRole",
    )

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
