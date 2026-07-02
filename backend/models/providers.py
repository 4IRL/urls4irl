from __future__ import annotations

from sqlalchemy import Boolean, Column, String

from backend import db


class Providers(db.Model):
    """Reference table listing the OAuth providers a local account may link.

    Source of truth for valid ``provider`` values: the FK target of
    ``UserOAuthIdentities.provider`` (the FK is the only validity gate). Rows are
    seeded as reference data by the Alembic migration (``google``, ``github``);
    the ``Provider`` StrEnum in the OAuth service is a code-side dispatch
    reference only and is not kept set-equal to this table.
    """

    __tablename__ = "Providers"

    key: str = Column(String(50), primary_key=True, name="key")
    display_name: str = Column(String(50), nullable=False, name="displayName")
    enabled: bool = Column(Boolean, nullable=False, default=True, name="enabled")

    def __init__(self, key: str, display_name: str, enabled: bool = True) -> None:
        self.key = key
        self.display_name = display_name
        self.enabled = enabled
