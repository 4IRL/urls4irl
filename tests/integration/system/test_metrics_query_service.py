from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Generator

import pytest
from flask import Flask

from backend.extensions.metrics.buckets import previous_window
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


@pytest.fixture
def metrics_pg_conn(metrics_enabled_runner_app: Flask) -> Generator[Any, None, None]:
    """Yield an already-truncated psycopg2 connection to the caller.

    Before yielding, truncates ``AnonymousMetrics`` and ``EventRegistry`` so
    each test starts from a clean slate.  After the test completes — even on
    failure — teardown truncates both tables again and closes the connection.
    """
    pg_conn = build_pg_conn(metrics_enabled_runner_app)
    _truncate_metrics_and_registry(pg_conn)
    yield pg_conn
    _truncate_metrics_and_registry(pg_conn)
    pg_conn.close()


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
    metrics_pg_conn: Any,
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

    _insert_metric_row(
        metrics_pg_conn, event_name=EventName.UTUB_OPENED, bucket_start=inside, count=5
    )
    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.UTUB_OPENED,
        bucket_start=inside + timedelta(hours=1),
        count=7,
    )
    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.UTUB_OPENED,
        bucket_start=inside + timedelta(hours=2),
        count=2,
    )
    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.API_HIT,
        bucket_start=inside + timedelta(hours=3),
        count=100,
    )

    prev_start, prev_end = previous_window(window_start, window_end)
    with app.app_context():
        rows = top_events(
            window_start=window_start,
            window_end=window_end,
            previous_window_start=prev_start,
            previous_window_end=prev_end,
            category=None,
            limit=10,
        )

    assert len(rows) == 2
    assert rows[0].event_name == EventName.API_HIT.value
    assert rows[0].total_count == 100
    assert rows[0].previous_count == 0
    assert rows[0].description == EVENT_DESCRIPTIONS[EventName.API_HIT]
    assert rows[1].event_name == EventName.UTUB_OPENED.value
    assert rows[1].total_count == 14
    assert rows[1].previous_count == 0
    assert rows[1].description == EVENT_DESCRIPTIONS[EventName.UTUB_OPENED]


def test_top_events_filters_by_category(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
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

    _insert_metric_row(
        metrics_pg_conn, event_name=EventName.UTUB_OPENED, bucket_start=inside, count=5
    )
    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.API_HIT,
        bucket_start=inside + timedelta(hours=1),
        count=100,
    )

    prev_start, prev_end = previous_window(window_start, window_end)
    with app.app_context():
        rows = top_events(
            window_start=window_start,
            window_end=window_end,
            previous_window_start=prev_start,
            previous_window_end=prev_end,
            category=EventCategory.DOMAIN,
            limit=10,
        )

    assert len(rows) == 1
    assert rows[0].event_name == EventName.UTUB_OPENED.value
    assert rows[0].category == EventCategory.DOMAIN.value


