from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB

from backend import db
from backend.utils.datetime_utils import utc_now

if TYPE_CHECKING:
    from backend.models.users import Users


class AuditLog(db.Model):
    """Append-only record of every admin-portal access and action.

    Each row captures WHO (``actor_id``), WHAT (``action``, e.g.
    ``"admin.user.view"``), on WHOM/WHAT (``target_type`` + ``target_id``),
    plus optional structured context (``log_metadata``) and WHEN
    (``created_at``).

    Privacy note: rows can embed personal data (actor, target user id,
    search queries inside ``log_metadata``), so the table is subject to a
    90-day retention window enforced by ``scripts/purge_audit_log.py``
    (see docker/crontab.workflow).

    The model attribute is ``log_metadata`` because ``metadata`` is reserved
    by SQLAlchemy's declarative base; the physical column is ``metadata``.
    """

    __tablename__ = "AuditLogs"
    # Composite index for the audit-log viewer's dominant access pattern:
    # newest-first time-windowed scans, optionally narrowed by actor.
    __table_args__ = (
        Index(
            "idx_audit_logs_created_at_actor",
            text('"createdAt" DESC'),
            "actorId",
        ),
    )

    id: int = Column(Integer, primary_key=True)
    actor_id: int = Column(
        Integer, ForeignKey("Users.id"), nullable=False, name="actorId"
    )
    action: str = Column(String(100), nullable=False, name="action")
    target_type: str | None = Column(String(50), nullable=True, name="targetType")
    target_id: str | None = Column(String(64), nullable=True, name="targetId")
    log_metadata: dict | None = Column(JSONB, nullable=True, name="metadata")
    created_at: datetime = Column(
        DateTime(timezone=True), nullable=False, default=utc_now, name="createdAt"
    )

    actor: Users = db.relationship("Users")
