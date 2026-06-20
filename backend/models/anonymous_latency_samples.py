from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from backend import db


class Anonymous_Latency_Samples(db.Model):
    """Fact table — raw per-request duration observations (one row per sample).

    Each row records one request's end-to-end handling time in milliseconds,
    tagged with the matched ``endpoint``/``method`` (promoted to flat columns at
    flush, like ``api_hit``) and a ``device_type`` kept in JSONB ``dimensions``.
    Storing raw samples (not pre-aggregated buckets) lets the query service
    compute exact arbitrary percentiles via Postgres ``percentile_cont``.

    Privacy: schema deliberately contains no user_id, session_id, IP, or
    user-agent — only a duration magnitude plus endpoint/method/device dims,
    matching ``Anonymous_Metrics`` and ``Anonymous_Gauges``. Append-only with no
    unique constraint, mirroring ``Anonymous_Gauges``.

    Uses physical column-name strings in ``__table_args__`` (not class-qualified
    attribute references) because the class object does not yet exist when
    ``__table_args__`` is evaluated; SQLAlchemy resolves these against the
    ``name=`` kwarg on each Column and the Alembic migration uses the same
    physical names.
    """

    __tablename__ = "AnonymousLatencySamples"
    __table_args__ = (
        Index("idx_latency_metric_time", "metricName", "observedAt"),
        Index("idx_latency_endpoint_time", "endpoint", "method", "observedAt"),
    )

    id: int = Column(Integer, primary_key=True)
    # Plain string with no ForeignKey: the in-code LatencyMetricName enum plus its
    # coverage test are the single source of truth, so a FK would add a second
    # source of truth — the same deliberate choice as Anonymous_Gauges.
    metric_name: str = Column(String(100), nullable=False, name="metricName")
    endpoint: str | None = Column(String(255), nullable=True, name="endpoint")
    method: str | None = Column(String(10), nullable=True, name="method")
    observed_at: datetime = Column(
        DateTime(timezone=True), nullable=False, name="observedAt"
    )
    duration_ms: float = Column(Numeric(20, 6), nullable=False, name="durationMs")
    # Holds {"device_type": <int>}. server_default keeps the model in sync with
    # the migration (an intentional divergence from Anonymous_Gauges, which omits
    # it on its dimensions column).
    dimensions: dict = Column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        name="dimensions",
    )
