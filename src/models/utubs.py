from datetime import datetime

from src import db
from src.models.utub_members import Utub_Members
from src.models.utub_urls import Utub_Urls
from src.utils.strings.model_strs import MODELS as MODEL_STRS


class Utubs(db.Model):
    """Class represents a UTub. A UTub is created by a specific user, but has read-edit access given to other users depending on who it
    is shared with. The UTub contains a set of URL's and their associated tags."""

    __tablename__ = "Utubs"
    id: int = db.Column(db.Integer, primary_key=True)
    name: str = db.Column(
        db.String(30), nullable=False
    )  # Note that multiple UTubs can have the same name, maybe verify this per user?
    utub_creator: int = db.Column(db.Integer, db.ForeignKey("Users.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    utub_description: str = db.Column(db.String(500), nullable=True)
    utub_url_tags = db.relationship(
        "Url_Tags", back_populates="utub_containing_this_tag", cascade="all, delete"
    )
    utub_urls: list[Utub_Urls] = db.relationship(
        "Utub_Urls", back_populates="utub", cascade="all, delete"
    )
    members: list[Utub_Members] = db.relationship(
        "Utub_Members", back_populates="to_utub", cascade="all, delete, delete-orphan"
    )

    def __init__(self, name: str, utub_creator: int, utub_description: str):
        self.name = name
        self.utub_creator = utub_creator
        self.utub_description = utub_description

    def serialized(self, current_user_id: int) -> dict[str, list | int | str]:
        """Return object in serialized form."""

        # self.utub_url_tags may contain repeats of tags since same tags can be on multiple URLs
        # Need to pull only the unique ones
        utub_tags = []
        for tag in self.utub_url_tags:
            tag_object = tag.tag_item.serialized

            if tag_object not in utub_tags:
                utub_tags.append(tag_object)

        return {
            MODEL_STRS.ID: self.id,
            MODEL_STRS.NAME: self.name,
            MODEL_STRS.CREATED_BY: self.utub_creator,
            MODEL_STRS.CREATED_AT: self.created_at.strftime("%m/%d/%Y %H:%M:%S"),
            MODEL_STRS.DESCRIPTION: (
                self.utub_description if self.utub_description is not None else ""
            ),
            MODEL_STRS.MEMBERS: [member.serialized for member in self.members],
            MODEL_STRS.URLS: [
                url_in_utub.serialized(current_user_id, self.utub_creator)
                for url_in_utub in self.utub_urls
            ],
            MODEL_STRS.TAGS: utub_tags,
        }
