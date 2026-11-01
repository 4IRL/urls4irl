from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer

from backend import db
from backend.invite_links.constants import (
    FK_INVITE_ACCEPTANCES_INVITE,
    FK_INVITE_ACCEPTANCES_USER,
    FK_INVITE_ACCEPTANCES_UTUB,
    IX_INVITE_ACCEPTANCES_INVITE,
)
from backend.utils.datetime_utils import utc_now

if TYPE_CHECKING:
    from backend.models.users import Users
    from backend.models.utub_invite_links import Utub_Invite_Links
    from backend.models.utubs import Utubs


class Utub_Invite_Acceptances(db.Model):
    """Permanent record of one person joining a UTub through an invite link.

    Rows are grouped by ``inviteID``. ``userID`` is nulled if the account is
    erased, so the row stays as an anonymous record; ``inviteID`` and ``utubID``
    cascade only when the invite or UTub row itself is deleted.
    """

    __tablename__ = "UtubInviteAcceptances"
    __table_args__ = (Index(IX_INVITE_ACCEPTANCES_INVITE, "inviteID"),)

    id: int = Column(Integer, primary_key=True)
    invite_id: int = Column(
        Integer,
        ForeignKey(
            "UtubInviteLinks.id",
            ondelete="CASCADE",
            name=FK_INVITE_ACCEPTANCES_INVITE,
        ),
        nullable=False,
        name="inviteID",
    )
    utub_id: int = Column(
        Integer,
        ForeignKey("Utubs.id", ondelete="CASCADE", name=FK_INVITE_ACCEPTANCES_UTUB),
        nullable=False,
        name="utubID",
    )
    user_id: int | None = Column(
        Integer,
        ForeignKey("Users.id", ondelete="SET NULL", name=FK_INVITE_ACCEPTANCES_USER),
        nullable=True,
        name="userID",
    )
    accepted_at: datetime = Column(
        DateTime(timezone=True), nullable=False, default=utc_now, name="acceptedAt"
    )

    invite: Utub_Invite_Links = db.relationship("Utub_Invite_Links")
    utub: Utubs = db.relationship("Utubs")
    user: Users | None = db.relationship("Users")

    def __init__(self, *, invite_id: int, utub_id: int, user_id: int | None) -> None:
        self.invite_id = invite_id
        self.utub_id = utub_id
        self.user_id = user_id
