from __future__ import annotations

from datetime import datetime
from typing import Literal

from sqlalchemy import func

from backend import db
from backend.metrics.events import EventCategory, EventName
from backend.models.anonymous_metrics import Anonymous_Metrics
from backend.models.event_registry import Event_Registry
from backend.schemas.metrics import (
    SummaryCategoryCount,
    TimeseriesBucketSchema,
    TopEventRow,
)


def top_events(
    *,
    window_start: datetime,
    window_end: datetime,
    category: EventCategory | None,
    limit: int,
) -> list[TopEventRow]:
    """Return the top events by total count inside the half-open window.

    `window_start` is inclusive, `window_end` is exclusive — matches the
    convention used throughout the metrics pipeline. When `category` is
    provided, only rows in that EventCategory are considered. Rows are
    ordered by total_count descending and capped at `limit`.
    """
    total_count = func.sum(Anonymous_Metrics.count).label("total_count")
    query = (
        db.session.query(
            Anonymous_Metrics.event_name,
            Event_Registry.category,
            Event_Registry.description,
            total_count,
        )
        .join(Event_Registry, Event_Registry.name == Anonymous_Metrics.event_name)
        .filter(
            Anonymous_Metrics.bucket_start >= window_start,
            Anonymous_Metrics.bucket_start < window_end,
        )
    )
    if category is not None:
        query = query.filter(Event_Registry.category == category)

    rows = (
        query.group_by(
            Anonymous_Metrics.event_name,
            Event_Registry.category,
            Event_Registry.description,
        )
        .order_by(
            func.sum(Anonymous_Metrics.count).desc(),
            Anonymous_Metrics.event_name.asc(),
        )
        .limit(limit)
        .all()
    )

    return [
        TopEventRow(
            event_name=row.event_name,
            category=row.category.value,
            description=row.description,
            total_count=int(row.total_count),
        )
        for row in rows
    ]


# Why: `resolution` finer than the writer's METRICS_BUCKET_SECONDS=3600 floor
# collapses to the bucket granularity — the writer always stores hour-aligned
# rows, so sub-hour resolutions would just return the same hourly buckets.
def timeseries(
    *,
    event_name: EventName,
    window_start: datetime,
    window_end: datetime,
    resolution: Literal["hour", "day"],
) -> list[TimeseriesBucketSchema]:
    """Return per-bucket counts for `event_name` inside the half-open window.

    `resolution` is a Postgres `date_trunc` field name — narrowed to the
    `Literal["hour", "day"]` set so any caller passing arbitrary text is
    flagged at type-check time, providing defense-in-depth on top of the
    Pydantic schema validation at the HTTP boundary. Buckets are returned
    in chronological order; the underlying rows are already hour-aligned
    at write time, so passing "hour" returns the raw buckets and "day"
    aggregates them.
    """
    bucket = func.date_trunc(resolution, Anonymous_Metrics.bucket_start).label("bucket")
    rows = (
        db.session.query(
            bucket,
            func.sum(Anonymous_Metrics.count).label("count"),
        )
        .filter(
            Anonymous_Metrics.event_name == event_name.value,
            Anonymous_Metrics.bucket_start >= window_start,
            Anonymous_Metrics.bucket_start < window_end,
        )
        .group_by(bucket)
        .order_by(bucket)
        .all()
    )

    return [
        TimeseriesBucketSchema(bucket=row.bucket, count=int(row.count)) for row in rows
    ]


def _by_category(start: datetime, end: datetime) -> dict[str, int]:
    """Sum counts grouped by EventCategory inside the half-open window.

    `Event_Registry.category` is a SQLAlchemy `Enum(EventCategory, ...)`
    column, so SQLAlchemy returns Python EventCategory enum instances —
    call `.value` so the result dict is keyed by the StrEnum value
    ("api"/"domain"/"ui") rather than the enum object itself. Pydantic's
    `SummaryCategoryCount.category: str` would otherwise reject the enum.
    """
    rows = (
        db.session.query(
            Event_Registry.category,
            func.sum(Anonymous_Metrics.count).label("total"),
        )
        .join(Event_Registry, Event_Registry.name == Anonymous_Metrics.event_name)
        .filter(
            Anonymous_Metrics.bucket_start >= start,
            Anonymous_Metrics.bucket_start < end,
        )
        .group_by(Event_Registry.category)
        .all()
    )
    return {row.category.value: int(row.total) for row in rows}


def summary(
    *,
    window_start: datetime,
    window_end: datetime,
    previous_window_start: datetime,
    previous_window_end: datetime,
) -> tuple[list[SummaryCategoryCount], datetime | None]:
    """Return per-category totals plus the most recent bucket timestamp.

    Missing categories are filled with 0 so both `current` and `previous`
    are always integers. Result is sorted by category value so the wire
    shape is deterministic across calls.

    The second tuple element is `MAX(bucket_start)` across the entire
    `AnonymousMetrics` table — NOT restricted to the queried window — so the
    admin dashboard's freshness badge keeps ticking even when the current
    window is empty. Returns `None` when the table is empty.
    """
    current_dict = _by_category(window_start, window_end)
    previous_dict = _by_category(previous_window_start, previous_window_end)
    by_category_list = [
        SummaryCategoryCount(
            category=category_value,
            current=current_dict.get(category_value, 0),
            previous=previous_dict.get(category_value, 0),
        )
        for category_value in sorted({*current_dict, *previous_dict})
    ]
    last_flush_at: datetime | None = db.session.query(
        func.max(Anonymous_Metrics.bucket_start)
    ).scalar()
    return by_category_list, last_flush_at
