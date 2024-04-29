from __future__ import annotations
from datetime import datetime

from src import db
from src.models.urls import Urls
from src.utils.strings.model_strs import MODELS as MODEL_STRS


class Utub_Urls(db.Model):
    """
    Represents the Many-to-Many relationship between UTubs and the shared URLs.
    A new entry is created in the URLs table if it is not already added in there. This table
    indicates which UTubs contain which URLs, as well as the title for that UTub specific URL.

    https://stackoverflow.com/questions/52920701/many-to-many-with-three-tables-relating-with-each-other-sqlalchemy
    """

    __tablename__ = "UtubUrls"

    utub_id: int = db.Column(db.Integer, db.ForeignKey("Utubs.id"), primary_key=True)
    url_id: int = db.Column(db.Integer, db.ForeignKey("Urls.id"), primary_key=True)
    user_id: int = db.Column(db.Integer, db.ForeignKey("Users.id"), primary_key=True)
    url_title: str = db.Column(db.String(140), default="")
    added_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user_that_added_url = db.relationship("Users", back_populates="utub_urls")
    standalone_url: Urls = db.relationship("Urls")
    utub = db.relationship("Utubs", back_populates="utub_urls")

    def serialized(
        self, current_user_id: int, utub_creator: int
    ) -> dict[str, int | str | list[int] | bool]:
        """Returns serialized object."""
        url_data = self.standalone_url.serialized_url

        return {
            MODEL_STRS.URL_ID: url_data[MODEL_STRS.ID],
            MODEL_STRS.URL_STRING: url_data[MODEL_STRS.URL],
            MODEL_STRS.URL_TAGS: self.associated_tags,
            MODEL_STRS.URL_TITLE: self.url_title,
            MODEL_STRS.CAN_DELETE: current_user_id == self.user_id
            or current_user_id == utub_creator,
        }

    @property
    def serialized_on_string_edit(self) -> dict[str, int | str | list[int]]:
        url_data = self.standalone_url.serialized_url

        return {
            MODEL_STRS.URL_ID: url_data[MODEL_STRS.ID],
            MODEL_STRS.URL_STRING: url_data[MODEL_STRS.URL],
            MODEL_STRS.URL_TAGS: self.associated_tags,
        }

    @property
    def serialized_on_title_edit(self) -> dict[str, int | str | list[int]]:
        url_data = self.standalone_url.serialized_url

        return {
            MODEL_STRS.URL_ID: url_data[MODEL_STRS.ID],
            MODEL_STRS.URL_TITLE: self.url_title,
            MODEL_STRS.URL_TAGS: self.associated_tags,
        }

    @property
    def associated_tags(self) -> list[int]:
        # Only return tags for the requested UTub
        url_tags = []
        for tag in self.standalone_url.url_tags:
            if int(tag.utub_id) == int(self.utub_id):
                url_tags.append(tag.tag_id)

        return sorted(url_tags)
