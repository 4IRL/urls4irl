from __future__ import annotations

from datetime import date

from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from backend import db


class Anonymous_Latency_Daily_Rollups(db.Model):
    """Fact table — one precomputed daily percentile rollup row per endpoint.

    Each row aggregates a single UTC calendar day of raw
    ``Anonymous_Latency_Samples`` into stored p50/p95/p99 values plus a
    ``sampleCount``, serving query windows older than the raw-sample retention
    horizon. The rollup is built nightly by the Flask-less flush worker via an
    idempotent upsert keyed on (metricName, endpoint, method, rollupDate), so a
    re-run merges late-arriving samples instead of duplicating rows.

    Aggregates across device_type (no device dimension), matching the current
    summary grouping; the ``dimensions`` column is retained for sibling parity
    with ``Anonymous_Latency_Samples`` but always stays ``{}``.

    Privacy: schema deliberately contains no user_id, session_id, IP, or
    user-agent — only duration percentiles plus endpoint/method dims, matching
    ``Anonymous_Latency_Samples`` and ``Anonymous_Metrics``.

    Uses physical column-name strings in ``__table_args__`` (not class-qualified
    attribute references) because the class object does not yet exist when
    ``__table_args__`` is evaluated; SQLAlchemy resolves these against the
    ``name=`` kwarg on each Column and the Alembic migration uses the same
    physical names.
    """

    __tablename__ = "AnonymousLatencyDailyRollups"
    __table_args__ = (
        UniqueConstraint(
            "metricName",
            "endpoint",
            "method",
            "rollupDate",
            name="unique_latency_rollup_day",
        ),
        Index("idx_latency_rollup_metric_date", "metricName", "rollupDate"),
        Index("idx_latency_rollup_endpoint_date", "endpoint", "method", "rollupDate"),
    )

    id: int = Column(Integer, primary_key=True)
    # Plain string with no ForeignKey: the in-code LatencyMetricName enum plus its
    # coverage test are the single source of truth, so a FK would add a second
    # source of truth — the same deliberate choice as Anonymous_Latency_Samples.
    metric_name: str = Column(String(100), nullable=False, name="metricName")
    # NOT NULL (differs from the nullable raw table): rollup rows always carry a
    # matched endpoint/method so the unique constraint behaves predictably.
    endpoint: str = Column(String(255), nullable=False, name="endpoint")
    method: str = Column(String(10), nullable=False, name="method")
    rollup_date: date = Column(Date, nullable=False, name="rollupDate")
    p50_ms: float = Column(Numeric(20, 6), nullable=False, name="p50Ms")
    p95_ms: float = Column(Numeric(20, 6), nullable=False, name="p95Ms")
    p99_ms: float = Column(Numeric(20, 6), nullable=False, name="p99Ms")
    sample_count: int = Column(BigInteger, nullable=False, name="sampleCount")
    # Kept for sibling parity with Anonymous_Latency_Samples; rollups aggregate
    # across devices so this stays {}.
    dimensions: dict = Column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        name="dimensions",
    )
