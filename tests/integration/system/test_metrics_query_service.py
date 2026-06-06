from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from flask import Flask

from backend.metrics.events import (
    EVENT_CATEGORY,
    EVENT_DESCRIPTIONS,
    EventCategory,
    EventName,
)
from backend.metrics.query_service import summary, timeseries, top_events
from tests.integration.system.metrics_helpers import (
    build_pg_conn,
    truncate_metrics_tables,
)

pytestmark = pytest.mark.cli


_WINDOW_REFERENCE: datetime = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


def _truncate_metrics_and_registry(pg_conn: Any) -> None:
    truncate_metrics_tables(pg_conn)
    with pg_conn.cursor() as cur:
        cur.execute('DELETE FROM "EventRegistry"')
    pg_conn.commit()


def _insert_metric_row(
    pg_conn: Any,
    *,
    event_name: EventName,
    bucket_start: datetime,
    dimensions: dict | None = None,
    count: int = 1,
    endpoint: str | None = None,
    method: str | None = None,
    status_code: int | None = None,
) -> None:
    """Seed one AnonymousMetrics row + ensure its EventRegistry row exists.

    `Anonymous_Metrics.event_name` is FK-constrained against
    `EventRegistry.name` — without the registry row the insert raises
    `ForeignKeyViolation`. The double-quoted identifiers match the
    SQLAlchemy `__tablename__` values exactly; PostgreSQL folds unquoted
    identifiers to lowercase.
    """
    dims = dimensions if dimensions is not None else {}
    with pg_conn.cursor() as cur:
        cur.execute(
            'INSERT INTO "EventRegistry" ("name", "category", "description", "addedAt")'
            " VALUES (%s, %s, %s, NOW())"
            ' ON CONFLICT ("name") DO NOTHING',
            (
                event_name.value,
                EVENT_CATEGORY[event_name].value,
                EVENT_DESCRIPTIONS[event_name],
            ),
        )
        cur.execute(
            'INSERT INTO "AnonymousMetrics"'
            ' ("eventName", "endpoint", "method", "statusCode",'
            ' "bucketStart", "dimensions", "count")'
            " VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (
                event_name.value,
                endpoint,
                method,
                status_code,
                bucket_start,
                json.dumps(dims),
                count,
            ),
        )
    pg_conn.commit()


def test_top_events_aggregates_by_event_name(
    metrics_enabled_runner_app: Flask,
) -> None:
    """
    GIVEN three rows for UTUB_OPENED (counts 5, 7, 2) and one row for API_HIT
        (count 100), all inside the window
    WHEN top_events is called with category=None
    THEN two rows are returned, sorted by total_count desc, each row's
        description matches the EventRegistry mapping.
    """
    app = metrics_enabled_runner_app
    window_end = _WINDOW_REFERENCE
    window_start = window_end - timedelta(days=1)
    inside = window_start + timedelta(hours=1)

    pg_conn = build_pg_conn(app)
    try:
        _truncate_metrics_and_registry(pg_conn)
        _insert_metric_row(
            pg_conn, event_name=EventName.UTUB_OPENED, bucket_start=inside, count=5
        )
        _insert_metric_row(
            pg_conn,
            event_name=EventName.UTUB_OPENED,
            bucket_start=inside + timedelta(hours=1),
            count=7,
        )
        _insert_metric_row(
            pg_conn,
            event_name=EventName.UTUB_OPENED,
            bucket_start=inside + timedelta(hours=2),
            count=2,
        )
        _insert_metric_row(
            pg_conn,
            event_name=EventName.API_HIT,
            bucket_start=inside + timedelta(hours=3),
            count=100,
        )

        with app.app_context():
            rows = top_events(
                window_start=window_start,
                window_end=window_end,
                category=None,
                limit=10,
            )

        assert len(rows) == 2
        assert rows[0].event_name == EventName.API_HIT.value
        assert rows[0].total_count == 100
        assert rows[0].description == EVENT_DESCRIPTIONS[EventName.API_HIT]
        assert rows[1].event_name == EventName.UTUB_OPENED.value
        assert rows[1].total_count == 14
        assert rows[1].description == EVENT_DESCRIPTIONS[EventName.UTUB_OPENED]
    finally:
        _truncate_metrics_and_registry(pg_conn)
        pg_conn.close()


