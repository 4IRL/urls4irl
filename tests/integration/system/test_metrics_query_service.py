from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Generator

import pytest
from flask import Flask

from backend.extensions.metrics.buckets import previous_window
from backend.metrics.events import (
    EVENT_CATEGORY,
    EVENT_DESCRIPTIONS,
    DeviceType,
    EventCategory,
    EventName,
)
from backend.metrics.latency import LatencyMetricName
from backend.metrics.query_service import (
    grouped_count_by,
    grouped_count_scalar,
    latency_percentiles,
    latency_timeseries,
    summary,
    timeseries,
    top_events,
)
from backend.metrics.resources import Resource
from backend.utils.strings.metrics_strs import METRICS_REDIS
from tests.integration.system.metrics_helpers import (
    build_pg_conn,
    truncate_latency_rollup_tables,
    truncate_latency_tables,
    truncate_metrics_tables,
)

pytestmark = pytest.mark.cli


_WINDOW_REFERENCE: datetime = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


def _truncate_metrics_and_registry(pg_conn: Any) -> None:
    truncate_metrics_tables(pg_conn)
    truncate_latency_tables(pg_conn)
    truncate_latency_rollup_tables(pg_conn)
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


_LATENCY_METRIC = LatencyMetricName.API_REQUEST_DURATION


