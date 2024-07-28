from datetime import datetime

from sqlalchemy import DateTime, Column, ForeignKey, Integer, String, UniqueConstraint

from src import db
from src.utils.strings.model_strs import MODELS as MODEL_STRS
from src.utils.datetime_utils import utc_now


class Utub_Tags(db.Model):
    """Class represents a tag, more specifically a tag for a URL. A tag is added by a single user, but can be used as a tag for any URL."""

    __tablename__ = "UtubTags"
    id: int = Column(Integer, primary_key=True)
    tag_string: str = Column(
        String(30), nullable=False, name="tagString"
    )  # Note that multiple URLs can have the same tag
    utub_id: int = Column(
        Integer,
        ForeignKey("Utubs.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        name="utubID",
    )
    created_by: int = Column(
        Integer, ForeignKey("Users.id"), nullable=False, name="createdBy"
    )
    created_at: datetime = Column(
        DateTime(timezone=True), nullable=False, default=utc_now, name="createdAt"
    )
    utub_url_tag_associations = db.relationship(
        "Utub_Url_Tags", back_populates="utub_tag_item", cascade="all, delete"
    )

    UniqueConstraint(utub_id, tag_string, name="unique_tag_per_utub")

    def __init__(self, utub_id: int, tag_string: str, created_by: int):
        self.utub_id = utub_id
        self.tag_string = tag_string
        self.created_by = created_by

    @property
    def serialized(self):
        """Returns serialized object."""
        return {MODEL_STRS.ID: self.id, MODEL_STRS.TAG_STRING: self.tag_string}

    @property
    def serialized_on_add_delete(self):
        """Returns serialized object."""
        return {MODEL_STRS.UTUB_TAG_ID: self.id, MODEL_STRS.TAG_STRING: self.tag_string}
