from __future__ import annotations
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer

from src import db
from src.models.utub_tags import Utub_Tags
from src.models.utubs import Utubs
from src.models.utub_urls import Utub_Urls
from src.utils.datetime_utils import utc_now


class Utub_Url_Tags(db.Model):
    """
    Represents the Many-to-Many relationship between tags, UTubs, and URLs.
    This table indicates which URLs in a specified UTub contain a specified tag.

    https://stackoverflow.com/questions/52920701/many-to-many-with-three-tables-relating-with-each-other-sqlalchemy
    """

    __tablename__ = "UtubUrlTags"

    id: int = Column(Integer, primary_key=True)
    utub_id: int = Column(
        Integer,
        ForeignKey("Utubs.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        name="utubID",
    )
    utub_url_id: int = Column(
        Integer,
        ForeignKey("UtubUrls.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        name="utubUrlID",
    )
    utub_tag_id: int = Column(
        Integer,
        ForeignKey("UtubTags.id", ondelete="CASCADE"),
        nullable=False,
        name="utubTagID",
    )
    added_at: datetime = Column(
        DateTime(timezone=True), nullable=False, default=utc_now, name="addedAt"
    )

    utub_tag_item: Utub_Tags = db.relationship("Utub_Tags")
    tagged_url: Utub_Urls = db.relationship("Utub_Urls", back_populates="url_tags")
    utub_containing_this_url_tag: Utubs = db.relationship(
        "Utubs", back_populates="utub_url_tags"
    )

    def __repr__(self):
        return f"Utub Url Tag | Utub_Url_Tags.id={self.id} | Utub_Url_Tags.utub_url_id={self.utub_url_id} | Utub_Url_Tags.utub_tag_id={self.utub_tag_id} | Utub_Url_Tags.utub_id={self.utub_id} "