def _insert_latency_row(
    pg_conn: Any,
    *,
    observed_at: datetime,
    duration_ms: float,
    endpoint: str | None = None,
    method: str | None = None,
    dimensions: dict | None = None,
    metric_name: LatencyMetricName = _LATENCY_METRIC,
) -> None:
    """Seed one AnonymousLatencySamples row via psycopg2.

    Mirrors `_insert_metric_row` but targets the raw-sample latency table.
    `AnonymousLatencySamples` has no FK to `EventRegistry`, so (unlike the
    metrics helper) no registry row is required. The double-quoted identifiers
    match the SQLAlchemy `__tablename__`/`name=` values exactly; PostgreSQL
    folds unquoted identifiers to lowercase.
    """
    dims = dimensions if dimensions is not None else {}
    with pg_conn.cursor() as cur:
        cur.execute(
            'INSERT INTO "AnonymousLatencySamples"'
            ' ("metricName", "endpoint", "method", "observedAt",'
            ' "durationMs", "dimensions")'
            " VALUES (%s, %s, %s, %s, %s, %s)",
            (
                metric_name.value,
                endpoint,
                method,
                observed_at,
                duration_ms,
                json.dumps(dims),
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
    assert top_row.api_endpoint == "utubs.get_single_utub"
    assert top_row.description == "Retrieve data for a single UTub"
    assert top_row.event_name.startswith("GET ")
    assert top_row.event_name != "GET utubs.get_single_utub"
    assert second_row.total_count == 2
    assert second_row.api_endpoint == "splash.splash_page"
    assert second_row.description == ""


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
    assert rows[0].api_endpoint == "utubs.get_single_utub"
    assert rows[0].description == "Retrieve data for a single UTub"
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
    GIVEN two UTUB_OPENED rows in two distinct hour buckets within a 1-day
        window aligned on the hour
    WHEN timeseries is called with resolution="hour"
    THEN 24 chronologically-ordered buckets are returned (one per hour) with
        the two seeded buckets carrying counts 3 and 4 and the remaining 22
        zero-filled.
    AND when resolution="day", the buckets collapse to one row summing 7.
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

    assert len(hourly) == 24
    bucket_starts = [row.bucket for row in hourly]
    assert bucket_starts == sorted(bucket_starts)
    nonzero = {row.bucket: row.count for row in hourly if row.count != 0}
    assert nonzero == {first_bucket: 3, second_bucket: 4}

    # The day window spans across a calendar-day boundary at 00:00 UTC, so the
    # zero-fill emits two day buckets: the one containing the seeded rows
    # (count=7) and the trailing day with no data (count=0).
    assert len(daily) == 2
    daily_by_bucket = {row.bucket: row.count for row in daily}
    seeded_day = window_start.replace(hour=0, minute=0, second=0, microsecond=0)
    trailing_day = seeded_day + timedelta(days=1)
    assert daily_by_bucket[seeded_day] == 7
    assert daily_by_bucket[trailing_day] == 0


def test_timeseries_zero_fills_when_no_rows_in_window(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN no rows exist for the event in a 1-day window
    WHEN timeseries is called with resolution="hour"
    THEN one zero-count bucket per hour is returned (24 total), so the
        admin chart renders a flat-zero baseline instead of a single
        lonely datapoint.
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

    assert len(rows) == 24
    assert all(row.count == 0 for row in rows)
    bucket_starts = [row.bucket for row in rows]
    assert bucket_starts == sorted(bucket_starts)


def test_timeseries_zero_fills_with_unaligned_window_start(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN a window whose `window_start` lands mid-hour (the common case for
        relative `window="day"` queries — `now` is rarely hour-aligned)
    WHEN timeseries is called with resolution="hour"
    THEN the first emitted bucket is `truncate('hour', window_start)` — even
        though its start is strictly before `window_start` — so the result
        covers every aligned interval that overlaps the queried range. Skipping
        the leading partial bucket would emit a zero where data could land in
        coarser-resolution queries (`date_trunc('day', ...)`).
    """
    app = metrics_enabled_runner_app
    window_end = _WINDOW_REFERENCE  # 12:00:00 (aligned)
    # Pin window_start to 11:37 the previous day so the leading aligned bucket
    # (11:00) starts strictly before window_start.
    window_start = (window_end - timedelta(days=1)).replace(minute=37)

    with app.app_context():
        rows = timeseries(
            event_name=EventName.UTUB_OPENED,
            window_start=window_start,
            window_end=window_end,
            resolution="hour",
        )

    # 24 buckets: the leading partial bucket (truncated hour containing
    # window_start) through to the last full hour bucket before window_end.
    assert len(rows) == 24
    expected_first = window_start.replace(minute=0)
    assert rows[0].bucket == expected_first
    assert rows[-1].bucket < window_end
    assert rows[-1].bucket + timedelta(hours=1) == window_end


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

    assert len(rows) == 24
    nonzero = [row for row in rows if row.count != 0]
    assert len(nonzero) == 1
    assert nonzero[0].count == 4
    assert nonzero[0].bucket == inside


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
        summary_result = summary(
            window_start=window_start,
            window_end=window_end,
            previous_window_start=previous_window_start,
            previous_window_end=previous_window_end,
        )

    api_row = next(row for row in summary_result.by_category if row.category == "api")
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
        summary_result = summary(
            window_start=window_start,
            window_end=window_end,
            previous_window_start=previous_window_start,
            previous_window_end=previous_window_end,
        )

    assert summary_result.by_category == []


def test_summary_includes_last_event_at_when_metrics_exist(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN a single seeded AnonymousMetrics row with a known bucket_start
    WHEN summary(...) is called
    THEN `last_event_at` equals that bucket_start exactly, so the dashboard's
        activity badge can render `now - last_event_at` without an additional
        round trip.
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
        summary_result = summary(
            window_start=window_start,
            window_end=window_end,
            previous_window_start=previous_window_start,
            previous_window_end=previous_window_end,
        )

    assert summary_result.last_event_at == seeded_bucket_start


def test_summary_last_event_at_is_null_when_no_metrics(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN an empty AnonymousMetrics table (assert-before-state)
    WHEN summary(...) is called
    THEN `last_event_at` is None — the badge falls back to its empty-state
        text rather than rendering a stale timestamp.
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
        summary_result = summary(
            window_start=window_start,
            window_end=window_end,
            previous_window_start=previous_window_start,
            previous_window_end=previous_window_end,
        )

    assert summary_result.by_category == []
    assert summary_result.last_event_at is None


def test_summary_last_flush_at_reads_sentinel_from_redis(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN a `metrics:flush:last_success_epoch` sentinel set in Redis at a known
        Unix epoch
    WHEN summary(...) is called
    THEN `last_flush_at` is the UTC-aware datetime parsed from that epoch,
        independent of whether AnonymousMetrics has any rows.
    """
    app = metrics_enabled_runner_app
    window_end = _WINDOW_REFERENCE
    window_start = window_end - timedelta(days=1)
    previous_window_end = window_start
    previous_window_start = previous_window_end - timedelta(days=1)

    expected_epoch = 1_733_606_400  # 2024-12-07 20:00:00 UTC
    expected_datetime = datetime.fromtimestamp(expected_epoch, tz=timezone.utc)

    writer = app.extensions["metrics_writer"]
    writer._redis.set(METRICS_REDIS.FLUSH_LAST_SUCCESS_KEY, str(expected_epoch))
    try:
        with app.app_context():
            summary_result = summary(
                window_start=window_start,
                window_end=window_end,
                previous_window_start=previous_window_start,
                previous_window_end=previous_window_end,
            )
    finally:
        writer._redis.delete(METRICS_REDIS.FLUSH_LAST_SUCCESS_KEY)

    assert summary_result.last_flush_at == expected_datetime


def test_summary_last_flush_at_is_null_when_sentinel_absent(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN the `metrics:flush:last_success_epoch` sentinel is unset in Redis
    WHEN summary(...) is called
    THEN `last_flush_at` is None — the badge can fall back to an empty state
        rather than misreporting a stale timestamp.
    """
    app = metrics_enabled_runner_app
    window_end = _WINDOW_REFERENCE
    window_start = window_end - timedelta(days=1)
    previous_window_end = window_start
    previous_window_start = previous_window_end - timedelta(days=1)

    writer = app.extensions["metrics_writer"]
    writer._redis.delete(METRICS_REDIS.FLUSH_LAST_SUCCESS_KEY)

    with app.app_context():
        summary_result = summary(
            window_start=window_start,
            window_end=window_end,
            previous_window_start=previous_window_start,
            previous_window_end=previous_window_end,
        )

    assert summary_result.last_flush_at is None


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


def test_top_events_resource_filter_ui_utub_only(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN one UI UTub event, one UI URL event, and one UI Tag event in the window
    WHEN top_events is called with category=UI and resource=UTUB
    THEN only the UTub event is returned; URL and Tag rows are filtered out.
    """
    app = metrics_enabled_runner_app
    window_end = _WINDOW_REFERENCE
    window_start = window_end - timedelta(days=1)
    inside = window_start + timedelta(hours=1)

    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.UI_UTUB_SELECT,
        bucket_start=inside,
        count=5,
    )
    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.UI_URL_ACCESS,
        bucket_start=inside,
        count=10,
    )
    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.UI_TAG_APPLY,
        bucket_start=inside,
        count=15,
    )

    prev_start, prev_end = previous_window(window_start, window_end)
    with app.app_context():
        rows = top_events(
            window_start=window_start,
            window_end=window_end,
            previous_window_start=prev_start,
            previous_window_end=prev_end,
            category=EventCategory.UI,
            resource=Resource.UTUB,
            limit=10,
        )

    assert len(rows) == 1
    assert rows[0].event_name == EventName.UI_UTUB_SELECT.value


def test_top_events_resource_filter_domain_tag_only(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN a Domain UTub event, a Domain URL event, and two Domain Tag events
    WHEN top_events is called with category=DOMAIN and resource=TAG
    THEN only the two Tag rows are returned, sorted by count desc.
    """
    app = metrics_enabled_runner_app
    window_end = _WINDOW_REFERENCE
    window_start = window_end - timedelta(days=1)
    inside = window_start + timedelta(hours=1)

    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.UTUB_CREATED,
        bucket_start=inside,
        count=100,
    )
    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.URL_ACCESSED,
        bucket_start=inside,
        count=200,
    )
    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.TAG_APPLIED,
        bucket_start=inside,
        count=7,
    )
    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.TAG_REMOVED,
        bucket_start=inside,
        count=3,
    )

    prev_start, prev_end = previous_window(window_start, window_end)
    with app.app_context():
        rows = top_events(
            window_start=window_start,
            window_end=window_end,
            previous_window_start=prev_start,
            previous_window_end=prev_end,
            category=EventCategory.DOMAIN,
            resource=Resource.TAG,
            limit=10,
        )

    returned_names = [row.event_name for row in rows]
    assert returned_names == [
        EventName.TAG_APPLIED.value,
        EventName.TAG_REMOVED.value,
    ]


def test_top_events_resource_filter_api_route_prefix(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN API hits across utubs.*, urls.*, and utub_tags.* Flask endpoints
    WHEN top_events is called with category=API and resource=UTUB
    THEN only rows with endpoint LIKE 'utubs.%' are returned.
    """
    app = metrics_enabled_runner_app
    window_end = _WINDOW_REFERENCE
    window_start = window_end - timedelta(days=1)
    inside = window_start + timedelta(hours=8)

    # Production writes Flask endpoint names (e.g. `utubs.get_single_utub`)
    # via `request.endpoint` in `extensions/metrics/middleware.py`, not URL
    # paths. The resource filter matches against that prefix.
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
        count=12,
    )
    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.API_HIT,
        bucket_start=inside,
        endpoint="urls.create_url",
        method="POST",
        status_code=201,
        dimensions={
            "endpoint": "urls.create_url",
            "method": "POST",
            "status_code": 201,
        },
        count=99,
    )
    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.API_HIT,
        bucket_start=inside,
        endpoint="utub_tags.delete_utub_tag",
        method="DELETE",
        status_code=204,
        dimensions={
            "endpoint": "utub_tags.delete_utub_tag",
            "method": "DELETE",
            "status_code": 204,
        },
        count=44,
    )

    prev_start, prev_end = previous_window(window_start, window_end)
    with app.app_context():
        rows = top_events(
            window_start=window_start,
            window_end=window_end,
            previous_window_start=prev_start,
            previous_window_end=prev_end,
            category=EventCategory.API,
            resource=Resource.UTUB,
            limit=10,
        )

    assert len(rows) == 1
    # The event_name is built from `endpoint_metadata[endpoint].url_pattern`
    # — `utubs.get_single_utub` resolves to `/utubs/<int:utub_id>` from the
    # registered Flask url_map.
    assert rows[0].api_endpoint == "utubs.get_single_utub"
    assert rows[0].event_name.startswith("GET ")
    assert "/utubs/" in rows[0].event_name


