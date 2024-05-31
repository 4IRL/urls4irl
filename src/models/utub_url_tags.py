from __future__ import annotations
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer

from src import db
from src.models.tags import Tags
from src.models.urls import Urls
from src.models.utubs import Utubs
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
        Integer, ForeignKey("Utubs.id"), nullable=False, name="utubID"
    )
    url_id: int = Column(Integer, ForeignKey("Urls.id"), nullable=True, name="urlID")
    tag_id: int = Column(Integer, ForeignKey("Tags.id"), nullable=False, name="tagID")
    added_at: datetime = Column(
        DateTime(timezone=True), nullable=False, default=utc_now, name="addedAt"
    )

    tag_item: Tags = db.relationship("Tags")
    tagged_url: Urls = db.relationship("Urls", back_populates="url_tags")
    utub_containing_this_tag: Utubs = db.relationship(
        "Utubs", back_populates="utub_url_tags"
    )