def test_top_events_respects_limit(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
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

    seeded_events = [
        EventName.UTUB_OPENED,
        EventName.UTUB_CREATED,
        EventName.UTUB_DELETED,
        EventName.URL_ACCESSED,
        EventName.API_HIT,
    ]
    for offset, event_name in enumerate(seeded_events):
        _insert_metric_row(
            metrics_pg_conn,
            event_name=event_name,
            bucket_start=inside + timedelta(hours=offset),
            count=offset + 1,
        )

    prev_start, prev_end = previous_window(window_start, window_end)
    with app.app_context():
        rows = top_events(
            window_start=window_start,
            window_end=window_end,
            previous_window_start=prev_start,
            previous_window_end=prev_end,
            category=None,
            limit=3,
        )

    assert len(rows) == 3


def test_top_events_breaks_ties_alphabetically_by_event_name(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN three events with identical total_count in the window
    WHEN top_events is called
    THEN the rows are returned in ascending event_name order, so the same
        query always returns the same rank — no flip-flop under ties.

    Without the secondary `event_name ASC` sort, Postgres can return tied
    rows in either order across calls, and `LIMIT N` would silently
    promote/demote rows on the rank-N boundary.
    """
    app = metrics_enabled_runner_app
    window_end = _WINDOW_REFERENCE
    window_start = window_end - timedelta(days=1)
    inside = window_start + timedelta(hours=1)

    # All three events get count=5 so total_count is identical.
    for event_name in (
        EventName.UTUB_OPENED,
        EventName.UTUB_CREATED,
        EventName.UTUB_DELETED,
    ):
        _insert_metric_row(
            metrics_pg_conn,
            event_name=event_name,
            bucket_start=inside,
            count=5,
        )

    prev_start, prev_end = previous_window(window_start, window_end)
    with app.app_context():
        rows = top_events(
            window_start=window_start,
            window_end=window_end,
            previous_window_start=prev_start,
            previous_window_end=prev_end,
            category=None,
            limit=10,
        )

    returned_names = [row.event_name for row in rows]
    assert returned_names == sorted(returned_names)
    assert {row.total_count for row in rows} == {5}


def test_top_events_api_category_groups_by_endpoint_method(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN three api_hit rows: two for (utubs.get_utub_details, GET) and one
        for (splash.login_form, POST), all in the current window
    WHEN top_events is called with category=EventCategory.API
    THEN two rows are returned (one per distinct endpoint/method pair),
        ordered by total_count descending, with each row's `event_name`
        formatted as "<METHOD> <url_pattern>" via the current app's url_map.
    """
    app = metrics_enabled_runner_app
    window_end = _WINDOW_REFERENCE
    window_start = window_end - timedelta(days=1)
    prev_start, prev_end = previous_window(window_start, window_end)
    # Offset to bucket 18:00 (mid-window, distinct from the +1h/+2h/+3h
    # buckets other tests in this file reuse) so the per-test truncate
    # races we've seen on api_hit unique-constraint don't bite.
    inside = window_start + timedelta(hours=6)

    # Production writes endpoint/method/status_code into BOTH the flat columns
    # and the dimensions dict (see writer.py for api_hit). Mirror that so the
    # `(bucketStart, eventName, dimensions)` unique constraint allows two
    # distinct endpoints in the same bucket.
    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.API_HIT,
        bucket_start=inside,
        endpoint="utubs.get_single_utub",
        method="GET",
        status_code=200,
        dimensions={
            "endpoint": "utubs.get_single_utub",
            "method": "GET",
            "status_code": 200,
        },
        count=7,
    )
    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.API_HIT,
        bucket_start=inside + timedelta(hours=1),
        endpoint="utubs.get_single_utub",
        method="GET",
        status_code=200,
        dimensions={
            "endpoint": "utubs.get_single_utub",
            "method": "GET",
            "status_code": 200,
        },
        count=3,
    )
    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.API_HIT,
        bucket_start=inside,
        endpoint="splash.splash_page",
        method="GET",
        status_code=200,
        dimensions={
            "endpoint": "splash.splash_page",
            "method": "GET",
            "status_code": 200,
        },
        count=2,
    )

    with app.app_context():
        rows = top_events(
            window_start=window_start,
            window_end=window_end,
            previous_window_start=prev_start,
            previous_window_end=prev_end,
            category=EventCategory.API,
            limit=10,
        )

    assert len(rows) == 2
    top_row = rows[0]
    second_row = rows[1]
    assert top_row.category == EventCategory.API.value
    assert top_row.total_count == 10
    assert top_row.description == "utubs.get_single_utub"
    assert top_row.event_name.startswith("GET ")
    assert top_row.event_name != "GET utubs.get_single_utub"
    assert second_row.total_count == 2
    assert second_row.description == "splash.splash_page"