def test_top_events_resource_other_excludes_known_prefixes(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN one API hit to a known prefix (`utubs.*`) AND one to an unknown
        blueprint (`system.health`)
    WHEN top_events is called with category=API and resource=OTHER
    THEN only the unknown-blueprint row appears; the known-prefix row is filtered.
    """
    app = metrics_enabled_runner_app
    window_end = _WINDOW_REFERENCE
    window_start = window_end - timedelta(days=1)
    inside = window_start + timedelta(hours=1)

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
        count=50,
    )
    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.API_HIT,
        bucket_start=inside,
        endpoint="system.health",
        method="GET",
        status_code=200,
        dimensions={
            "endpoint": "system.health",
            "method": "GET",
            "status_code": 200,
        },
        count=3,
    )

    prev_start, prev_end = previous_window(window_start, window_end)
    with app.app_context():
        rows = top_events(
            window_start=window_start,
            window_end=window_end,
            previous_window_start=prev_start,
            previous_window_end=prev_end,
            category=EventCategory.API,
            resource=Resource.OTHER,
            limit=10,
        )

    assert len(rows) == 1
    assert rows[0].api_endpoint == "system.health"


def test_top_events_resource_filter_runs_before_limit_truncation(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN twelve high-count UTub events and twelve low-count Tag events
    WHEN top_events is called with category=UI, resource=TAG, limit=10
    THEN ten Tag rows are returned — NOT the global top-10 (which would be
    dominated by the higher-count UTub events).
    """
    app = metrics_enabled_runner_app
    window_end = _WINDOW_REFERENCE
    window_start = window_end - timedelta(days=1)
    inside = window_start + timedelta(hours=1)

    utub_events = [
        EventName.UI_UTUB_SELECT,
        EventName.UI_UTUB_CREATE_OPEN,
        EventName.UI_UTUB_DELETE_OPEN,
        EventName.UI_UTUB_DELETE_CONFIRM,
        EventName.UI_UTUB_DELETE_CANCEL,
        EventName.UI_UTUB_NAME_EDIT_OPEN,
        EventName.UI_UTUB_DESC_EDIT_OPEN,
    ]
    tag_events = [
        EventName.UI_TAG_APPLY,
        EventName.UI_TAG_REMOVE,
        EventName.UI_TAG_CREATE_OPEN,
        EventName.UI_TAG_DELETE_OPEN,
        EventName.UI_TAG_DELETE_CONFIRM,
        EventName.UI_TAG_DELETE_CANCEL,
        EventName.UI_TAG_FILTER_TOGGLE,
    ]
    for utub_event in utub_events:
        _insert_metric_row(
            metrics_pg_conn,
            event_name=utub_event,
            bucket_start=inside,
            count=1000,
        )
    for tag_event in tag_events:
        _insert_metric_row(
            metrics_pg_conn,
            event_name=tag_event,
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
            category=EventCategory.UI,
            resource=Resource.TAG,
            limit=10,
        )

    assert all(row.event_name.startswith("ui_tag_") for row in rows)
    assert len(rows) == len(tag_events)


@pytest.mark.parametrize(
    "filter_device_type, other_device_type",
    [
        (DeviceType.MOBILE, DeviceType.DESKTOP),
        (DeviceType.DESKTOP, DeviceType.MOBILE),
    ],
    ids=["mobile", "desktop"],
)
def test_top_events_device_type_filter_returns_only_matching_rows(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
    filter_device_type: DeviceType,
    other_device_type: DeviceType,
) -> None:
    """
    GIVEN two UI events tagged with `filter_device_type` and one tagged with
        the opposite device_type
    WHEN top_events is called with category=UI and device_type=filter_device_type
    THEN only the two matching rows are returned; the opposite-device row is
        excluded.
    """
    app = metrics_enabled_runner_app
    window_end = _WINDOW_REFERENCE
    window_start = window_end - timedelta(days=1)
    inside = window_start + timedelta(hours=1)

    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.UI_UTUB_SELECT,
        bucket_start=inside,
        dimensions={"device_type": int(filter_device_type)},
        count=5,
    )
    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.UI_URL_ACCESS,
        bucket_start=inside,
        dimensions={"device_type": int(filter_device_type)},
        count=10,
    )
    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.UI_TAG_APPLY,
        bucket_start=inside,
        dimensions={"device_type": int(other_device_type)},
        count=15,
    )

    prev_start, prev_end = previous_window(window_start, window_end)
    with app.app_context():
        rows = top_events(
            window_start=window_start,
            window_end=window_end,
            previous_window_start=prev_start,
            previous_window_end=prev_end,
            category=EventCategory.UI,
            limit=10,
            device_type=int(filter_device_type),
        )

    returned_names = {row.event_name for row in rows}
    assert returned_names == {
        EventName.UI_UTUB_SELECT.value,
        EventName.UI_URL_ACCESS.value,
    }


def test_top_events_device_type_none_returns_all_rows(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN UI rows with mixed device_type values (mobile + desktop)
    WHEN top_events is called with device_type=None
    THEN all rows are returned regardless of device_type.
    """
    app = metrics_enabled_runner_app
    window_end = _WINDOW_REFERENCE
    window_start = window_end - timedelta(days=1)
    inside = window_start + timedelta(hours=1)

    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.UI_UTUB_SELECT,
        bucket_start=inside,
        dimensions={"device_type": int(DeviceType.MOBILE)},
        count=5,
    )
    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.UI_URL_ACCESS,
        bucket_start=inside,
        dimensions={"device_type": int(DeviceType.DESKTOP)},
        count=10,
    )

    prev_start, prev_end = previous_window(window_start, window_end)
    with app.app_context():
        rows = top_events(
            window_start=window_start,
            window_end=window_end,
            previous_window_start=prev_start,
            previous_window_end=prev_end,
            category=EventCategory.UI,
            limit=10,
            device_type=None,
        )

    returned_names = {row.event_name for row in rows}
    assert returned_names == {
        EventName.UI_UTUB_SELECT.value,
        EventName.UI_URL_ACCESS.value,
    }


def test_top_events_device_type_with_api_category(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN three api_hit rows: two with device_type=MOBILE and one with DESKTOP
    WHEN top_events is called with category=API and device_type=MOBILE
    THEN only the two mobile rows are returned.
    """
    app = metrics_enabled_runner_app
    window_end = _WINDOW_REFERENCE
    window_start = window_end - timedelta(days=1)
    inside = window_start + timedelta(hours=1)

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
            "device_type": int(DeviceType.MOBILE),
        },
        count=4,
    )
    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.API_HIT,
        bucket_start=inside,
        endpoint="urls.create_url",
        method="POST",
        status_code=201,
        dimensions={
            "endpoint": "urls.create_url",
            "method": "POST",
            "status_code": 201,
            "device_type": int(DeviceType.MOBILE),
        },
        count=8,
    )
    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.API_HIT,
        bucket_start=inside,
        endpoint="utub_tags.delete_utub_tag",
        method="DELETE",
        status_code=204,
        dimensions={
            "endpoint": "utub_tags.delete_utub_tag",
            "method": "DELETE",
            "status_code": 204,
            "device_type": int(DeviceType.DESKTOP),
        },
        count=99,
    )

    prev_start, prev_end = previous_window(window_start, window_end)
    with app.app_context():
        rows = top_events(
            window_start=window_start,
            window_end=window_end,
            previous_window_start=prev_start,
            previous_window_end=prev_end,
            category=EventCategory.API,
            limit=10,
            device_type=int(DeviceType.MOBILE),
        )

    returned_endpoints = {row.api_endpoint for row in rows}
    assert returned_endpoints == {"utubs.get_single_utub", "urls.create_url"}