def test_top_events_filters_by_category(
    metrics_enabled_runner_app: Flask,
) -> None:
    """
    GIVEN UTUB_OPENED (domain) and API_HIT (api) rows in the window
    WHEN top_events is called with category=EventCategory.DOMAIN
    THEN only UTUB_OPENED is returned.
    """
    app = metrics_enabled_runner_app
    window_end = _WINDOW_REFERENCE
    window_start = window_end - timedelta(days=1)
    inside = window_start + timedelta(hours=1)

    pg_conn = build_pg_conn(app)
    try:
        _truncate_metrics_and_registry(pg_conn)
        _insert_metric_row(
            pg_conn, event_name=EventName.UTUB_OPENED, bucket_start=inside, count=5
        )
        _insert_metric_row(
            pg_conn,
            event_name=EventName.API_HIT,
            bucket_start=inside + timedelta(hours=1),
            count=100,
        )

        with app.app_context():
            rows = top_events(
                window_start=window_start,
                window_end=window_end,
                category=EventCategory.DOMAIN,
                limit=10,
            )

        assert len(rows) == 1
        assert rows[0].event_name == EventName.UTUB_OPENED.value
        assert rows[0].category == EventCategory.DOMAIN.value
    finally:
        _truncate_metrics_and_registry(pg_conn)
        pg_conn.close()


def test_top_events_respects_limit(
    metrics_enabled_runner_app: Flask,
) -> None:
    """
    GIVEN five distinct events in the window
    WHEN top_events is called with limit=3
    THEN exactly three rows are returned.
    """
    app = metrics_enabled_runner_app
    window_end = _WINDOW_REFERENCE
    window_start = window_end - timedelta(days=1)
    inside = window_start + timedelta(hours=1)

    pg_conn = build_pg_conn(app)
    try:
        _truncate_metrics_and_registry(pg_conn)
        seeded_events = [
            EventName.UTUB_OPENED,
            EventName.UTUB_CREATED,
            EventName.UTUB_DELETED,
            EventName.URL_ACCESSED,
            EventName.API_HIT,
        ]
        for offset, event_name in enumerate(seeded_events):
            _insert_metric_row(
                pg_conn,
                event_name=event_name,
                bucket_start=inside + timedelta(hours=offset),
                count=offset + 1,
            )

        with app.app_context():
            rows = top_events(
                window_start=window_start,
                window_end=window_end,
                category=None,
                limit=3,
            )

        assert len(rows) == 3
    finally:
        _truncate_metrics_and_registry(pg_conn)
        pg_conn.close()


def test_top_events_empty_window_returns_empty_list(
    metrics_enabled_runner_app: Flask,
) -> None:
    """
    GIVEN rows seeded with bucket_start BEFORE the window
    WHEN top_events is called against the window
    THEN the result is [] and length is 0.
    """
    app = metrics_enabled_runner_app
    window_end = _WINDOW_REFERENCE
    window_start = window_end - timedelta(days=1)
    before_window = window_start - timedelta(days=2)

    pg_conn = build_pg_conn(app)
    try:
        _truncate_metrics_and_registry(pg_conn)
        _insert_metric_row(
            pg_conn,
            event_name=EventName.UTUB_OPENED,
            bucket_start=before_window,
            count=5,
        )

        with app.app_context():
            rows = top_events(
                window_start=window_start,
                window_end=window_end,
                category=None,
                limit=10,
            )

        assert rows == []
    finally:
        _truncate_metrics_and_registry(pg_conn)
        pg_conn.close()


def test_timeseries_groups_by_resolution(
    metrics_enabled_runner_app: Flask,
) -> None:
    """
    GIVEN two UTUB_OPENED rows in two distinct hour buckets within one day
    WHEN timeseries is called with resolution="hour"
    THEN two rows are returned in chronological order with the correct sums
    AND when resolution="day", the buckets collapse to one row.
    """
    app = metrics_enabled_runner_app
    window_end = _WINDOW_REFERENCE
    window_start = window_end - timedelta(days=1)
    first_bucket = window_start + timedelta(hours=1)
    second_bucket = first_bucket + timedelta(hours=2)

    pg_conn = build_pg_conn(app)
    try:
        _truncate_metrics_and_registry(pg_conn)
        _insert_metric_row(
            pg_conn,
            event_name=EventName.UTUB_OPENED,
            bucket_start=first_bucket,
            count=3,
        )
        _insert_metric_row(
            pg_conn,
            event_name=EventName.UTUB_OPENED,
            bucket_start=second_bucket,
            count=4,
        )

        with app.app_context():
            hourly = timeseries(
                event_name=EventName.UTUB_OPENED,
                window_start=window_start,
                window_end=window_end,
                resolution="hour",
            )
            daily = timeseries(
                event_name=EventName.UTUB_OPENED,
                window_start=window_start,
                window_end=window_end,
                resolution="day",
            )

        assert len(hourly) == 2
        assert hourly[0].bucket < hourly[1].bucket
        assert hourly[0].count == 3
        assert hourly[1].count == 4

        assert len(daily) == 1
        assert daily[0].count == 7
    finally:
        _truncate_metrics_and_registry(pg_conn)
        pg_conn.close()


