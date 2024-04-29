from datetime import datetime

from src import db
from src.utils.strings.model_strs import MODELS as MODEL_STRS


class Tags(db.Model):
    """Class represents a tag, more specifically a tag for a URL. A tag is added by a single user, but can be used as a tag for any URL."""

    __tablename__ = "Tags"
    id: int = db.Column(db.Integer, primary_key=True)
    tag_string: str = db.Column(
        db.String(30), nullable=False
    )  # Note that multiple URLs can have the same tag
    created_by: int = db.Column(db.Integer, db.ForeignKey("Users.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __init__(self, tag_string: str, created_by: int):
        self.tag_string = tag_string
        self.created_by = created_by

    @property
    def serialized(self):
        """Returns serialized object."""
        return {MODEL_STRS.ID: self.id, MODEL_STRS.TAG_STRING: self.tag_string}