def test_top_events_api_category_excludes_rows_with_null_endpoint(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN an api_hit row with endpoint=NULL (ingest path the dashboard cannot
        attribute) and a normal api_hit row with endpoint set
    WHEN top_events is called with category=EventCategory.API
    THEN only the row with a non-null endpoint is returned.
    """
    app = metrics_enabled_runner_app
    window_end = _WINDOW_REFERENCE
    window_start = window_end - timedelta(days=1)
    prev_start, prev_end = previous_window(window_start, window_end)
    inside = window_start + timedelta(hours=1)

    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.API_HIT,
        bucket_start=inside,
        endpoint=None,
        method=None,
        count=99,
    )
    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.API_HIT,
        bucket_start=inside + timedelta(hours=1),
        endpoint="utubs.get_single_utub",
        method="GET",
        dimensions={"endpoint": "utubs.get_single_utub", "method": "GET"},
        count=5,
    )

    with app.app_context():
        rows = top_events(
            window_start=window_start,
            window_end=window_end,
            previous_window_start=prev_start,
            previous_window_end=prev_end,
            category=EventCategory.API,
            limit=10,
        )

    assert len(rows) == 1
    assert rows[0].description == "utubs.get_single_utub"
    assert rows[0].total_count == 5


def test_top_events_reports_previous_window_count_per_event(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN UTUB_OPENED with count 8 in the current window AND count 5 in the
        previous window, AND API_HIT with count 100 only in the current window
    WHEN top_events is called with the previous-window range supplied
    THEN UTUB_OPENED.previous_count == 5, API_HIT.previous_count == 0 (no
        previous data), and both rows still order by current total_count desc.
    """
    app = metrics_enabled_runner_app
    window_end = _WINDOW_REFERENCE
    window_start = window_end - timedelta(days=1)
    prev_start, prev_end = previous_window(window_start, window_end)
    inside_current = window_start + timedelta(hours=1)
    inside_previous = prev_start + timedelta(hours=1)

    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.UTUB_OPENED,
        bucket_start=inside_current,
        count=8,
    )
    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.UTUB_OPENED,
        bucket_start=inside_previous,
        count=5,
    )
    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.API_HIT,
        bucket_start=inside_current,
        count=100,
    )

    with app.app_context():
        rows = top_events(
            window_start=window_start,
            window_end=window_end,
            previous_window_start=prev_start,
            previous_window_end=prev_end,
            category=None,
            limit=10,
        )

    assert len(rows) == 2
    api_row = next(row for row in rows if row.event_name == EventName.API_HIT.value)
    utub_row = next(
        row for row in rows if row.event_name == EventName.UTUB_OPENED.value
    )
    assert api_row.total_count == 100
    assert api_row.previous_count == 0
    assert utub_row.total_count == 8
    assert utub_row.previous_count == 5


def test_top_events_empty_window_returns_empty_list(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
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

    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.UTUB_OPENED,
        bucket_start=before_window,
        count=5,
    )

    prev_start, prev_end = previous_window(window_start, window_end)
    with app.app_context():
        rows = top_events(
            window_start=window_start,
            window_end=window_end,
            previous_window_start=prev_start,
            previous_window_end=prev_end,
            category=None,
            limit=10,
        )

    assert rows == []


def test_timeseries_groups_by_resolution(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
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

    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.UTUB_OPENED,
        bucket_start=first_bucket,
        count=3,
    )
    _insert_metric_row(
        metrics_pg_conn,
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


def test_timeseries_empty_window_returns_empty_list(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN no rows exist for the event in the window
    WHEN timeseries is called
    THEN the result is [] (assert-before-state: confirm no rows first).
    """
    app = metrics_enabled_runner_app
    window_end = _WINDOW_REFERENCE
    window_start = window_end - timedelta(days=1)

    with metrics_pg_conn.cursor() as cur:
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


def test_timeseries_filters_by_endpoint_and_method(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN api_hit rows for two distinct (endpoint, method) pairs in the same
        bucket plus a third api_hit row for the same endpoint but a different
        method (POST vs GET)
    WHEN timeseries is called with event_name=API_HIT + endpoint + method
    THEN only the matching (endpoint, method) row's count is summed; the
        other endpoint and the other method are excluded.
    """
    app = metrics_enabled_runner_app
    window_end = _WINDOW_REFERENCE
    window_start = window_end - timedelta(days=1)
    # Bucket 18:00 (mid-window, distinct from other tests' +1h..+4h reuse)
    # to avoid the api_hit unique-constraint race we hit elsewhere.
    inside = window_start + timedelta(hours=6)

    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.API_HIT,
        bucket_start=inside,
        endpoint="utubs.get_single_utub",
        method="GET",
        dimensions={"endpoint": "utubs.get_single_utub", "method": "GET"},
        count=4,
    )
    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.API_HIT,
        bucket_start=inside,
        endpoint="splash.splash_page",
        method="GET",
        dimensions={"endpoint": "splash.splash_page", "method": "GET"},
        count=10,
    )
    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.API_HIT,
        bucket_start=inside,
        endpoint="utubs.get_single_utub",
        method="POST",
        dimensions={"endpoint": "utubs.get_single_utub", "method": "POST"},
        count=7,
    )

    with app.app_context():
        rows = timeseries(
            event_name=EventName.API_HIT,
            window_start=window_start,
            window_end=window_end,
            resolution="hour",
            endpoint="utubs.get_single_utub",
            method="GET",
        )

    assert len(rows) == 1
    assert rows[0].count == 4


