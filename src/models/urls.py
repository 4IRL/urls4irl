from datetime import datetime

from src import db
from src.utils.strings.model_strs import MODELS as MODEL_STRS


class Urls(db.Model):
    """Class represents a URL. A URL is added by a single user, but can be used generically across multiple UTubs if it's already
    stored in the server."""

    __tablename__ = "Urls"
    id: int = db.Column(db.Integer, primary_key=True)
    url_string: str = db.Column(
        db.String(2000), nullable=False, unique=True
    )  # Note that multiple UTubs can have the same URL
    created_by: int = db.Column(db.Integer, db.ForeignKey("Users.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    url_tags = db.relationship("Url_Tags", back_populates="tagged_url")

    def __init__(self, normalized_url: str, current_user_id: int):
        self.url_string = normalized_url
        self.created_by = int(current_user_id)

    @property
    def serialized_url(self):
        """Includes an array of tag IDs for all ID's on this url"""
        return {
            MODEL_STRS.ID: self.id,
            MODEL_STRS.URL: self.url_string,
            MODEL_STRS.TAGS: [tag.tag_item.serialized for tag in self.url_tags],
        }