def test_top_events_device_type_with_domain_category(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN two UTUB_OPENED rows with device_type=MOBILE and one with DESKTOP
    WHEN top_events is called with category=DOMAIN and device_type=MOBILE
    THEN only the two mobile rows are aggregated; the desktop row is excluded.

    Note: identical (event_name, bucket, dimensions) rows are summed by
    SQLAlchemy GROUP BY into a single returned row; the assertion checks the
    summed total_count (2 mobile rows of count=5 each = 10).
    """
    app = metrics_enabled_runner_app
    window_end = _WINDOW_REFERENCE
    window_start = window_end - timedelta(days=1)
    inside_first = window_start + timedelta(hours=1)
    inside_second = window_start + timedelta(hours=2)
    inside_third = window_start + timedelta(hours=3)

    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.UTUB_OPENED,
        bucket_start=inside_first,
        dimensions={"device_type": int(DeviceType.MOBILE)},
        count=5,
    )
    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.UTUB_OPENED,
        bucket_start=inside_second,
        dimensions={"device_type": int(DeviceType.MOBILE)},
        count=5,
    )
    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.UTUB_OPENED,
        bucket_start=inside_third,
        dimensions={"device_type": int(DeviceType.DESKTOP)},
        count=99,
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
            device_type=int(DeviceType.MOBILE),
        )

    assert len(rows) == 1
    assert rows[0].event_name == EventName.UTUB_OPENED.value
    assert rows[0].total_count == 10


def test_top_events_device_type_excludes_rows_without_dimension_key(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN one UI row tagged device_type=MOBILE and one row without the key
    WHEN top_events is called with device_type=MOBILE
    THEN only the explicitly-tagged row is returned; the untagged row
        (NULL JSONB key) is correctly excluded.

    This documents the pre-PR backfill exclusion behavior: rows written
    before Step 2 of the device-type-filter plan landed carry {} dimensions
    and silently disappear from filtered results — matching the resource
    filter's backfill semantics.
    """
    app = metrics_enabled_runner_app
    window_end = _WINDOW_REFERENCE
    window_start = window_end - timedelta(days=1)
    inside = window_start + timedelta(hours=1)

    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.UI_UTUB_SELECT,
        bucket_start=inside,
        dimensions={"device_type": int(DeviceType.MOBILE)},
        count=5,
    )
    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.UI_URL_ACCESS,
        bucket_start=inside,
        dimensions={},
        count=10,
    )

    prev_start, prev_end = previous_window(window_start, window_end)
    with app.app_context():
        rows = top_events(
            window_start=window_start,
            window_end=window_end,
            previous_window_start=prev_start,
            previous_window_end=prev_end,
            category=EventCategory.UI,
            limit=10,
            device_type=int(DeviceType.MOBILE),
        )

    assert len(rows) == 1
    assert rows[0].event_name == EventName.UI_UTUB_SELECT.value


@pytest.mark.parametrize(
    "filter_device_type, expected_count",
    [
        (DeviceType.MOBILE, 4),
        (DeviceType.DESKTOP, 10),
    ],
    ids=["mobile", "desktop"],
)
def test_timeseries_filters_by_device_type(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
    filter_device_type: DeviceType,
    expected_count: int,
) -> None:
    """
    GIVEN two UI_UTUB_SELECT rows in the same bucket — one MOBILE (count=4),
        one DESKTOP (count=10)
    WHEN timeseries is called with device_type=filter_device_type
    THEN only the matching row's count is summed; the opposite-device row is
        excluded.
    """
    app = metrics_enabled_runner_app
    window_end = _WINDOW_REFERENCE
    window_start = window_end - timedelta(days=1)
    inside = window_start + timedelta(hours=6)

    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.UI_UTUB_SELECT,
        bucket_start=inside,
        dimensions={"device_type": int(DeviceType.MOBILE)},
        count=4,
    )
    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.UI_UTUB_SELECT,
        bucket_start=inside,
        dimensions={"device_type": int(DeviceType.DESKTOP)},
        count=10,
    )

    with app.app_context():
        rows = timeseries(
            event_name=EventName.UI_UTUB_SELECT,
            window_start=window_start,
            window_end=window_end,
            resolution="hour",
            device_type=int(filter_device_type),
        )

    assert len(rows) == 24
    nonzero = [row for row in rows if row.count != 0]
    assert len(nonzero) == 1
    assert nonzero[0].count == expected_count
    assert nonzero[0].bucket == inside


# --------------------------- grouped_counts --------------------------------


def _count_rows_for_event(pg_conn: Any, event_name: EventName) -> int:
    """Return the raw COUNT(*) of AnonymousMetrics rows for an event.

    Used for assert-before-state checks proving the window starts empty before
    the rows under test are seeded.
    """
    with pg_conn.cursor() as cur:
        cur.execute(
            'SELECT COUNT(*) FROM "AnonymousMetrics" WHERE "eventName" = %s',
            (event_name.value,),
        )
        return cur.fetchone()[0]


def test_grouped_counts_filters_and_groups_by_dim(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN several UI_FORM_CANCEL rows across (form, trigger) combinations
    WHEN grouped_counts is called filtering form=utub_create grouped by trigger
    THEN it returns a list of (trigger, count) tuples summed across buckets,
        excluding non-matching form values.
    """
    app = metrics_enabled_runner_app
    window_end = _WINDOW_REFERENCE
    window_start = window_end - timedelta(days=1)
    inside = window_start + timedelta(hours=1)

    assert _count_rows_for_event(metrics_pg_conn, EventName.UI_FORM_CANCEL) == 0

    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.UI_FORM_CANCEL,
        bucket_start=inside,
        dimensions={
            "form": "utub_create",
            "trigger": "escape_key",
            "device_type": int(DeviceType.DESKTOP),
        },
        count=3,
    )
    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.UI_FORM_CANCEL,
        bucket_start=inside + timedelta(hours=2),
        dimensions={
            "form": "utub_create",
            "trigger": "escape_key",
            "device_type": int(DeviceType.DESKTOP),
        },
        count=4,
    )
    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.UI_FORM_CANCEL,
        bucket_start=inside + timedelta(hours=1),
        dimensions={
            "form": "utub_create",
            "trigger": "cancel_button",
            "device_type": int(DeviceType.DESKTOP),
        },
        count=2,
    )
    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.UI_FORM_CANCEL,
        bucket_start=inside,
        dimensions={
            "form": "url_create",
            "trigger": "escape_key",
            "device_type": int(DeviceType.DESKTOP),
        },
        count=99,
    )

    with app.app_context():
        result = grouped_count_by(
            event_name=EventName.UI_FORM_CANCEL,
            window_start=window_start,
            window_end=window_end,
            dim_filter=[("form", "utub_create")],
            group_by="trigger",
        )

    assert isinstance(result, list)
    for entry in result:
        assert isinstance(entry, tuple)
        assert isinstance(entry[0], str)
        assert isinstance(entry[1], int)
    result_dict = dict(result)
    assert result_dict == {"escape_key": 7, "cancel_button": 2}
    # Descending-by-count ordering.
    assert result[0] == ("escape_key", 7)


def test_grouped_counts_no_filter_no_group_by(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN several rows for a single event in the window
    WHEN grouped_counts is called with no dim_filter and no group_by
    THEN it returns the summed total as a scalar int (not a list).
    """
    app = metrics_enabled_runner_app
    window_end = _WINDOW_REFERENCE
    window_start = window_end - timedelta(days=1)
    inside = window_start + timedelta(hours=1)

    assert _count_rows_for_event(metrics_pg_conn, EventName.UTUB_OPENED) == 0

    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.UTUB_OPENED,
        bucket_start=inside,
        count=5,
    )
    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.UTUB_OPENED,
        bucket_start=inside + timedelta(hours=1),
        count=7,
    )

    with app.app_context():
        result = grouped_count_scalar(
            event_name=EventName.UTUB_OPENED,
            window_start=window_start,
            window_end=window_end,
        )

    assert isinstance(result, int)
    assert result == 12


