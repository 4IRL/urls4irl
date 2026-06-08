from __future__ import annotations

from datetime import datetime
from typing import Literal

from flask import current_app
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


def _endpoint_to_url_pattern() -> dict[str, str]:
    """Build a {flask_endpoint_name: url_rule_pattern} map from the active app.

    Used by `top_events()` when category=api to convert stored endpoint names
    (e.g. "utubs.create_url") into the user-facing URL patterns the dashboard
    renders ("POST /utubs/<utub_id>/urls"). Falls back to the endpoint name
    itself when the endpoint is no longer registered (e.g. an old request
    against a route that has since been removed).
    """
    return {rule.endpoint: rule.rule for rule in current_app.url_map.iter_rules()}


def _per_endpoint_counts(
    *,
    window_start: datetime,
    window_end: datetime,
) -> dict[tuple[str, str], int]:
    """Return a {(endpoint, method): count} map for api_hit rows in the window.

    api_hit is the only event that carries per-request dimensions in flat
    columns (endpoint/method/status_code, promoted at flush time). This
    helper groups by those flat columns so the API tab can drill into per-
    route counts. Rows with NULL endpoint or method are excluded — those
    represent ingest paths the dashboard cannot meaningfully attribute.
    """
    total_count = func.sum(Anonymous_Metrics.count).label("total_count")
    rows = (
        db.session.query(
            Anonymous_Metrics.endpoint,
            Anonymous_Metrics.method,
            total_count,
        )
        .filter(
            Anonymous_Metrics.event_name == EventName.API_HIT.value,
            Anonymous_Metrics.bucket_start >= window_start,
            Anonymous_Metrics.bucket_start < window_end,
            Anonymous_Metrics.endpoint.isnot(None),
            Anonymous_Metrics.method.isnot(None),
        )
        .group_by(Anonymous_Metrics.endpoint, Anonymous_Metrics.method)
        .all()
    )
    return {(row.endpoint, row.method): int(row.total_count) for row in rows}


def _per_event_counts(
    *,
    window_start: datetime,
    window_end: datetime,
    category: EventCategory | None,
) -> dict[str, int]:
    """Return a {event_name: count} map summed across a half-open window."""
    total_count = func.sum(Anonymous_Metrics.count).label("total_count")
    query = (
        db.session.query(Anonymous_Metrics.event_name, total_count)
        .join(Event_Registry, Event_Registry.name == Anonymous_Metrics.event_name)
        .filter(
            Anonymous_Metrics.bucket_start >= window_start,
            Anonymous_Metrics.bucket_start < window_end,
        )
    )
    if category is not None:
        query = query.filter(Event_Registry.category == category)
    rows = query.group_by(Anonymous_Metrics.event_name).all()
    return {row.event_name: int(row.total_count) for row in rows}


def _top_endpoints_for_api_hit(
    *,
    window_start: datetime,
    window_end: datetime,
    previous_window_start: datetime,
    previous_window_end: datetime,
    limit: int,
) -> list[TopEventRow]:
    """Return the top api_hit rows grouped by (endpoint, method).

    Used when the API tab is the active category — api_hit is a single
    event that fans out across every HTTP route, so grouping by event_name
    collapses everything into one row. Grouping by the flat endpoint/method
    columns instead surfaces per-route hits like "POST /utubs/<utub_id>/urls".
    """
    total_count = func.sum(Anonymous_Metrics.count).label("total_count")
    rows = (
        db.session.query(
            Anonymous_Metrics.endpoint,
            Anonymous_Metrics.method,
            total_count,
        )
        .filter(
            Anonymous_Metrics.event_name == EventName.API_HIT.value,
            Anonymous_Metrics.bucket_start >= window_start,
            Anonymous_Metrics.bucket_start < window_end,
            Anonymous_Metrics.endpoint.isnot(None),
            Anonymous_Metrics.method.isnot(None),
        )
        .group_by(Anonymous_Metrics.endpoint, Anonymous_Metrics.method)
        .order_by(
            func.sum(Anonymous_Metrics.count).desc(),
            Anonymous_Metrics.endpoint.asc(),
            Anonymous_Metrics.method.asc(),
        )
        .limit(limit)
        .all()
    )
    previous_counts = _per_endpoint_counts(
        window_start=previous_window_start,
        window_end=previous_window_end,
    )
    endpoint_to_url = _endpoint_to_url_pattern()
    return [
        TopEventRow(
            event_name=f"{row.method} {endpoint_to_url.get(row.endpoint, row.endpoint)}",
            category=EventCategory.API.value,
            description=row.endpoint,
            total_count=int(row.total_count),
            previous_count=previous_counts.get((row.endpoint, row.method), 0),
        )
        for row in rows
    ]


