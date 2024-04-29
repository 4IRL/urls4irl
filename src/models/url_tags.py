from __future__ import annotations
from datetime import datetime

from src import db
from src.models.tags import Tags
from src.models.urls import Urls
from src.models.utubs import Utubs
from src.utils.strings.model_strs import MODELS as MODEL_STRS


class Url_Tags(db.Model):
    """
    Represents the Many-to-Many relationship between tags, UTubs, and URLs.
    This table indicates which URLs in a specified UTub contain a specified tag.

    https://stackoverflow.com/questions/52920701/many-to-many-with-three-tables-relating-with-each-other-sqlalchemy
    """

    __tablename__ = "UrlTags"

    utub_id: int = db.Column(db.Integer, db.ForeignKey("Utubs.id"), primary_key=True)
    url_id: int = db.Column(db.Integer, db.ForeignKey("Urls.id"), primary_key=True)
    tag_id: int = db.Column(db.Integer, db.ForeignKey("Tags.id"), primary_key=True)
    added_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    tag_item: Tags = db.relationship("Tags")
    tagged_url: Urls = db.relationship("Urls", back_populates="url_tags")
    utub_containing_this_tag: Utubs = db.relationship(
        "Utubs", back_populates="utub_url_tags"
    )

    @property
    def serialized(self) -> dict:
        """Returns serialized object."""
        return {
            MODEL_STRS.TAG: self.tag_item.serialized,
            MODEL_STRS.TAGGED_URL: self.tagged_url.serialized_url,
        }
