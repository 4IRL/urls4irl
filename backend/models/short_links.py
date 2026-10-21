from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint

from backend import db
from backend.utils.datetime_utils import utc_now

if TYPE_CHECKING:
    from backend.models.users import Users
    from backend.models.utub_urls import Utub_Urls

# Defined here (not backend/utils/constants.py) because this module is imported by
# backend/models/__init__.py; importing constants back would be circular.
SHORT_LINK_CODE_LENGTH = 10


class Short_Links(db.Model):
    """A temporary public share link (``/s/<code>``) for one UtubUrls row.

    One row per UtubUrl. The DB-level ``ON DELETE CASCADE`` removes the link when
    its ``UtubUrls`` row is hard-deleted (raw SQL, bulk deletes, purge paths).
    ``createdBy`` is the minter and is nulled if that user is deleted.
    """

    __tablename__ = "ShortLinks"
    __table_args__ = (
        UniqueConstraint("utubUrlID", name="unique_short_link_per_utub_url"),
        UniqueConstraint("code", name="unique_short_link_code"),
    )

    id: int = Column(Integer, primary_key=True)
    utub_url_id: int = Column(
        Integer,
        ForeignKey("UtubUrls.id", ondelete="CASCADE"),
        nullable=False,
        name="utubUrlID",
    )
    code: str = Column(String(SHORT_LINK_CODE_LENGTH), nullable=False)
    created_by: int | None = Column(
        Integer,
        ForeignKey("Users.id", ondelete="SET NULL"),
        nullable=True,
        name="createdBy",
    )
    created_at: datetime = Column(
        DateTime(timezone=True), nullable=False, default=utc_now, name="createdAt"
    )
    expires_at: datetime = Column(
        DateTime(timezone=True), nullable=False, name="expiresAt"
    )

    utub_url: Utub_Urls = db.relationship("Utub_Urls", back_populates="short_link")
    creator: Users | None = db.relationship("Users")

    def __init__(
        self,
        *,
        utub_url_id: int,
        code: str,
        created_by: int | None,
        expires_at: datetime,
    ) -> None:
        self.utub_url_id = utub_url_id
        self.code = code
        self.created_by = created_by
        self.expires_at = expires_at

    def is_expired(self) -> bool:
        return utc_now() >= self.expires_at