def test_grouped_counts_group_by_none_returns_int(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN zero matching rows for an event in the window
    WHEN grouped_count_scalar is called
    THEN it returns the integer 0 (not an empty list, not None).
    """
    app = metrics_enabled_runner_app
    window_end = _WINDOW_REFERENCE
    window_start = window_end - timedelta(days=1)

    assert _count_rows_for_event(metrics_pg_conn, EventName.UTUB_OPENED) == 0

    with app.app_context():
        result = grouped_count_scalar(
            event_name=EventName.UTUB_OPENED,
            window_start=window_start,
            window_end=window_end,
        )

    assert result == 0
    assert isinstance(result, int)


def test_grouped_counts_group_by_set_returns_list_of_tuples(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN rows for an event with varying trigger dim values
    WHEN grouped_counts is called with group_by="trigger"
    THEN the return is a list whose elements are (str, int) tuples.
    """
    app = metrics_enabled_runner_app
    window_end = _WINDOW_REFERENCE
    window_start = window_end - timedelta(days=1)
    inside = window_start + timedelta(hours=1)

    assert _count_rows_for_event(metrics_pg_conn, EventName.UI_FORM_CANCEL) == 0

    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.UI_FORM_CANCEL,
        bucket_start=inside,
        dimensions={
            "form": "utub_create",
            "trigger": "escape_key",
            "device_type": int(DeviceType.DESKTOP),
        },
        count=1,
    )

    with app.app_context():
        result = grouped_count_by(
            event_name=EventName.UI_FORM_CANCEL,
            window_start=window_start,
            window_end=window_end,
            group_by="trigger",
        )

    assert isinstance(result, list)
    for entry in result:
        assert isinstance(entry, tuple)
        assert isinstance(entry[0], str)
        assert isinstance(entry[1], int)
    assert result == [("escape_key", 1)]


def test_grouped_counts_invalid_filter_key_nonapi_event_raises_value_error(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN a non-API event (JSONB dimension path)
    WHEN grouped_count_scalar is called with an unknown dim key in dim_filter
    THEN ValueError is raised.
    """
    app = metrics_enabled_runner_app
    window_end = _WINDOW_REFERENCE
    window_start = window_end - timedelta(days=1)

    with app.app_context():
        with pytest.raises(ValueError):
            grouped_count_scalar(
                event_name=EventName.UI_FORM_CANCEL,
                window_start=window_start,
                window_end=window_end,
                dim_filter=[("nonexistent_dim", "value")],
            )


def test_grouped_counts_invalid_filter_key_api_event_raises_value_error(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN an API-category event (flat-column path)
    WHEN grouped_count_scalar is called with a key outside {endpoint, method,
        status_code} (e.g. device_type, which is not a flat column)
    THEN ValueError is raised.
    """
    app = metrics_enabled_runner_app
    window_end = _WINDOW_REFERENCE
    window_start = window_end - timedelta(days=1)

    with app.app_context():
        with pytest.raises(ValueError):
            grouped_count_scalar(
                event_name=EventName.API_HIT,
                window_start=window_start,
                window_end=window_end,
                dim_filter=[("device_type", "2")],
            )


def test_grouped_counts_invalid_group_by_key_raises_value_error(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN both a non-API event (JSONB dimension path) and an API-category event
        (flat-column path)
    WHEN grouped_count_by is called with a `group_by` key that is not a valid
        dimension on the event
    THEN ValueError is raised on BOTH paths — the unknown group_by key is
        rejected by `_raise_on_unknown_keys` before any query runs.
    """
    app = metrics_enabled_runner_app
    window_end = _WINDOW_REFERENCE
    window_start = window_end - timedelta(days=1)

    with app.app_context():
        with pytest.raises(ValueError):
            grouped_count_by(
                event_name=EventName.UI_FORM_CANCEL,
                window_start=window_start,
                window_end=window_end,
                dim_filter=[],
                group_by="nonexistent",
            )
        with pytest.raises(ValueError):
            grouped_count_by(
                event_name=EventName.API_HIT,
                window_start=window_start,
                window_end=window_end,
                dim_filter=[],
                group_by="nonexistent",
            )


def test_grouped_counts_api_category_filters_by_flat_columns(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN API_HIT rows with distinct endpoint/method/status_code combos
    WHEN grouped_counts filters by flat columns (endpoint+method, then
        status_code)
    THEN only rows matching those flat-column values are counted, and the
        status_code integer cast works.
    """
    app = metrics_enabled_runner_app
    window_end = _WINDOW_REFERENCE
    window_start = window_end - timedelta(days=1)
    inside = window_start + timedelta(hours=1)

    assert _count_rows_for_event(metrics_pg_conn, EventName.API_HIT) == 0

    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.API_HIT,
        bucket_start=inside,
        endpoint="urls.create_url",
        method="POST",
        status_code=200,
        count=5,
    )
    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.API_HIT,
        bucket_start=inside + timedelta(hours=1),
        endpoint="urls.create_url",
        method="POST",
        status_code=400,
        count=3,
    )
    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.API_HIT,
        bucket_start=inside + timedelta(hours=2),
        endpoint="utubs.get_single_utub",
        method="GET",
        status_code=200,
        count=11,
    )

    with app.app_context():
        endpoint_method_total = grouped_count_scalar(
            event_name=EventName.API_HIT,
            window_start=window_start,
            window_end=window_end,
            dim_filter=[("endpoint", "urls.create_url"), ("method", "POST")],
        )
        status_code_total = grouped_count_scalar(
            event_name=EventName.API_HIT,
            window_start=window_start,
            window_end=window_end,
            dim_filter=[
                ("endpoint", "urls.create_url"),
                ("method", "POST"),
                ("status_code", "200"),
            ],
        )

    assert endpoint_method_total == 8
    assert status_code_total == 5


def test_grouped_counts_status_code_nonnumeric_filter_value_raises_value_error(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN an API_HIT query with a non-numeric status_code filter value
    WHEN grouped_count_scalar is called
    THEN ValueError is raised with the controlled status_code message (not the
        raw int() error message that would leak the input).
    """
    app = metrics_enabled_runner_app
    window_end = _WINDOW_REFERENCE
    window_start = window_end - timedelta(days=1)

    with app.app_context():
        with pytest.raises(ValueError) as exc_info:
            grouped_count_scalar(
                event_name=EventName.API_HIT,
                window_start=window_start,
                window_end=window_end,
                dim_filter=[("status_code", "abc")],
            )

    assert "filter value for status_code must be an integer" in str(exc_info.value)


def test_grouped_counts_device_type_nonnumeric_filter_value_raises_value_error(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN a non-API event filtered on device_type with a non-numeric value
    WHEN grouped_count_scalar is called
    THEN ValueError is raised with the controlled device_type message (not the
        raw int() error message that would leak the input).
    """
    app = metrics_enabled_runner_app
    window_end = _WINDOW_REFERENCE
    window_start = window_end - timedelta(days=1)

    with app.app_context():
        with pytest.raises(ValueError) as exc_info:
            grouped_count_scalar(
                event_name=EventName.UI_FORM_CANCEL,
                window_start=window_start,
                window_end=window_end,
                dim_filter=[("device_type", "phone")],
            )

    assert "filter value for device_type must be an integer" in str(exc_info.value)


# ----------------------------- latency ------------------------------------


_LATENCY_ENDPOINT_FAST = "utubs.get_utub"
_LATENCY_ENDPOINT_SLOW = "urls.add_url"


def _count_latency_rows(pg_conn: Any) -> int:
    """Return the raw COUNT(*) of AnonymousLatencySamples rows.

    Used for assert-before-state checks proving the table starts empty before
    the samples under test are seeded.
    """
    with pg_conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) FROM "AnonymousLatencySamples"')
        return cur.fetchone()[0]


