from sqlalchemy import Column, ForeignKey, Integer, String

from src import db
from src.utils.strings.model_strs import MODELS


class Utub_Members(db.Model):
    __tablename__ = "UtubMembers"
    utub_id: int = Column(Integer, ForeignKey("Utubs.id"), primary_key=True)
    user_id: int = Column(Integer, ForeignKey("Users.id"), primary_key=True)
    member_role: str = Column(String(9), nullable=False, default="member")

    to_user = db.relationship("Users", back_populates="utubs_is_member_of")
    to_utub = db.relationship("Utubs", back_populates="members")

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
