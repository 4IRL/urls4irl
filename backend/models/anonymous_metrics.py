from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB

from backend import db


class Anonymous_Metrics(db.Model):
    """Fact table — anonymous aggregate counters. Each row represents
    `count` occurrences of `event_name` (with `dimensions`) inside the
    hour-bucket starting at `bucket_start`. Privacy: schema deliberately
    contains no user_id, session_id, IP, or user-agent.

    Uses ``__table_args__`` for the multi-column ``UniqueConstraint`` rather
    than the bare class-body ``UniqueConstraint(...)`` form used elsewhere in
    the codebase. The ``__table_args__`` form is the SQLAlchemy-canonical way
    to declare composite unique constraints and ensures they are registered
    with the table metadata correctly.
    """

    __tablename__ = "AnonymousMetrics"
    # Physical column name strings are used here rather than class-qualified
    # attribute references (e.g. Anonymous_Metrics.bucket_start). Class-
    # qualified references cause a NameError at class-construction time
    # because the class object does not yet exist when __table_args__ is
    # evaluated. SQLAlchemy resolves these strings via the name= kwarg passed
    # to each Column(...) definition (i.e. the physical DB column name).
    # This is also consistent with the Alembic migration body, which uses
    # the same string column names.
    __table_args__ = (
        UniqueConstraint(
            "bucketStart",
            "eventName",
            "dimensions",
            name="unique_metric_bucket",
        ),
    )

    id: int = Column(Integer, primary_key=True)
    event_name: str = Column(
        String(100),
        ForeignKey("EventRegistry.name", onupdate="CASCADE"),
        nullable=False,
        name="eventName",
    )
    endpoint: str | None = Column(String(255), nullable=True, name="endpoint")
    method: str | None = Column(String(10), nullable=True, name="method")
    status_code: int | None = Column(Integer, nullable=True, name="statusCode")
    bucket_start: datetime = Column(
        DateTime(timezone=True), nullable=False, name="bucketStart"
    )
    dimensions: dict = Column(JSONB, nullable=False, default=dict, name="dimensions")
    count: int = Column(BigInteger, nullable=False, name="count")
