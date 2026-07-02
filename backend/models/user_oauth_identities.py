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
from backend.utils.constants import USER_CONSTANTS
from backend.utils.datetime_utils import utc_now

if TYPE_CHECKING:
    from backend.models.users import Users


class UserOAuthIdentity(db.Model):
    """A single third-party OAuth identity linked to a local Users account.

    Child of Users: one Users row may have many identities (e.g. Google and
    GitHub), one per provider. The composite uniqueness constraints enforce
    that a given provider-subject maps to exactly one account and that a user
    links at most one identity per provider.

    Uses physical column-name strings in ``__table_args__`` (not class-qualified
    attribute references) because the class object does not yet exist when
    ``__table_args__`` is evaluated; SQLAlchemy resolves these against the
    ``name=`` kwarg on each Column and the Alembic migration uses the same
    physical names.
    """

    __tablename__ = "UserOAuthIdentities"
    __table_args__ = (
        UniqueConstraint("provider", "providerSubject", name="unique_provider_subject"),
        UniqueConstraint("userID", "provider", name="unique_user_provider"),
        Index("idx_oauth_identity_user", "userID"),
    )

    id: int = Column(Integer, primary_key=True)
    user_id: int = Column(
        Integer,
        ForeignKey("Users.id", ondelete="CASCADE"),
        nullable=False,
        name="userID",
    )
    provider: str = Column(
        String(50), ForeignKey("Providers.key"), nullable=False, name="provider"
    )
    provider_subject: str = Column(String(255), nullable=False, name="providerSubject")
    email: str | None = Column(
        String(USER_CONSTANTS.MAX_EMAIL_LENGTH), nullable=True, name="email"
    )
    linked_at: datetime = Column(
        DateTime(timezone=True), nullable=False, default=utc_now, name="linkedAt"
    )

    user: Users = db.relationship("Users", back_populates="oauth_identities")

    def __init__(
        self, provider: str, provider_subject: str, email: str | None = None
    ) -> None:
        self.provider = provider
        self.provider_subject = provider_subject
        self.email = email
