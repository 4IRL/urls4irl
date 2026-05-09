from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Enum as SQLEnum, String

from backend import db
from backend.metrics.events import EventCategory
from backend.utils.datetime_utils import utc_now


class Event_Registry(db.Model):
    """Dimension table — one row per defined event name. Synced from the
    Python EventName enum by the `flask metrics sync-registry` CLI command
    (invoked from `docker/startup-flask.sh` on container start); never
    modified by Alembic after the table exists."""

    __tablename__ = "EventRegistry"
    name: str = Column(String(100), primary_key=True, name="name")
    category: EventCategory = Column(
        SQLEnum(
            EventCategory,
            name="event_category_enum",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        name="category",
    )
    description: str = Column(String(500), nullable=False, name="description")
    added_at: datetime = Column(
        DateTime(timezone=True), nullable=False, default=utc_now, name="addedAt"
    )