def _count_latency_rollup_rows(pg_conn: Any) -> int:
    """Return the COUNT(*) of AnonymousLatencyDailyRollups rows.

    Used for assert-before-state checks proving the rollup table starts empty
    before the rows under test are seeded.
    """
    with pg_conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) FROM "AnonymousLatencyDailyRollups"')
        return cur.fetchone()[0]


def _insert_latency_rollup_row(
    pg_conn: Any,
    *,
    rollup_date: date,
    p50_ms: float,
    p95_ms: float,
    p99_ms: float,
    sample_count: int,
    endpoint: str = _LATENCY_ENDPOINT_FAST,
    method: str = "GET",
    metric_name: LatencyMetricName = _LATENCY_METRIC,
) -> None:
    """Seed one AnonymousLatencyDailyRollups row via psycopg2.

    Mirrors `_insert_latency_row` but targets the daily rollup table — the
    source for windows beyond the raw-sample retention horizon. Stores the
    precomputed daily percentiles plus the day's `sampleCount`.
    """
    with pg_conn.cursor() as cur:
        cur.execute(
            'INSERT INTO "AnonymousLatencyDailyRollups"'
            ' ("metricName", "endpoint", "method", "rollupDate",'
            ' "p50Ms", "p95Ms", "p99Ms", "sampleCount", "dimensions")'
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                metric_name.value,
                endpoint,
                method,
                rollup_date,
                p50_ms,
                p95_ms,
                p99_ms,
                sample_count,
                json.dumps({}),
            ),
        )
    pg_conn.commit()


