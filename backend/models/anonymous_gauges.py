from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB

from backend import db


class Anonymous_Gauges(db.Model):
    """Fact table — periodically-sampled scalar gauges over relational tables.

    Each row records one gauge's value at one sample instant: COUNT/MAX gauges
    populate ``value_int``, AVG gauges populate ``value_float`` (the other stays
    NULL). Privacy: schema deliberately contains no user_id, session_id, IP, or
    user-agent, matching ``Anonymous_Metrics``.

    Uses physical column-name strings in ``__table_args__`` (not class-qualified
    attribute references) because the class object does not yet exist when
    ``__table_args__`` is evaluated; SQLAlchemy resolves these against the
    ``name=`` kwarg on each Column and the Alembic migration uses the same
    physical names.
    """

    __tablename__ = "AnonymousGauges"
    __table_args__ = (Index("idx_gauges_name_time", "gaugeName", "sampledAt"),)

    id: int = Column(Integer, primary_key=True)
    # Plain string with no ForeignKey: unlike Anonymous_Metrics.event_name (which
    # references EventRegistry.name), gauges have no companion registry table. The
    # in-code GaugeName enum plus its coverage test are the single source of truth,
    # so a FK would add a second source of truth and defeat the one-place-add goal.
    gauge_name: str = Column(String(100), nullable=False, name="gaugeName")
    sampled_at: datetime = Column(
        DateTime(timezone=True), nullable=False, name="sampledAt"
    )
    value_int: int | None = Column(BigInteger, nullable=True, name="valueInt")
    value_float: float | None = Column(Numeric(20, 6), nullable=True, name="valueFloat")
    dimensions: dict = Column(JSONB, nullable=False, default=dict, name="dimensions")
