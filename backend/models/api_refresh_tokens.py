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
)

from backend import db
from backend.utils.datetime_utils import utc_now

if TYPE_CHECKING:
    from backend.models.users import Users

# Column sizes are defined here (not backend/utils/constants.py) because this
# module is imported by backend/models/__init__.py, which backend/utils/
# constants.py itself triggers via its Member_Role import — importing constants
# back from here would be circular.
REFRESH_TOKEN_MAX_LENGTH = 128
FAMILY_ID_LENGTH = 36  # canonical str(uuid.uuid4()) length


class ApiRefreshTokens(db.Model):
    """A revocable, rotating refresh token for the mobile /api/v1 surface.

    Each row is one link in a per-device rotation chain: every refresh issues a
    new row in the same ``familyId`` and stamps the presented row with
    ``rotatedAt``/``replacedBy``. Presenting an already-rotated token is
    treated as theft (reuse detection) and revokes the entire family.

    Uses physical column-name strings in ``__table_args__`` (not
    class-qualified attribute references) because the class object does not
    yet exist when ``__table_args__`` is evaluated; SQLAlchemy resolves these
    against the ``name=`` kwarg on each Column and the Alembic migration uses
    the same physical names.
    """

    __tablename__ = "ApiRefreshTokens"
    __table_args__ = (
        UniqueConstraint("token", name="unique_api_refresh_token"),
        Index("idx_api_refresh_token_user", "userID"),
        Index("idx_api_refresh_token_family", "familyId"),
    )

    id: int = Column(Integer, primary_key=True)
    user_id: int = Column(
        Integer,
        ForeignKey("Users.id", ondelete="CASCADE"),
        nullable=False,
        name="userID",
    )
    token: str = Column(String(REFRESH_TOKEN_MAX_LENGTH), nullable=False)
    family_id: str = Column(String(FAMILY_ID_LENGTH), nullable=False, name="familyId")
    issued_at: datetime = Column(
        DateTime(timezone=True), nullable=False, default=utc_now, name="issuedAt"
    )
    expires_at: datetime = Column(
        DateTime(timezone=True), nullable=False, name="expiresAt"
    )
    rotated_at: datetime | None = Column(
        DateTime(timezone=True), nullable=True, default=None, name="rotatedAt"
    )
    replaced_by_id: int | None = Column(
        Integer,
        ForeignKey("ApiRefreshTokens.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
        name="replacedBy",
    )
    revoked_at: datetime | None = Column(
        DateTime(timezone=True), nullable=True, default=None, name="revokedAt"
    )

    user: Users = db.relationship("Users")

    def __init__(
        self, *, user_id: int, token: str, family_id: str, expires_at: datetime
    ) -> None:
        self.user_id = user_id
        self.token = token
        self.family_id = family_id
        self.expires_at = expires_at

    def is_expired(self) -> bool:
        return utc_now() >= self.expires_at

    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    def is_rotated(self) -> bool:
        return self.rotated_at is not None

    def is_active(self) -> bool:
        return not (self.is_revoked() or self.is_rotated() or self.is_expired())