def test_timeseries_empty_window_returns_empty_list(
    metrics_enabled_runner_app: Flask,
) -> None:
    """
    GIVEN no rows exist for the event in the window
    WHEN timeseries is called
    THEN the result is [] (assert-before-state: confirm no rows first).
    """
    app = metrics_enabled_runner_app
    window_end = _WINDOW_REFERENCE
    window_start = window_end - timedelta(days=1)

    pg_conn = build_pg_conn(app)
    try:
        _truncate_metrics_and_registry(pg_conn)

        with pg_conn.cursor() as cur:
            cur.execute(
                'SELECT COUNT(*) FROM "AnonymousMetrics"'
                ' WHERE "eventName" = %s AND "bucketStart" >= %s'
                ' AND "bucketStart" < %s',
                (EventName.UTUB_OPENED.value, window_start, window_end),
            )
            existing_count = cur.fetchone()[0]
        assert existing_count == 0

        with app.app_context():
            rows = timeseries(
                event_name=EventName.UTUB_OPENED,
                window_start=window_start,
                window_end=window_end,
                resolution="hour",
            )

        assert rows == []
    finally:
        _truncate_metrics_and_registry(pg_conn)
        pg_conn.close()


def test_summary_current_vs_previous_window(
    metrics_enabled_runner_app: Flask,
) -> None:
    """
    GIVEN 6 API_HIT rows in the current window (sum 60) and 3 API_HIT rows
        in the prior window (sum 30)
    WHEN summary is called
    THEN by_category returns a list[SummaryCategoryCount] where the api row
        has current=60 and previous=30, and category is a str (not enum).
    """
    app = metrics_enabled_runner_app
    window_end = _WINDOW_REFERENCE
    window_start = window_end - timedelta(days=1)
    previous_window_end = window_start
    previous_window_start = previous_window_end - timedelta(days=1)

    current_inside = window_start + timedelta(hours=1)
    previous_inside = previous_window_start + timedelta(hours=1)

    pg_conn = build_pg_conn(app)
    try:
        _truncate_metrics_and_registry(pg_conn)
        for offset in range(6):
            _insert_metric_row(
                pg_conn,
                event_name=EventName.API_HIT,
                bucket_start=current_inside + timedelta(hours=offset),
                count=10,
            )
        for offset in range(3):
            _insert_metric_row(
                pg_conn,
                event_name=EventName.API_HIT,
                bucket_start=previous_inside + timedelta(hours=offset),
                count=10,
            )

        with app.app_context():
            result = summary(
                window_start=window_start,
                window_end=window_end,
                previous_window_start=previous_window_start,
                previous_window_end=previous_window_end,
            )

        api_row = next(row for row in result if row.category == "api")
        assert api_row.current == 60
        assert api_row.previous == 30
        assert isinstance(api_row.category, str)
    finally:
        _truncate_metrics_and_registry(pg_conn)
        pg_conn.close()


def test_summary_empty_window_returns_empty_list(
    metrics_enabled_runner_app: Flask,
) -> None:
    """
    GIVEN no rows exist for the current OR previous windows
    WHEN summary is called
    THEN the result is [] (assert-before-state: confirm no rows in either
        window first).
    """
    app = metrics_enabled_runner_app
    window_end = _WINDOW_REFERENCE
    window_start = window_end - timedelta(days=1)
    previous_window_end = window_start
    previous_window_start = previous_window_end - timedelta(days=1)

    pg_conn = build_pg_conn(app)
    try:
        _truncate_metrics_and_registry(pg_conn)

        with pg_conn.cursor() as cur:
            cur.execute(
                'SELECT COUNT(*) FROM "AnonymousMetrics"'
                ' WHERE "bucketStart" >= %s AND "bucketStart" < %s',
                (previous_window_start, window_end),
            )
            existing_count = cur.fetchone()[0]
        assert existing_count == 0

        with app.app_context():
            result = summary(
                window_start=window_start,
                window_end=window_end,
                previous_window_start=previous_window_start,
                previous_window_end=previous_window_end,
            )

        assert result == []
    finally:
        _truncate_metrics_and_registry(pg_conn)
        pg_conn.close()


def test_query_service_join_includes_description_for_every_event(
    metrics_enabled_runner_app: Flask,
) -> None:
    """
    GIVEN seeded rows across multiple event names
    WHEN top_events is called
    THEN every returned row has a non-empty description from EventRegistry.
    """
    app = metrics_enabled_runner_app
    window_end = _WINDOW_REFERENCE
    window_start = window_end - timedelta(days=1)
    inside = window_start + timedelta(hours=1)

    pg_conn = build_pg_conn(app)
    try:
        _truncate_metrics_and_registry(pg_conn)
        for offset, event_name in enumerate(
            (EventName.UTUB_OPENED, EventName.API_HIT, EventName.URL_ACCESSED)
        ):
            _insert_metric_row(
                pg_conn,
                event_name=event_name,
                bucket_start=inside + timedelta(hours=offset),
                count=offset + 1,
            )

        with app.app_context():
            rows = top_events(
                window_start=window_start,
                window_end=window_end,
                category=None,
                limit=10,
            )

        assert len(rows) == 3
        for row in rows:
            assert row.description != ""
            assert row.description is not None
    finally:
        _truncate_metrics_and_registry(pg_conn)
        pg_conn.close()