def test_summary_current_vs_previous_window(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
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

    for offset in range(6):
        _insert_metric_row(
            metrics_pg_conn,
            event_name=EventName.API_HIT,
            bucket_start=current_inside + timedelta(hours=offset),
            count=10,
        )
    for offset in range(3):
        _insert_metric_row(
            metrics_pg_conn,
            event_name=EventName.API_HIT,
            bucket_start=previous_inside + timedelta(hours=offset),
            count=10,
        )

    with app.app_context():
        result, _ = summary(
            window_start=window_start,
            window_end=window_end,
            previous_window_start=previous_window_start,
            previous_window_end=previous_window_end,
        )

    api_row = next(row for row in result if row.category == "api")
    assert api_row.current == 60
    assert api_row.previous == 30
    assert isinstance(api_row.category, str)


def test_summary_empty_window_returns_empty_list(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
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

    with metrics_pg_conn.cursor() as cur:
        cur.execute(
            'SELECT COUNT(*) FROM "AnonymousMetrics"'
            ' WHERE "bucketStart" >= %s AND "bucketStart" < %s',
            (previous_window_start, window_end),
        )
        existing_count = cur.fetchone()[0]
    assert existing_count == 0

    with app.app_context():
        category_list, _ = summary(
            window_start=window_start,
            window_end=window_end,
            previous_window_start=previous_window_start,
            previous_window_end=previous_window_end,
        )

    assert category_list == []


def test_summary_includes_last_flush_at_when_metrics_exist(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN a single seeded AnonymousMetrics row with a known bucket_start
    WHEN summary(...) is called
    THEN the second tuple element equals that bucket_start exactly, so the
        dashboard's freshness badge can render `now - last_flush_at` without
        an additional round trip.
    """
    app = metrics_enabled_runner_app
    window_end = _WINDOW_REFERENCE
    window_start = window_end - timedelta(days=1)
    previous_window_end = window_start
    previous_window_start = previous_window_end - timedelta(days=1)
    seeded_bucket_start = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.API_HIT,
        bucket_start=seeded_bucket_start,
    )

    with app.app_context():
        _, last_flush_at = summary(
            window_start=window_start,
            window_end=window_end,
            previous_window_start=previous_window_start,
            previous_window_end=previous_window_end,
        )

    assert last_flush_at == seeded_bucket_start


def test_summary_last_flush_at_is_null_when_no_metrics(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN an empty AnonymousMetrics table (assert-before-state)
    WHEN summary(...) is called
    THEN the second tuple element is None — the badge falls back to its
        empty-state text rather than rendering a stale timestamp.
    """
    app = metrics_enabled_runner_app
    window_end = _WINDOW_REFERENCE
    window_start = window_end - timedelta(days=1)
    previous_window_end = window_start
    previous_window_start = previous_window_end - timedelta(days=1)

    with metrics_pg_conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) FROM "AnonymousMetrics"')
        existing_count = cur.fetchone()[0]
    assert existing_count == 0

    with app.app_context():
        category_list, last_flush_at = summary(
            window_start=window_start,
            window_end=window_end,
            previous_window_start=previous_window_start,
            previous_window_end=previous_window_end,
        )

    assert category_list == []
    assert last_flush_at is None


def test_query_service_join_includes_description_for_every_event(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
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

    for offset, event_name in enumerate(
        (EventName.UTUB_OPENED, EventName.API_HIT, EventName.URL_ACCESSED)
    ):
        _insert_metric_row(
            metrics_pg_conn,
            event_name=event_name,
            bucket_start=inside + timedelta(hours=offset),
            count=offset + 1,
        )

    prev_start, prev_end = previous_window(window_start, window_end)
    with app.app_context():
        rows = top_events(
            window_start=window_start,
            window_end=window_end,
            previous_window_start=prev_start,
            previous_window_end=prev_end,
            category=None,
            limit=10,
        )

    assert len(rows) == 3
    for row in rows:
        assert row.description != ""
        assert row.description is not None
