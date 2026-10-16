from enum import Enum

from sqlalchemy import Column, ForeignKey, Index, Integer, UniqueConstraint, text
from sqlalchemy import Enum as SQLEnum

from backend import db


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
    # TODO: Add time when member was added

    to_user = db.relationship("Users", back_populates="utubs_is_member_of")
    to_utub = db.relationship("Utubs", back_populates="members")

    UniqueConstraint(utub_id, user_id, name="unique_member")

    # At most one CREATOR row per UTub. Checked per statement, so writers must
    # demote/delete the outgoing CREATOR and flush before promoting a new one.
    # The predicate uses the enum NAME 'CREATOR' (not the value "creator").
    __table_args__ = (
        Index(
            "uq_utub_members_single_creator",
            "utubID",
            unique=True,
            postgresql_where=text("\"memberRole\" = 'CREATOR'"),
        ),
    )