def test_latency_percentiles_empty_window_returns_empty_list(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN no AnonymousLatencySamples rows exist (assert-before-state)
    WHEN latency_percentiles is called over the window
    THEN the result is [] — the dashboard table renders its empty state.
    """
    app = metrics_enabled_runner_app
    window_end = _WINDOW_REFERENCE
    window_start = window_end - timedelta(days=1)

    assert _count_latency_rows(metrics_pg_conn) == 0

    with app.app_context():
        result = latency_percentiles(
            window_start=window_start,
            window_end=window_end,
            now=window_end,
            metric_name=_LATENCY_METRIC,
            limit=25,
        )

    assert result.rows == [] and result.approximate is False


def test_latency_percentiles_empty_rollup_window_returns_empty_approximate(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN no AnonymousLatencyDailyRollups rows exist (assert-before-state)
    WHEN latency_percentiles is called over a window older than the 35-day raw
        retention horizon, forcing the rollup (approximate) read path
    THEN the result is [] and approximate=True — the dashboard renders its empty
        state while still flagging the window as daily-resolution.
    """
    app = metrics_enabled_runner_app
    now = _WINDOW_REFERENCE
    window_start = now - timedelta(days=60)
    window_end = now - timedelta(days=40)

    assert _count_latency_rollup_rows(metrics_pg_conn) == 0

    with app.app_context():
        result = latency_percentiles(
            window_start=window_start,
            window_end=window_end,
            now=now,
            metric_name=_LATENCY_METRIC,
            limit=25,
        )

    assert result.rows == []
    assert result.approximate


def test_latency_percentiles_exact_interpolated_values(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN ten samples [10,20,...,100] for one endpoint in the window
    WHEN latency_percentiles is called
    THEN p50/p95/p99 match the hand-computed `percentile_cont` interpolation
        exactly (continuous, NOT discrete) and sample_count is 10.

    `percentile_cont(p)` over n sorted values picks rank = p*(n-1) and linearly
    interpolates between the floor and ceil ranks. For n=10:
      p50 -> rank 4.5 -> (50 + 60) / 2          = 55.0
      p95 -> rank 8.55 -> 90 + 0.55 * (100-90)  = 95.5
      p99 -> rank 8.91 -> 90 + 0.91 * (100-90)  = 99.1
    """
    app = metrics_enabled_runner_app
    window_end = _WINDOW_REFERENCE
    window_start = window_end - timedelta(days=1)
    inside = window_start + timedelta(hours=1)

    assert _count_latency_rows(metrics_pg_conn) == 0

    for duration in (10, 20, 30, 40, 50, 60, 70, 80, 90, 100):
        _insert_latency_row(
            metrics_pg_conn,
            observed_at=inside,
            duration_ms=float(duration),
            endpoint=_LATENCY_ENDPOINT_FAST,
            method="GET",
        )

    with app.app_context():
        result = latency_percentiles(
            window_start=window_start,
            window_end=window_end,
            now=window_end,
            metric_name=_LATENCY_METRIC,
            limit=25,
        )

    assert result.approximate is False
    assert len(result.rows) == 1
    row = result.rows[0]
    assert row.endpoint == _LATENCY_ENDPOINT_FAST
    assert row.method == "GET"
    assert row.p50 == pytest.approx(55.0)
    assert row.p95 == pytest.approx(95.5)
    assert row.p99 == pytest.approx(99.1)
    assert row.sample_count == 10


def test_latency_percentiles_orders_by_p95_descending(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN two endpoints — a fast one ([10..100], p95=95.5) and a slow one
        ([100..500], p95=480.0) — in the same window
    WHEN latency_percentiles is called
    THEN both rows are returned ordered by p95 descending (slowest first), so
        the dashboard surfaces the worst-latency endpoint at the top.

    Slow endpoint samples [100,200,300,400,500] (n=5):
      p50 -> rank 2.0  -> 300.0
      p95 -> rank 3.8  -> 400 + 0.8 * (500-400)  = 480.0
      p99 -> rank 3.96 -> 400 + 0.96 * (500-400) = 496.0
    """
    app = metrics_enabled_runner_app
    window_end = _WINDOW_REFERENCE
    window_start = window_end - timedelta(days=1)
    inside = window_start + timedelta(hours=1)

    assert _count_latency_rows(metrics_pg_conn) == 0

    for duration in (10, 20, 30, 40, 50, 60, 70, 80, 90, 100):
        _insert_latency_row(
            metrics_pg_conn,
            observed_at=inside,
            duration_ms=float(duration),
            endpoint=_LATENCY_ENDPOINT_FAST,
            method="GET",
        )
    for duration in (100, 200, 300, 400, 500):
        _insert_latency_row(
            metrics_pg_conn,
            observed_at=inside,
            duration_ms=float(duration),
            endpoint=_LATENCY_ENDPOINT_SLOW,
            method="POST",
        )

    with app.app_context():
        result = latency_percentiles(
            window_start=window_start,
            window_end=window_end,
            now=window_end,
            metric_name=_LATENCY_METRIC,
            limit=25,
        )

    assert result.approximate is False
    assert [row.endpoint for row in result.rows] == [
        _LATENCY_ENDPOINT_SLOW,
        _LATENCY_ENDPOINT_FAST,
    ]
    slow_row = result.rows[0]
    assert slow_row.p50 == pytest.approx(300.0)
    assert slow_row.p95 == pytest.approx(480.0)
    assert slow_row.p99 == pytest.approx(496.0)
    assert slow_row.sample_count == 5


def test_latency_percentiles_filters_by_endpoint_method_and_device(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN samples spread across two endpoints, two methods, and two device
        types in the same window
    WHEN latency_percentiles is called with endpoint+method+device_type filters
    THEN only the samples matching all three narrow the result to a single row
        whose sample_count reflects exactly the matching samples.
    """
    app = metrics_enabled_runner_app
    window_end = _WINDOW_REFERENCE
    window_start = window_end - timedelta(days=1)
    inside = window_start + timedelta(hours=1)

    assert _count_latency_rows(metrics_pg_conn) == 0

    # Target: fast endpoint, GET, MOBILE (the two samples we want to keep).
    for duration in (10.0, 30.0):
        _insert_latency_row(
            metrics_pg_conn,
            observed_at=inside,
            duration_ms=duration,
            endpoint=_LATENCY_ENDPOINT_FAST,
            method="GET",
            dimensions={"device_type": int(DeviceType.MOBILE)},
        )
    # Same endpoint+method but DESKTOP — excluded by the device filter.
    _insert_latency_row(
        metrics_pg_conn,
        observed_at=inside,
        duration_ms=999.0,
        endpoint=_LATENCY_ENDPOINT_FAST,
        method="GET",
        dimensions={"device_type": int(DeviceType.DESKTOP)},
    )
    # Same endpoint+device but POST — excluded by the method filter.
    _insert_latency_row(
        metrics_pg_conn,
        observed_at=inside,
        duration_ms=888.0,
        endpoint=_LATENCY_ENDPOINT_FAST,
        method="POST",
        dimensions={"device_type": int(DeviceType.MOBILE)},
    )
    # Different endpoint — excluded by the endpoint filter.
    _insert_latency_row(
        metrics_pg_conn,
        observed_at=inside,
        duration_ms=777.0,
        endpoint=_LATENCY_ENDPOINT_SLOW,
        method="GET",
        dimensions={"device_type": int(DeviceType.MOBILE)},
    )

    with app.app_context():
        result = latency_percentiles(
            window_start=window_start,
            window_end=window_end,
            now=window_end,
            metric_name=_LATENCY_METRIC,
            endpoint=_LATENCY_ENDPOINT_FAST,
            method="GET",
            device_type=DeviceType.MOBILE,
            limit=25,
        )

    assert result.approximate is False
    assert len(result.rows) == 1
    row = result.rows[0]
    assert row.endpoint == _LATENCY_ENDPOINT_FAST
    assert row.method == "GET"
    assert row.sample_count == 2
    # Only [10, 30] remain: p50 -> rank 0.5 -> 10 + 0.5*(30-10) = 20.0
    assert row.p50 == pytest.approx(20.0)


def test_latency_timeseries_empty_window_zero_fills_with_none(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN no samples exist in a 3-hour window (assert-before-state)
    WHEN latency_timeseries is called with resolution="hour"
    THEN exactly 3 buckets are returned, each zero-filled with
        p50 = p95 = p99 = None and sample_count = 0 across all three series.
    """
    app = metrics_enabled_runner_app
    window_end = _WINDOW_REFERENCE
    window_start = window_end - timedelta(hours=3)

    assert _count_latency_rows(metrics_pg_conn) == 0

    with app.app_context():
        buckets = latency_timeseries(
            metric_name=_LATENCY_METRIC,
            window_start=window_start,
            window_end=window_end,
            now=window_end,
            resolution="hour",
            endpoint=_LATENCY_ENDPOINT_FAST,
        )

    assert len(buckets) == 3
    bucket_starts = [bucket.bucket for bucket in buckets]
    assert bucket_starts == sorted(bucket_starts)
    for bucket in buckets:
        assert bucket.p50 is None
        assert bucket.p95 is None
        assert bucket.p99 is None
        assert bucket.sample_count == 0


def test_latency_timeseries_per_bucket_percentiles_and_zero_fill(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN samples [10,20,30,40,50] seeded into ONLY the middle of three
        consecutive 1-hour buckets in the window
    WHEN latency_timeseries is called with resolution="hour"
    THEN exactly 3 buckets are returned: the seeded middle bucket carries the
        hand-computed p50/p95/p99 for all three series and sample_count=5, while
        the two empty buckets are zero-filled with None percentiles for all
        three series and sample_count=0.

    Middle-bucket samples [10,20,30,40,50] (n=5):
      p50 -> rank 2.0  -> 30.0
      p95 -> rank 3.8  -> 40 + 0.8 * (50-40)  = 48.0
      p99 -> rank 3.96 -> 40 + 0.96 * (50-40) = 49.6
    """
    app = metrics_enabled_runner_app
    # A 3-hour window aligned on the hour so each bucket is a clean hour.
    window_start = _WINDOW_REFERENCE - timedelta(hours=3)
    window_end = _WINDOW_REFERENCE
    middle_bucket_start = window_start + timedelta(hours=1)
    # Seed mid-bucket (offset into the hour) to prove the bucket is the
    # truncated hour, not the exact sample instant.
    inside_middle = middle_bucket_start + timedelta(minutes=20)

    assert _count_latency_rows(metrics_pg_conn) == 0

    for duration in (10, 20, 30, 40, 50):
        _insert_latency_row(
            metrics_pg_conn,
            observed_at=inside_middle,
            duration_ms=float(duration),
            endpoint=_LATENCY_ENDPOINT_FAST,
            method="GET",
        )

    with app.app_context():
        buckets = latency_timeseries(
            metric_name=_LATENCY_METRIC,
            window_start=window_start,
            window_end=window_end,
            now=window_end,
            resolution="hour",
            endpoint=_LATENCY_ENDPOINT_FAST,
        )

    assert len(buckets) == 3
    bucket_starts = [bucket.bucket for bucket in buckets]
    assert bucket_starts == sorted(bucket_starts)

    by_bucket = {bucket.bucket: bucket for bucket in buckets}
    seeded = by_bucket[middle_bucket_start]
    assert seeded.p50 == pytest.approx(30.0)
    assert seeded.p95 == pytest.approx(48.0)
    assert seeded.p99 == pytest.approx(49.6)
    assert seeded.sample_count == 5

    empty_buckets = [
        bucket for bucket in buckets if bucket.bucket != middle_bucket_start
    ]
    assert len(empty_buckets) == 2
    for bucket in empty_buckets:
        assert bucket.p50 is None
        assert bucket.p95 is None
        assert bucket.p99 is None
        assert bucket.sample_count == 0


def test_latency_percentiles_recent_window_is_exact_and_not_approximate(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN raw samples [10..100] inside a 1-day window AND rollup rows that would
        produce different values (assert-before-state: both tables empty first)
    WHEN latency_percentiles is called with `now` such that the window is inside
        the 35-day raw retention horizon
    THEN the result is served from raw samples (exact percentiles) with
        approximate=False — the rollup rows are ignored on the recent path.
    """
    app = metrics_enabled_runner_app
    window_end = _WINDOW_REFERENCE
    window_start = window_end - timedelta(days=1)
    inside = window_start + timedelta(hours=1)

    assert _count_latency_rows(metrics_pg_conn) == 0
    assert _count_latency_rollup_rows(metrics_pg_conn) == 0

    for duration in (10, 20, 30, 40, 50, 60, 70, 80, 90, 100):
        _insert_latency_row(
            metrics_pg_conn,
            observed_at=inside,
            duration_ms=float(duration),
            endpoint=_LATENCY_ENDPOINT_FAST,
            method="GET",
        )
    # A rollup row for the same day with deliberately different values, to prove
    # the recent path never reads it.
    _insert_latency_rollup_row(
        metrics_pg_conn,
        rollup_date=window_start.date(),
        p50_ms=999.0,
        p95_ms=999.0,
        p99_ms=999.0,
        sample_count=42,
        endpoint=_LATENCY_ENDPOINT_FAST,
        method="GET",
    )

    with app.app_context():
        result = latency_percentiles(
            window_start=window_start,
            window_end=window_end,
            now=window_end,
            metric_name=_LATENCY_METRIC,
            limit=25,
        )

    assert result.approximate is False
    assert len(result.rows) == 1
    row = result.rows[0]
    assert row.p50 == pytest.approx(55.0)
    assert row.p95 == pytest.approx(95.5)
    assert row.p99 == pytest.approx(99.1)
    assert row.sample_count == 10


def test_latency_percentiles_old_window_is_weighted_average_and_approximate(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN two daily rollup rows for one endpoint inside a window older than the
        35-day raw retention horizon (assert-before-state: rollup table empty)
    WHEN latency_percentiles is called with `now` placing the window beyond raw
        retention
    THEN the result is approximate=True and each percentile is the
        sample-count-weighted average of the daily values.

    Hand-computed weighted p95 over two days:
      day1: p95=100.0, count=10  -> contributes 100*10 = 1000
      day2: p95=200.0, count=30  -> contributes 200*30 = 6000
      weighted p95 = (1000 + 6000) / (10 + 30) = 7000 / 40 = 175.0
    p50 weighted = (50*10 + 150*30) / 40 = (500 + 4500) / 40 = 125.0
    p99 weighted = (110*10 + 210*30) / 40 = (1100 + 6300) / 40 = 185.0
    sample_count = 40
    """
    app = metrics_enabled_runner_app
    now = _WINDOW_REFERENCE
    window_start = now - timedelta(days=60)
    window_end = now - timedelta(days=40)
    day_one = window_start.date() + timedelta(days=1)
    day_two = window_start.date() + timedelta(days=2)

    assert _count_latency_rollup_rows(metrics_pg_conn) == 0

    _insert_latency_rollup_row(
        metrics_pg_conn,
        rollup_date=day_one,
        p50_ms=50.0,
        p95_ms=100.0,
        p99_ms=110.0,
        sample_count=10,
        endpoint=_LATENCY_ENDPOINT_FAST,
        method="GET",
    )
    _insert_latency_rollup_row(
        metrics_pg_conn,
        rollup_date=day_two,
        p50_ms=150.0,
        p95_ms=200.0,
        p99_ms=210.0,
        sample_count=30,
        endpoint=_LATENCY_ENDPOINT_FAST,
        method="GET",
    )

    with app.app_context():
        result = latency_percentiles(
            window_start=window_start,
            window_end=window_end,
            now=now,
            metric_name=_LATENCY_METRIC,
            limit=25,
        )

    assert result.approximate is True
    assert len(result.rows) == 1
    row = result.rows[0]
    assert row.endpoint == _LATENCY_ENDPOINT_FAST
    assert row.method == "GET"
    assert row.p50 == pytest.approx(125.0)
    assert row.p95 == pytest.approx(175.0)
    assert row.p99 == pytest.approx(185.0)
    assert row.sample_count == 40


def test_latency_percentiles_old_window_orders_by_weighted_p95_descending(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN rollup rows for a fast endpoint (weighted p95=100) and a slow endpoint
        (weighted p95=400) in a window older than raw retention
    WHEN latency_percentiles is called on the rollup path
    THEN rows are ordered by weighted p95 descending (slowest endpoint first).
    """
    app = metrics_enabled_runner_app
    now = _WINDOW_REFERENCE
    window_start = now - timedelta(days=60)
    window_end = now - timedelta(days=40)
    day_one = window_start.date() + timedelta(days=1)

    assert _count_latency_rollup_rows(metrics_pg_conn) == 0

    _insert_latency_rollup_row(
        metrics_pg_conn,
        rollup_date=day_one,
        p50_ms=50.0,
        p95_ms=100.0,
        p99_ms=110.0,
        sample_count=10,
        endpoint=_LATENCY_ENDPOINT_FAST,
        method="GET",
    )
    _insert_latency_rollup_row(
        metrics_pg_conn,
        rollup_date=day_one,
        p50_ms=300.0,
        p95_ms=400.0,
        p99_ms=410.0,
        sample_count=10,
        endpoint=_LATENCY_ENDPOINT_SLOW,
        method="POST",
    )

    with app.app_context():
        result = latency_percentiles(
            window_start=window_start,
            window_end=window_end,
            now=now,
            metric_name=_LATENCY_METRIC,
            limit=25,
        )

    assert result.approximate is True
    assert [row.endpoint for row in result.rows] == [
        _LATENCY_ENDPOINT_SLOW,
        _LATENCY_ENDPOINT_FAST,
    ]


def test_latency_timeseries_old_window_reads_daily_rollup_with_zero_fill(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN rollup rows seeded on two non-adjacent days inside a window older than
        raw retention, with one gap day between them
    WHEN latency_timeseries is called with resolution="hour" (which must coerce
        to daily grain because the window is beyond raw retention)
    THEN one bucket per UTC day is returned, the two seeded days carry their
        exact stored percentiles, and the gap day zero-fills with None — proving
        the date->datetime bucket-key conversion aligns with the day cursor.
    """
    app = metrics_enabled_runner_app
    now = _WINDOW_REFERENCE
    window_start = (now - timedelta(days=50)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    window_end = window_start + timedelta(days=3)
    day_zero = window_start.date()
    day_two = window_start.date() + timedelta(days=2)

    assert _count_latency_rollup_rows(metrics_pg_conn) == 0

    _insert_latency_rollup_row(
        metrics_pg_conn,
        rollup_date=day_zero,
        p50_ms=11.0,
        p95_ms=22.0,
        p99_ms=33.0,
        sample_count=5,
        endpoint=_LATENCY_ENDPOINT_FAST,
        method="GET",
    )
    _insert_latency_rollup_row(
        metrics_pg_conn,
        rollup_date=day_two,
        p50_ms=44.0,
        p95_ms=55.0,
        p99_ms=66.0,
        sample_count=7,
        endpoint=_LATENCY_ENDPOINT_FAST,
        method="GET",
    )

    with app.app_context():
        buckets = latency_timeseries(
            metric_name=_LATENCY_METRIC,
            window_start=window_start,
            window_end=window_end,
            now=now,
            resolution="hour",
            endpoint=_LATENCY_ENDPOINT_FAST,
        )

    assert len(buckets) == 3
    by_bucket = {bucket.bucket: bucket for bucket in buckets}

    seeded_zero = by_bucket[datetime.combine(day_zero, time.min, tzinfo=timezone.utc)]
    assert seeded_zero.p50 == pytest.approx(11.0)
    assert seeded_zero.p95 == pytest.approx(22.0)
    assert seeded_zero.p99 == pytest.approx(33.0)
    assert seeded_zero.sample_count == 5

    seeded_two = by_bucket[datetime.combine(day_two, time.min, tzinfo=timezone.utc)]
    assert seeded_two.p50 == pytest.approx(44.0)
    assert seeded_two.p95 == pytest.approx(55.0)
    assert seeded_two.p99 == pytest.approx(66.0)
    assert seeded_two.sample_count == 7

    gap_day = window_start.date() + timedelta(days=1)
    gap_bucket = by_bucket[datetime.combine(gap_day, time.min, tzinfo=timezone.utc)]
    assert gap_bucket.p50 is None
    assert gap_bucket.p95 is None
    assert gap_bucket.p99 is None
    assert gap_bucket.sample_count == 0
