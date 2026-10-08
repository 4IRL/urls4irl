from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB

from backend import db
from backend.models.urls import Urls
from backend.utils.datetime_utils import utc_now
from backend.utils.strings.model_strs import MODELS as MODEL_STRS


class Utub_Urls(db.Model):
    """
    Represents the Many-to-Many relationship between UTubs and the shared URLs.
    A new entry is created in the URLs table if it is not already added in there. This table
    indicates which UTubs contain which URLs, as well as the title for that UTub specific URL.

    https://stackoverflow.com/questions/52920701/many-to-many-with-three-tables-relating-with-each-other-sqlalchemy
    """

    __tablename__ = "UtubUrls"

    id: int = Column(Integer, primary_key=True)
    utub_id: int = Column(
        Integer,
        ForeignKey("Utubs.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        name="utubID",
    )
    url_id: int = Column(Integer, ForeignKey("Urls.id"), nullable=False, name="urlID")
    user_id: int = Column(
        Integer, ForeignKey("Users.id"), nullable=False, name="userID"
    )
    url_title: str = Column(String(140), default="", name="urlTitle")
    added_at: datetime = Column(
        DateTime(timezone=True), nullable=False, default=utc_now, name="addedAt"
    )
    last_accessed: datetime = Column(
        DateTime(timezone=True), nullable=False, default=utc_now, name="lastAccessed"
    )
    # Soft-delete marker; NULL means not trashed.
    deleted_at: datetime | None = Column(
        DateTime(timezone=True), nullable=True, default=None, name="deletedAt"
    )
    deleted_by: int | None = Column(
        Integer, ForeignKey("Users.id"), nullable=True, default=None, name="deletedBy"
    )
    # Snapshot of the URL's tag ids at delete time. NULL means "no snapshot" (so no
    # default=list). JSONB has no mutation tracking: always reassign a new list,
    # never mutate in place.
    trashed_tag_ids: list[int] | None = Column(
        JSONB(none_as_null=True), nullable=True, default=None, name="trashedTagIds"
    )

    standalone_url: Urls = db.relationship("Urls")
    utub = db.relationship("Utubs", back_populates="utub_urls")
    url_tags = db.relationship("Utub_Url_Tags", back_populates="tagged_url")

    UniqueConstraint(utub_id, url_id, name="unique_url_per_utub")

    @property
    def is_trashed(self) -> bool:
        return self.deleted_at is not None

    @property
    def associated_tag_ids(self) -> list[int]:
        # Only return tags for the requested UTub
        url_tags = []
        for tag_in_utub in self.url_tags:
            if int(tag_in_utub.utub_id) == int(self.utub_id):
                url_tags.append(tag_in_utub.utub_tag_id)

        return sorted(url_tags)

    @property
    def associated_tags(self) -> list[dict[str, int | str]]:
        url_tags = []
        for tag_in_utub in self.url_tags:
            if tag_in_utub.utub_id == self.utub_id:
                url_tags.append(
                    {
                        MODEL_STRS.UTUB_TAG_ID: tag_in_utub.utub_tag_id,
                        MODEL_STRS.TAG_STRING: tag_in_utub.utub_tag_item.tag_string,
                    }
                )
        return url_tags
