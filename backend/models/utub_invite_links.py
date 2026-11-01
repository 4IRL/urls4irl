from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)

from backend import db
from backend.invite_links.constants import (
    INVITE_LINK_TOKEN_LENGTH,
    ONE_ACTIVE_INVITE_LINK_PER_UTUB,
    UNIQUE_INVITE_LINK_TOKEN,
)
from backend.utils.datetime_utils import utc_now

if TYPE_CHECKING:
    from backend.models.users import Users
    from backend.models.utubs import Utubs


class Utub_Invite_Links(db.Model):
    """A shareable invite link (plaintext token) that lets a person join one UTub.

    Revoked and replaced rows are kept so their tokens stay recognisable; the
    partial unique index allows only one unrevoked row per UTub. ``utubID``
    cascades on delete, ``createdBy`` is nulled if the creator is deleted
    (NULL means the link is dead), and ``EmailValidations.pendingInviteID``
    is nulled when a link row is deleted.
    """

    __tablename__ = "UtubInviteLinks"
    __table_args__ = (
        UniqueConstraint("token", name=UNIQUE_INVITE_LINK_TOKEN),
        Index(
            ONE_ACTIVE_INVITE_LINK_PER_UTUB,
            "utubID",
            unique=True,
            postgresql_where=text('"revokedAt" IS NULL'),
        ),
    )

    id: int = Column(Integer, primary_key=True)
    utub_id: int = Column(
        Integer,
        ForeignKey("Utubs.id", ondelete="CASCADE"),
        nullable=False,
        name="utubID",
    )
    token: str = Column(String(INVITE_LINK_TOKEN_LENGTH), nullable=False)
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
    max_uses: int | None = Column(Integer, nullable=True, name="maxUses")
    use_count: int = Column(
        Integer, nullable=False, default=0, server_default="0", name="useCount"
    )
    revoked_at: datetime | None = Column(
        DateTime(timezone=True), nullable=True, name="revokedAt"
    )

    utub: Utubs = db.relationship("Utubs")
    creator: Users | None = db.relationship("Users")

    def __init__(
        self,
        *,
        utub_id: int,
        token: str,
        created_by: int | None,
        expires_at: datetime,
        max_uses: int | None = None,
    ) -> None:
        self.utub_id = utub_id
        self.token = token
        self.created_by = created_by
        self.expires_at = expires_at
        self.max_uses = max_uses
