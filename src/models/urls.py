from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from src import db
from src.utils.datetime_utils import utc_now
from src.utils.strings.model_strs import MODELS as MODEL_STRS


class Urls(db.Model):
    """Class represents a URL. A URL is added by a single user, but can be used generically across multiple UTubs if it's already
    stored in the server."""

    __tablename__ = "Urls"
    id: int = Column(Integer, primary_key=True)
    url_string: str = Column(
        String(8000), nullable=False, unique=True
    )  # Note that multiple UTubs can have the same URL
    created_by: int = Column(Integer, ForeignKey("Users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    url_tags = db.relationship("Url_Tags", back_populates="tagged_url")

    def __init__(self, normalized_url: str, current_user_id: int):
        self.url_string = normalized_url
        self.created_by = int(current_user_id)

    @property
    def serialized_url(self):
        """Includes an array of tag IDs for all ID's on this url"""
        from src.models.url_tags import Url_Tags

        url_tags: list[Url_Tags] = self.url_tags
        return {
            MODEL_STRS.ID: self.id,
            MODEL_STRS.URL: self.url_string,
            MODEL_STRS.TAGS: [tag.tag_item.serialized for tag in url_tags],
        }
