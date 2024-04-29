from src import db


class Utub_Members(db.Model):
    __tablename__ = "UtubMembers"
    utub_id: int = db.Column(db.Integer, db.ForeignKey("Utubs.id"), primary_key=True)
    user_id: int = db.Column(db.Integer, db.ForeignKey("Users.id"), primary_key=True)

    to_user = db.relationship("Users", back_populates="utubs_is_member_of")
    to_utub = db.relationship("Utubs", back_populates="members")

    @property
    def serialized(self) -> dict:
        return self.to_user.serialized

    @property
    def serialized_on_initial_load(self):
        """Returns the serialized object on initial load for this member, including UTub name and id."""
        return {"id": self.to_utub.id, "name": self.to_utub.name}
