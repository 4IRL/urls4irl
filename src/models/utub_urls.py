from __future__ import annotations
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from src import db
from src.models.urls import Urls
from src.utils.datetime_utils import utc_now
from src.utils.strings.model_strs import MODELS as MODEL_STRS


class Utub_Urls(db.Model):
    """
    Represents the Many-to-Many relationship between UTubs and the shared URLs.
    A new entry is created in the URLs table if it is not already added in there. This table
    indicates which UTubs contain which URLs, as well as the title for that UTub specific URL.

    https://stackoverflow.com/questions/52920701/many-to-many-with-three-tables-relating-with-each-other-sqlalchemy
    """

    __tablename__ = "UtubUrls"

    id: int = Column(Integer, primary_key=True)
    utub_id: int = Column(Integer, ForeignKey("Utubs.id"), name="utubID")
    url_id: int = Column(Integer, ForeignKey("Urls.id"), name="urlID")
    user_id: int = Column(Integer, ForeignKey("Users.id"), name="userID")
    url_title: str = Column(String(140), default="", name="urlTitle")
    added_at: datetime = Column(
        DateTime(timezone=True), nullable=False, default=utc_now, name="addedAt"
    )
    last_accessed: datetime = Column(
        DateTime(timezone=True), nullable=False, default=utc_now, name="lastAccessed"
    )

    standalone_url: Urls = db.relationship("Urls")
    utub = db.relationship("Utubs", back_populates="utub_urls")
    url_tags = db.relationship("Utub_Url_Tags", back_populates="tagged_url")

    def serialized(
        self, current_user_id: int, utub_creator: int
    ) -> dict[str, int | str | list[int] | bool]:
        """Returns serialized object."""
        url_item: Urls = self.standalone_url

        return {
            MODEL_STRS.UTUB_URL_ID: self.id,
            MODEL_STRS.URL_STRING: url_item.url_string,
            MODEL_STRS.URL_TAGS: self.associated_tags,
            MODEL_STRS.URL_TITLE: self.url_title,
            MODEL_STRS.CAN_DELETE: current_user_id == self.user_id
            or current_user_id == utub_creator,
        }

    @property
    def serialized_on_string_update(self) -> dict[str, int | str | list[int]]:
        return {
            MODEL_STRS.UTUB_URL_ID: self.id,
            MODEL_STRS.URL_STRING: self.standalone_url.url_string,
            MODEL_STRS.URL_TAGS: self.associated_tags,
        }

    @property
    def serialized_on_title_update(self) -> dict[str, int | str | list[int]]:
        return {
            MODEL_STRS.UTUB_URL_ID: self.id,
            MODEL_STRS.URL_TITLE: self.url_title,
            MODEL_STRS.URL_TAGS: self.associated_tags,
        }

    @property
    def associated_tags(self) -> list[int]:
        # Only return tags for the requested UTub
        url_tags = []
        for tag_in_utub in self.url_tags:
            if int(tag_in_utub.utub_id) == int(self.utub_id):
                url_tags.append(tag_in_utub.tag_id)

        return sorted(url_tags)