def top_events(
    *,
    window_start: datetime,
    window_end: datetime,
    previous_window_start: datetime,
    previous_window_end: datetime,
    category: EventCategory | None,
    limit: int,
) -> list[TopEventRow]:
    """Return the top events by total count inside the half-open window.

    `window_start` is inclusive, `window_end` is exclusive — matches the
    convention used throughout the metrics pipeline. When `category` is
    provided, only rows in that EventCategory are considered. Rows are
    ordered by total_count descending and capped at `limit`.

    `previous_window_start`/`previous_window_end` define the equal-length
    interval immediately preceding `(start, end)` (callers compute via
    `previous_window()`). Each returned row carries `previous_count` for the
    same event in that interval; missing events get 0 so the dashboard's
    Δ-vs-prev column has a number even for newly-seen events.

    When `category == EventCategory.API`, rows are aggregated by the flat
    `(endpoint, method)` columns on api_hit rather than by event_name — api_hit
    is a single auto-instrumented event that spans every HTTP route, so a
    per-event-name aggregation collapses every endpoint into a single row.
    """
    if category is EventCategory.API:
        return _top_endpoints_for_api_hit(
            window_start=window_start,
            window_end=window_end,
            previous_window_start=previous_window_start,
            previous_window_end=previous_window_end,
            limit=limit,
        )

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

    previous_counts = _per_event_counts(
        window_start=previous_window_start,
        window_end=previous_window_end,
        category=category,
    )

    return [
        TopEventRow(
            event_name=row.event_name,
            category=row.category.value,
            description=row.description,
            total_count=int(row.total_count),
            previous_count=previous_counts.get(row.event_name, 0),
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
    endpoint: str | None = None,
    method: str | None = None,
) -> list[TimeseriesBucketSchema]:
    """Return per-bucket counts for `event_name` inside the half-open window.

    `resolution` is a Postgres `date_trunc` field name — narrowed to the
    `Literal["hour", "day"]` set so any caller passing arbitrary text is
    flagged at type-check time, providing defense-in-depth on top of the
    Pydantic schema validation at the HTTP boundary. Buckets are returned
    in chronological order; the underlying rows are already hour-aligned
    at write time, so passing "hour" returns the raw buckets and "day"
    aggregates them.

    Optional `endpoint`/`method` narrow the series to a single api_hit
    (endpoint, method) pair — used by the admin dashboard's API tab to
    chart per-endpoint timeseries (event_name=api_hit otherwise collapses
    every API route into one aggregate series).
    """
    bucket = func.date_trunc(resolution, Anonymous_Metrics.bucket_start).label("bucket")
    query = db.session.query(
        bucket,
        func.sum(Anonymous_Metrics.count).label("count"),
    ).filter(
        Anonymous_Metrics.event_name == event_name.value,
        Anonymous_Metrics.bucket_start >= window_start,
        Anonymous_Metrics.bucket_start < window_end,
    )
    if endpoint is not None:
        query = query.filter(Anonymous_Metrics.endpoint == endpoint)
    if method is not None:
        query = query.filter(Anonymous_Metrics.method == method)

    rows = query.group_by(bucket).order_by(bucket).all()

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
