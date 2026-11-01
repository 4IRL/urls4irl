from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Generator, Literal

import pytest
from flask import Flask
from sqlalchemy import text

from backend import db
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
    grouped_timeseries,
    latency_percentiles,
    latency_timeseries,
    summary,
    timeseries,
    top_events,
    validate_dim_keys,
)
from backend.metrics.resources import Resource
from backend.metrics.suppression import MIN_CELL_COUNT, SUPPRESSED_DIM_VALUE
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
    GIVEN two UTUB_CREATED rows in two distinct hour buckets within a 1-day
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
        event_name=EventName.UTUB_CREATED,
        bucket_start=first_bucket,
        count=3,
    )
    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.UTUB_CREATED,
        bucket_start=second_bucket,
        count=4,
    )

    with app.app_context():
        hourly_result = timeseries(
            event_name=EventName.UTUB_CREATED,
            window_start=window_start,
            window_end=window_end,
            resolution="hour",
        )
        daily_result = timeseries(
            event_name=EventName.UTUB_CREATED,
            window_start=window_start,
            window_end=window_end,
            resolution="day",
        )

    hourly = hourly_result.buckets
    daily = daily_result.buckets
    assert hourly_result.resolution == "hour"
    assert daily_result.resolution == "day"

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
            (EventName.UTUB_CREATED.value, window_start, window_end),
        )
        existing_count = cur.fetchone()[0]
    assert existing_count == 0

    with app.app_context():
        result = timeseries(
            event_name=EventName.UTUB_CREATED,
            window_start=window_start,
            window_end=window_end,
            resolution="hour",
        )

    rows = result.buckets
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
        result = timeseries(
            event_name=EventName.UTUB_CREATED,
            window_start=window_start,
            window_end=window_end,
            resolution="hour",
        )

    rows = result.buckets
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
        result = timeseries(
            event_name=EventName.API_HIT,
            window_start=window_start,
            window_end=window_end,
            resolution="hour",
            endpoint="utubs.get_single_utub",
            method="GET",
        )

    rows = result.buckets
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
        EventName.UI_TAG_APPLY_DRAG,
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
        result = timeseries(
            event_name=EventName.UI_UTUB_SELECT,
            window_start=window_start,
            window_end=window_end,
            resolution="hour",
            device_type=int(filter_device_type),
        )

    rows = result.buckets
    assert len(rows) == 24
    nonzero = [row for row in rows if row.count != 0]
    assert len(nonzero) == 1
    assert nonzero[0].count == expected_count
    assert nonzero[0].bucket == inside


def test_timeseries_daily_event_returns_complete_days_as_day_resolution(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN UTUB_OPENED rows at three UTC midnights and a mid-day window
    WHEN timeseries is called with resolution="hour"
    THEN the result reports "day", covers complete UTC days only (current day
        excluded) and zero-fills days without rows.
    """
    window_end = _WINDOW_REFERENCE  # 2026-01-15 12:00 UTC
    window_start = window_end - timedelta(days=3)  # 2026-01-12 12:00 UTC
    day_13 = datetime(2026, 1, 13, tzinfo=timezone.utc)
    day_14 = datetime(2026, 1, 14, tzinfo=timezone.utc)
    day_15 = datetime(2026, 1, 15, tzinfo=timezone.utc)
    for bucket_start, count in ((day_13, 5), (day_15, 9)):
        _insert_metric_row(
            metrics_pg_conn,
            event_name=EventName.UTUB_OPENED,
            bucket_start=bucket_start,
            count=count,
        )

    with metrics_enabled_runner_app.app_context():
        result = timeseries(
            event_name=EventName.UTUB_OPENED,
            window_start=window_start,
            window_end=window_end,
            resolution="hour",
        )

    assert result.resolution == "day"
    # [floor(Jan 12 12:00), floor(Jan 15 12:00)) = Jan 12, 13, 14
    assert [(row.bucket, row.count) for row in result.buckets] == [
        (datetime(2026, 1, 12, tzinfo=timezone.utc), 0),
        (day_13, 5),
        (day_14, 0),
    ]


def test_timeseries_daily_event_without_complete_day_is_empty(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN a window inside a single UTC day
    WHEN timeseries is called for a daily event
    THEN no buckets are returned and the resolution is "day".
    """
    with metrics_enabled_runner_app.app_context():
        result = timeseries(
            event_name=EventName.UTUB_OPENED,
            window_start=_WINDOW_REFERENCE - timedelta(hours=6),
            window_end=_WINDOW_REFERENCE,
            resolution="hour",
        )

    assert result.resolution == "day"
    assert result.buckets == []


def test_timeseries_daily_event_offset_range_keys_by_utc_midnight(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN UTUB_OPENED rows at UTC midnights and an explicit -07:00 range
    WHEN timeseries is called
    THEN buckets are keyed at UTC midnights with the counts in the right
        buckets (never local-midnight keys that miss the UTC keys).
    """
    tz_minus_7 = timezone(timedelta(hours=-7))
    # 2026-01-12 20:00 -07:00 = Jan 13 03:00 UTC; end Jan 15 20:00 -07:00 =
    # Jan 16 03:00 UTC. Complete UTC days: Jan 13, 14, 15.
    window_start = datetime(2026, 1, 12, 20, 0, tzinfo=tz_minus_7)
    window_end = datetime(2026, 1, 15, 20, 0, tzinfo=tz_minus_7)
    for day, count in ((13, 2), (14, 3), (15, 4)):
        _insert_metric_row(
            metrics_pg_conn,
            event_name=EventName.UTUB_OPENED,
            bucket_start=datetime(2026, 1, day, tzinfo=timezone.utc),
            count=count,
        )

    with metrics_enabled_runner_app.app_context():
        result = timeseries(
            event_name=EventName.UTUB_OPENED,
            window_start=window_start,
            window_end=window_end,
            resolution="day",
        )

    assert [(row.bucket, row.count) for row in result.buckets] == [
        (datetime(2026, 1, 13, tzinfo=timezone.utc), 2),
        (datetime(2026, 1, 14, tzinfo=timezone.utc), 3),
        (datetime(2026, 1, 15, tzinfo=timezone.utc), 4),
    ]


def test_timeseries_hourly_event_day_resolution_offset_start_keys_by_utc_midnight(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN UTUB_CREATED (hourly-stored) rows on Jan 13 and Jan 14 and a day
        resolution range starting at 20:00 -07:00 (= 03:00 UTC)
    WHEN timeseries is called
    THEN the first bucket is the UTC midnight of the start's UTC day (never the
        local midnight) and counts land in the matching UTC-midnight buckets.
    """
    tz_minus_7 = timezone(timedelta(hours=-7))
    # Start Jan 12 20:00 -07:00 = Jan 13 03:00 UTC; end Jan 14 20:00 -07:00 =
    # Jan 15 03:00 UTC.
    window_start = datetime(2026, 1, 12, 20, 0, tzinfo=tz_minus_7)
    window_end = datetime(2026, 1, 14, 20, 0, tzinfo=tz_minus_7)
    for bucket_start, count in (
        (datetime(2026, 1, 13, 5, tzinfo=timezone.utc), 2),
        (datetime(2026, 1, 14, 1, tzinfo=timezone.utc), 3),
    ):
        _insert_metric_row(
            metrics_pg_conn,
            event_name=EventName.UTUB_CREATED,
            bucket_start=bucket_start,
            count=count,
        )

    with metrics_enabled_runner_app.app_context():
        result = timeseries(
            event_name=EventName.UTUB_CREATED,
            window_start=window_start,
            window_end=window_end,
            resolution="day",
        )

    assert result.resolution == "day"
    assert [(row.bucket, row.count) for row in result.buckets] == [
        (datetime(2026, 1, 13, tzinfo=timezone.utc), 2),
        (datetime(2026, 1, 14, tzinfo=timezone.utc), 3),
        # Partial trailing day (end is 03:00 UTC) is zero-filled for hourly events.
        (datetime(2026, 1, 15, tzinfo=timezone.utc), 0),
    ]


def test_timeseries_day_groups_under_utc_date_with_non_utc_session_timezone(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN a midnight-UTC UTUB_OPENED row and a Los Angeles session timezone on
        the session the service reads through
    WHEN timeseries runs
    THEN the row is grouped under its own UTC date (without the three-argument
        `date_trunc` it would land on the previous local day and read zero).
    """
    day = datetime(2026, 1, 14, tzinfo=timezone.utc)
    _insert_metric_row(
        metrics_pg_conn, event_name=EventName.UTUB_OPENED, bucket_start=day, count=6
    )

    with metrics_enabled_runner_app.app_context():
        db.session.execute(text("SET LOCAL TIME ZONE 'America/Los_Angeles'"))
        result = timeseries(
            event_name=EventName.UTUB_OPENED,
            window_start=datetime(2026, 1, 13, tzinfo=timezone.utc),
            window_end=datetime(2026, 1, 15, tzinfo=timezone.utc),
            resolution="day",
        )
        db.session.rollback()

    assert [(row.bucket, row.count) for row in result.buckets] == [
        (datetime(2026, 1, 13, tzinfo=timezone.utc), 0),
        (day, 6),
    ]


def test_grouped_timeseries_day_groups_under_utc_date_with_non_utc_session_timezone(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN a midnight-UTC API_METRICS_INGEST_BATCH row and a Los Angeles
        session timezone on the session the service reads through
    WHEN grouped_timeseries runs at day resolution
    THEN the row's bucket is its own UTC date, not the previous local day.
    """
    day = datetime(2026, 1, 14, tzinfo=timezone.utc)
    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.API_METRICS_INGEST_BATCH,
        bucket_start=day,
        dimensions={
            "batch_size_bucket": "1",
            "transport": "fetch",
            "device_type": 2,
        },
        count=1000,
    )

    with metrics_enabled_runner_app.app_context():
        db.session.execute(text("SET LOCAL TIME ZONE 'America/Los_Angeles'"))
        response = grouped_timeseries(
            event_name=EventName.API_METRICS_INGEST_BATCH,
            group_by=["batch_size_bucket", "transport", "device_type"],
            window_start=datetime(2026, 1, 13, tzinfo=timezone.utc),
            window_end=datetime(2026, 1, 15, tzinfo=timezone.utc),
            resolution="day",
        )
        db.session.rollback()

    assert [bucket.bucket for bucket in response.buckets] == [day]


def test_grouped_timeseries_daily_event_counts_complete_days_only(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN UTUB_OPENED rows at the UTC midnights of Jan 12, 13 and 15 and a
        mid-day window (Jan 12 12:00 to Jan 15 12:00)
    WHEN grouped_timeseries runs at day resolution
    THEN both ends floor to UTC midnight: Jan 12 (floored start) and Jan 13
        are returned while the current day (Jan 15) stays hidden.
    """
    window_end = _WINDOW_REFERENCE  # 2026-01-15 12:00 UTC
    window_start = window_end - timedelta(days=3)  # 2026-01-12 12:00 UTC
    day_12 = datetime(2026, 1, 12, tzinfo=timezone.utc)
    day_13 = datetime(2026, 1, 13, tzinfo=timezone.utc)
    day_15 = datetime(2026, 1, 15, tzinfo=timezone.utc)
    for bucket_start, count in ((day_12, 6), (day_13, 7), (day_15, 9)):
        _insert_metric_row(
            metrics_pg_conn,
            event_name=EventName.UTUB_OPENED,
            bucket_start=bucket_start,
            dimensions=_utub_opened_dims(),
            count=count,
        )

    with metrics_enabled_runner_app.app_context():
        response = grouped_timeseries(
            event_name=EventName.UTUB_OPENED,
            group_by=["url_count_bucket"],
            window_start=window_start,
            window_end=window_end,
            resolution="day",
        )

    assert [(bucket.bucket, bucket.count) for bucket in response.buckets] == [
        (day_12, 6),
        (day_13, 7),
    ]


def _utub_opened_dims(
    *,
    url_count_bucket: str = "1-5",
    age_bucket: str = "0-6d",
    device_type: DeviceType = DeviceType.DESKTOP,
) -> dict[str, str | int]:
    """Return a full UTUB_OPENED dimension dict (both bucket keys + device)."""
    return {
        "url_count_bucket": url_count_bucket,
        "age_bucket": age_bucket,
        "device_type": int(device_type),
    }


@pytest.mark.parametrize("requested", ["hour", "day"])
def test_grouped_timeseries_daily_event_reports_effective_day_resolution(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
    requested: Literal["hour", "day"],
) -> None:
    """
    GIVEN a UTUB_OPENED cell of 6 on a complete UTC day
    WHEN grouped_timeseries is requested at `hour` or `day`
    THEN the response reports `day` and the bucket is the UTC midnight.
    """
    day = datetime(2026, 1, 13, tzinfo=timezone.utc)
    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.UTUB_OPENED,
        bucket_start=day,
        dimensions=_utub_opened_dims(),
        count=6,
    )

    with metrics_enabled_runner_app.app_context():
        response = grouped_timeseries(
            event_name=EventName.UTUB_OPENED,
            group_by=["age_bucket"],
            window_start=datetime(2026, 1, 13, tzinfo=timezone.utc),
            window_end=datetime(2026, 1, 14, 12, tzinfo=timezone.utc),
            resolution=requested,
        )

    assert response.resolution == "day"
    assert [(bucket.bucket, bucket.count) for bucket in response.buckets] == [(day, 6)]


@pytest.mark.parametrize("dim_key", ["url_count_bucket", "age_bucket"])
def test_grouped_timeseries_new_dims_floor_and_exact_floor(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
    dim_key: str,
) -> None:
    """
    GIVEN UTUB_OPENED cells of MIN_CELL_COUNT - 1 and MIN_CELL_COUNT in
        separate day partitions
    WHEN grouped_timeseries groups by one bucket dim
    THEN the sub-floor cell reads "suppressed" and the exact-floor cell keeps
        its real label.
    """
    small_label, floor_label = (
        ("1-5", "6-20")
        if dim_key == "url_count_bucket"
        else (
            "0-6d",
            "7-29d",
        )
    )
    day_a = datetime(2026, 1, 12, tzinfo=timezone.utc)
    day_b = datetime(2026, 1, 13, tzinfo=timezone.utc)
    for day, label, count in (
        (day_a, small_label, MIN_CELL_COUNT - 1),
        (day_b, floor_label, MIN_CELL_COUNT),
    ):
        _insert_metric_row(
            metrics_pg_conn,
            event_name=EventName.UTUB_OPENED,
            bucket_start=day,
            dimensions={**_utub_opened_dims(), dim_key: label},
            count=count,
        )

    with metrics_enabled_runner_app.app_context():
        response = grouped_timeseries(
            event_name=EventName.UTUB_OPENED,
            group_by=[dim_key],
            window_start=day_a,
            window_end=datetime(2026, 1, 15, tzinfo=timezone.utc),
            resolution="day",
        )

    cells = [
        (bucket.bucket, bucket.dimensions[dim_key], bucket.count)
        for bucket in response.buckets
    ]
    assert cells == [
        (day_a, SUPPRESSED_DIM_VALUE, MIN_CELL_COUNT - 1),
        (day_b, floor_label, MIN_CELL_COUNT),
    ]


@pytest.mark.parametrize(
    "dim_key,labels",
    [
        ("url_count_bucket", ("1-5", "6-20", "21-50")),
        ("age_bucket", ("0-6d", "7-29d", "30-89d")),
    ],
)
def test_grouped_count_by_new_dims_merge_and_skip_rows_without_keys(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
    dim_key: str,
    labels: tuple[str, str, str],
) -> None:
    """
    GIVEN cells of 3, 20 and 30 on a bucket dim plus a legacy row without it
    WHEN grouped_count_by groups by that dim
    THEN the lone 3 absorbs the 20 into one sentinel of 23, the 30 survives and
        the legacy row is absent.
    """
    inside = datetime(2026, 1, 13, tzinfo=timezone.utc)
    for label, count in zip(labels, (3, 20, 30)):
        _insert_metric_row(
            metrics_pg_conn,
            event_name=EventName.UTUB_OPENED,
            bucket_start=inside,
            dimensions={**_utub_opened_dims(), dim_key: label},
            count=count,
        )
    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.UTUB_OPENED,
        bucket_start=inside,
        dimensions={"device_type": int(DeviceType.DESKTOP)},
        count=40,
    )

    with metrics_enabled_runner_app.app_context():
        rows = grouped_count_by(
            event_name=EventName.UTUB_OPENED,
            window_start=datetime(2026, 1, 13, tzinfo=timezone.utc),
            window_end=datetime(2026, 1, 15, tzinfo=timezone.utc),
            group_by=dim_key,
        )

    assert rows == [(labels[2], 30), (SUPPRESSED_DIM_VALUE, 23)]


def test_grouped_count_by_exact_floor_cell_survives(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN size cells of exactly MIN_CELL_COUNT and 30
    WHEN grouped_count_by groups by url_count_bucket
    THEN both keep their real labels (no sub-floor sibling).
    """
    day = datetime(2026, 1, 13, tzinfo=timezone.utc)
    for label, count in (("6-20", MIN_CELL_COUNT), ("21-50", 30)):
        _insert_metric_row(
            metrics_pg_conn,
            event_name=EventName.UTUB_OPENED,
            bucket_start=day,
            dimensions=_utub_opened_dims(url_count_bucket=label),
            count=count,
        )

    with metrics_enabled_runner_app.app_context():
        rows = grouped_count_by(
            event_name=EventName.UTUB_OPENED,
            window_start=day,
            window_end=datetime(2026, 1, 15, tzinfo=timezone.utc),
            group_by="url_count_bucket",
        )

    assert rows == [("21-50", 30), ("6-20", MIN_CELL_COUNT)]


def test_grouped_timeseries_non_partitioned_offset_start_uses_utc_midnight(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN UTUB_OPENED rows on Jan 13 and Jan 14 and a -07:00 window starting
        at Jan 12 20:00 local (= Jan 13 03:00 UTC)
    WHEN grouped_timeseries runs at day resolution (requested `hour` too) with
        partition_by_bucket=False
    THEN the single synthetic bucket is the UTC midnight of the start's UTC
        day (Jan 13), never the local midnight, and sums both days.
    """
    tz_minus_7 = timezone(timedelta(hours=-7))
    window_start = datetime(2026, 1, 12, 20, 0, tzinfo=tz_minus_7)
    window_end = datetime(2026, 1, 15, 20, 0, tzinfo=tz_minus_7)
    for day, count in ((13, 2), (14, 3)):
        _insert_metric_row(
            metrics_pg_conn,
            event_name=EventName.UTUB_OPENED,
            bucket_start=datetime(2026, 1, day, tzinfo=timezone.utc),
            dimensions=_utub_opened_dims(),
            count=count,
        )

    with metrics_enabled_runner_app.app_context():
        response = grouped_timeseries(
            event_name=EventName.UTUB_OPENED,
            group_by=["url_count_bucket"],
            window_start=window_start,
            window_end=window_end,
            resolution="hour",
            partition_by_bucket=False,
        )

    assert response.resolution == "day"
    assert [(bucket.bucket, bucket.count) for bucket in response.buckets] == [
        (datetime(2026, 1, 13, tzinfo=timezone.utc), 5)
    ]


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
        count=5,
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
    assert result_dict == {"escape_key": 7, "cancel_button": 5}
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


_DAILY_NOW: datetime = datetime(2026, 1, 15, 14, 0, 0, tzinfo=timezone.utc)
_DAILY_TODAY: datetime = datetime(2026, 1, 15, 0, 0, 0, tzinfo=timezone.utc)


def test_top_events_daily_event_counts_complete_days_only(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN UTUB_OPENED rows for D-2 (2), D-1 (3 at midnight + 4 hourly leftover)
        and the current day D (8 at midnight, 16 at 09:00), now = D 14:00
    WHEN top_events is called with window=day
    THEN current counts only D-1 in full (7), previous counts only D-2 (2),
        and the current day D is hidden.
    """
    app = metrics_enabled_runner_app
    for bucket_start, count in (
        (_DAILY_TODAY - timedelta(days=2), 2),
        (_DAILY_TODAY - timedelta(days=1), 3),
        (_DAILY_TODAY - timedelta(days=1) + timedelta(hours=7), 4),
        (_DAILY_TODAY, 8),
        (_DAILY_TODAY + timedelta(hours=9), 16),
    ):
        _insert_metric_row(
            metrics_pg_conn,
            event_name=EventName.UTUB_OPENED,
            bucket_start=bucket_start,
            count=count,
        )

    window_start = _DAILY_NOW - timedelta(days=1)
    with app.app_context():
        rows = top_events(
            window_start=window_start,
            window_end=_DAILY_NOW,
            previous_window_start=window_start - timedelta(days=1),
            previous_window_end=window_start,
            category=None,
            limit=10,
        )

    assert len(rows) == 1
    assert rows[0].event_name == EventName.UTUB_OPENED.value
    assert rows[0].total_count == 7
    assert rows[0].previous_count == 2


@pytest.mark.parametrize("span_days", [1, 7, 30])
def test_summary_daily_event_never_counted_in_both_windows(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
    span_days: int,
) -> None:
    """
    GIVEN one UTUB_OPENED row (count 1) per UTC day for 70 days, plus the
        current day's row
    WHEN summary is called for contiguous current and previous windows of
        span_days ending at D 14:00
    THEN each period counts exactly span_days days: no overlap, no loss, and
        the current day is excluded.
    """
    app = metrics_enabled_runner_app
    for days_back in range(0, 70):
        _insert_metric_row(
            metrics_pg_conn,
            event_name=EventName.UTUB_OPENED,
            bucket_start=_DAILY_TODAY - timedelta(days=days_back),
            count=1,
        )

    window_start = _DAILY_NOW - timedelta(days=span_days)
    with app.app_context():
        result = summary(
            window_start=window_start,
            window_end=_DAILY_NOW,
            previous_window_start=window_start - timedelta(days=span_days),
            previous_window_end=window_start,
        )

    domain_row = next(row for row in result.by_category if row.category == "domain")
    assert domain_row.current == span_days
    assert domain_row.previous == span_days


def test_summary_explicit_range_never_counted_in_both_windows(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN one UTUB_OPENED row per UTC day and an explicit 3-day range with
        non-midnight ends, with its preceding contiguous window
    WHEN summary is called
    THEN current and previous each count their 3 complete days once.
    """
    app = metrics_enabled_runner_app
    for days_back in range(0, 20):
        _insert_metric_row(
            metrics_pg_conn,
            event_name=EventName.UTUB_OPENED,
            bucket_start=_DAILY_TODAY - timedelta(days=days_back),
            count=1,
        )
    window_start = datetime(2026, 1, 10, 5, 30, tzinfo=timezone.utc)
    window_end = datetime(2026, 1, 13, 18, 45, tzinfo=timezone.utc)
    previous_start = window_start - (window_end - window_start)

    with app.app_context():
        result = summary(
            window_start=window_start,
            window_end=window_end,
            previous_window_start=previous_start,
            previous_window_end=window_start,
        )

    domain_row = next(row for row in result.by_category if row.category == "domain")
    # Current floors to [Jan 10, Jan 13): Jan 10, 11, 12.
    assert domain_row.current == 3
    # Previous floors to [Jan 6, Jan 10): Jan 6, 7, 8, 9.
    assert domain_row.previous == 4


def test_grouped_count_scalar_daily_event_single_day_range_is_zero(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN a UTUB_OPENED row and a UTUB_CREATED row, both inside one UTC day
    WHEN grouped_count_scalar is called with a range inside that single day
    THEN the daily event returns 0 and the hourly event returns its count.
    """
    app = metrics_enabled_runner_app
    day_start = _DAILY_TODAY - timedelta(days=1)
    for event_name in (EventName.UTUB_OPENED, EventName.UTUB_CREATED):
        _insert_metric_row(
            metrics_pg_conn,
            event_name=event_name,
            bucket_start=day_start + timedelta(hours=10),
            count=5,
        )

    window_start = day_start + timedelta(hours=9)
    window_end = day_start + timedelta(hours=12)
    with app.app_context():
        daily = grouped_count_scalar(
            event_name=EventName.UTUB_OPENED,
            window_start=window_start,
            window_end=window_end,
        )
        hourly = grouped_count_scalar(
            event_name=EventName.UTUB_CREATED,
            window_start=window_start,
            window_end=window_end,
        )

    assert daily == 0
    assert hourly == 5


def test_grouped_count_scalar_daily_event_straddling_midnight_returns_full_day(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN a UTUB_OPENED row for D-1 (midnight) and one for D (midnight)
    WHEN the window is 23:00 D-1 to 01:00 D
    THEN the full day D-1 is counted and day D is not (accepted behavior).
    """
    app = metrics_enabled_runner_app
    previous_day = _DAILY_TODAY - timedelta(days=1)
    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.UTUB_OPENED,
        bucket_start=previous_day,
        count=4,
    )
    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.UTUB_OPENED,
        bucket_start=_DAILY_TODAY,
        count=9,
    )

    with app.app_context():
        result = grouped_count_scalar(
            event_name=EventName.UTUB_OPENED,
            window_start=previous_day + timedelta(hours=23),
            window_end=_DAILY_TODAY + timedelta(hours=1),
        )

    assert result == 4


def test_grouped_count_scalar_daily_event_offset_range_floors_by_utc_date(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN daily UTUB_OPENED rows on Jan 14, 15 and 16 (UTC midnights)
    WHEN the range is given with a -07:00 offset, 2026-01-14T20:00-07:00 to
        2026-01-15T17:00-07:00 (UTC: Jan 15 03:00 to Jan 16 00:00)
    THEN it floors by the UTC date and counts only the Jan 15 row.
    """
    app = metrics_enabled_runner_app
    for day_of_month, count in ((14, 1), (15, 10), (16, 100)):
        _insert_metric_row(
            metrics_pg_conn,
            event_name=EventName.UTUB_OPENED,
            bucket_start=datetime(2026, 1, day_of_month, tzinfo=timezone.utc),
            count=count,
        )
    offset = timezone(timedelta(hours=-7))

    with app.app_context():
        result = grouped_count_scalar(
            event_name=EventName.UTUB_OPENED,
            window_start=datetime(2026, 1, 14, 20, 0, tzinfo=offset),
            window_end=datetime(2026, 1, 15, 17, 0, tzinfo=offset),
        )

    assert result == 10


def test_daily_event_includes_legacy_hourly_rows_for_complete_days_only(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN hourly-stamped UTUB_OPENED rows written before deploy on D-1 and D
    WHEN grouped_count_scalar covers D-2 00:00 to D 14:00
    THEN the D-1 hourly rows are included and the current day's are hidden.
    """
    app = metrics_enabled_runner_app
    previous_day = _DAILY_TODAY - timedelta(days=1)
    for bucket_start, count in (
        (previous_day + timedelta(hours=3), 2),
        (previous_day + timedelta(hours=22), 3),
        (_DAILY_TODAY + timedelta(hours=5), 50),
    ):
        _insert_metric_row(
            metrics_pg_conn,
            event_name=EventName.UTUB_OPENED,
            bucket_start=bucket_start,
            count=count,
        )

    with app.app_context():
        result = grouped_count_scalar(
            event_name=EventName.UTUB_OPENED,
            window_start=_DAILY_TODAY - timedelta(days=2),
            window_end=_DAILY_NOW,
        )

    assert result == 5


def test_hourly_event_window_boundaries_unchanged(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN UTUB_CREATED rows at exactly window_start, mid-window and exactly
        window_end
    WHEN top_events is called
    THEN the window_start row is counted and the window_end row is excluded.
    """
    app = metrics_enabled_runner_app
    window_start = _DAILY_NOW - timedelta(hours=6)
    for bucket_start, count in (
        (window_start, 1),
        (window_start + timedelta(hours=2), 2),
        (_DAILY_NOW, 4),
    ):
        _insert_metric_row(
            metrics_pg_conn,
            event_name=EventName.UTUB_CREATED,
            bucket_start=bucket_start,
            count=count,
        )

    with app.app_context():
        rows = top_events(
            window_start=window_start,
            window_end=_DAILY_NOW,
            previous_window_start=window_start - timedelta(hours=6),
            previous_window_end=window_start,
            category=None,
            limit=10,
        )

    assert rows[0].total_count == 3


def test_mixed_daily_and_hourly_flow_steps_use_their_own_windows(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN daily UTUB_OPENED rows and hourly UTUB_CREATED rows near the edges
        of a window that starts and ends mid-day
    WHEN grouped_count_scalar is called for each flow step over that window
    THEN the daily step uses the floored [start, end) and the hourly step the
        exact window.
    """
    app = metrics_enabled_runner_app
    window_start = datetime(2026, 1, 10, 6, 0, tzinfo=timezone.utc)
    window_end = datetime(2026, 1, 12, 18, 0, tzinfo=timezone.utc)
    daily_rows = (
        (datetime(2026, 1, 9, tzinfo=timezone.utc), 1),
        (datetime(2026, 1, 10, tzinfo=timezone.utc), 10),
        (datetime(2026, 1, 11, tzinfo=timezone.utc), 100),
        (datetime(2026, 1, 12, tzinfo=timezone.utc), 1000),
    )
    hourly_rows = (
        (window_start - timedelta(hours=1), 1),
        (window_start, 10),
        (datetime(2026, 1, 11, 12, tzinfo=timezone.utc), 100),
        (window_end - timedelta(hours=1), 1000),
        (window_end, 10000),
    )
    for bucket_start, count in daily_rows:
        _insert_metric_row(
            metrics_pg_conn,
            event_name=EventName.UTUB_OPENED,
            bucket_start=bucket_start,
            count=count,
        )
    for bucket_start, count in hourly_rows:
        _insert_metric_row(
            metrics_pg_conn,
            event_name=EventName.UTUB_CREATED,
            bucket_start=bucket_start,
            count=count,
        )

    with app.app_context():
        daily_step = grouped_count_scalar(
            event_name=EventName.UTUB_OPENED,
            window_start=window_start,
            window_end=window_end,
        )
        hourly_step = grouped_count_scalar(
            event_name=EventName.UTUB_CREATED,
            window_start=window_start,
            window_end=window_end,
        )

    # Daily floors to [Jan 10, Jan 12): Jan 10 and Jan 11.
    assert daily_step == 110
    # Hourly keeps the exact [Jan 10 06:00, Jan 12 18:00).
    assert hourly_step == 1110


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
        count=5,
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
    assert result == [("escape_key", 5)]


def test_grouped_counts_sub_floor_rows_merge_into_sentinel(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN UI_FORM_CANCEL triggers with counts 9, 4 and 2
    WHEN grouped_count_by groups by trigger
    THEN the sub-floor rows are summed into a trailing `suppressed` pair.
    """
    app = metrics_enabled_runner_app
    window_end = _WINDOW_REFERENCE
    window_start = window_end - timedelta(days=1)
    inside = window_start + timedelta(hours=1)

    for trigger, count in (("escape_key", 9), ("cancel_button", 4), ("other", 2)):
        _insert_metric_row(
            metrics_pg_conn,
            event_name=EventName.UI_FORM_CANCEL,
            bucket_start=inside,
            dimensions={
                "form": "utub_create",
                "trigger": trigger,
                "device_type": int(DeviceType.DESKTOP),
            },
            count=count,
        )

    with app.app_context():
        result = grouped_count_by(
            event_name=EventName.UI_FORM_CANCEL,
            window_start=window_start,
            window_end=window_end,
            group_by="trigger",
        )

    assert result == [("escape_key", 9), ("suppressed", 6)]


def test_grouped_counts_api_hit_is_never_merged(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN an API_HIT row with a sub-floor count
    WHEN grouped_count_by groups by status_code
    THEN the row is returned unmerged (API_HIT is exempt from the floor).
    """
    app = metrics_enabled_runner_app
    window_end = _WINDOW_REFERENCE
    window_start = window_end - timedelta(days=1)
    inside = window_start + timedelta(hours=1)

    _insert_metric_row(
        metrics_pg_conn,
        event_name=EventName.API_HIT,
        bucket_start=inside,
        count=2,
        endpoint="urls.create_url",
        method="POST",
        status_code=201,
    )

    with app.app_context():
        result = grouped_count_by(
            event_name=EventName.API_HIT,
            window_start=window_start,
            window_end=window_end,
            group_by="status_code",
        )

    assert result == [("201", 2)]


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
        rejected by `validate_dim_keys` before any query runs.
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


@pytest.mark.parametrize(
    "event_name,group_by",
    [
        (EventName.UI_FORM_CANCEL, "form"),  # declared dim, not registered
        (EventName.UI_URL_ACCESS, "device_type"),  # event with no projection
        (EventName.API_METRICS_INGEST_BATCH, "endpoint"),  # API, not API_HIT
    ],
)
def test_grouped_count_by_unregistered_projection_raises_value_error(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
    event_name: EventName,
    group_by: str,
) -> None:
    """
    GIVEN a declared dim that is not a registered single-key projection
    WHEN grouped_count_by is called
    THEN ValueError is raised before any query result is returned.
    """
    window_end = _WINDOW_REFERENCE
    with metrics_enabled_runner_app.app_context():
        with pytest.raises(ValueError, match="not an allowed projection"):
            grouped_count_by(
                event_name=event_name,
                window_start=window_end - timedelta(days=1),
                window_end=window_end,
                group_by=group_by,
            )


def test_grouped_timeseries_unregistered_projection_raises_value_error(
    metrics_enabled_runner_app: Flask,
    metrics_pg_conn: Any,
) -> None:
    """
    GIVEN a strict subset of the Pipeline Health projection
    WHEN grouped_timeseries is called
    THEN ValueError is raised.
    """
    window_end = _WINDOW_REFERENCE
    with metrics_enabled_runner_app.app_context():
        with pytest.raises(ValueError, match="not an allowed projection"):
            grouped_timeseries(
                event_name=EventName.API_METRICS_INGEST_BATCH,
                group_by=["transport", "device_type"],
                window_start=window_end - timedelta(days=1),
                window_end=window_end,
                resolution="hour",
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


def test_validate_dim_keys_unknown_key_nonapi_event_raises() -> None:
    """
    GIVEN a non-API event
    WHEN validate_dim_keys gets an unknown filter key
    THEN ValueError names the key and the valid keys.
    """
    with pytest.raises(ValueError, match="Unknown filter/group_by key") as exc_info:
        validate_dim_keys(
            event_name=EventName.UI_FORM_CANCEL,
            dim_filter=[("nonexistent_dim", "value")],
            group_by=None,
        )
    assert "nonexistent_dim" in str(exc_info.value)


def test_validate_dim_keys_key_outside_flat_columns_api_event_raises() -> None:
    """
    GIVEN API_HIT
    WHEN validate_dim_keys gets a key outside endpoint/method/status_code
    THEN ValueError is raised.
    """
    with pytest.raises(ValueError, match="Unknown filter/group_by key"):
        validate_dim_keys(
            event_name=EventName.API_HIT,
            dim_filter=[("device_type", "2")],
            group_by=None,
        )


@pytest.mark.parametrize("event_name", (EventName.UI_FORM_CANCEL, EventName.API_HIT))
def test_validate_dim_keys_unknown_group_by_raises(event_name: EventName) -> None:
    """
    GIVEN a non-API or an API event
    WHEN validate_dim_keys gets an unknown group_by
    THEN ValueError is raised.
    """
    with pytest.raises(ValueError, match="Unknown filter/group_by key"):
        validate_dim_keys(event_name=event_name, dim_filter=[], group_by="nonexistent")


def test_validate_dim_keys_unknown_key_wins_over_nonint_value() -> None:
    """
    GIVEN API_HIT with a non-integer status_code value and an unknown key
    WHEN validate_dim_keys runs
    THEN the unknown-key ValueError is raised, not the integer one.
    """
    with pytest.raises(ValueError, match="Unknown filter/group_by key"):
        validate_dim_keys(
            event_name=EventName.API_HIT,
            dim_filter=[("status_code", "abc"), ("bogus", "x")],
            group_by=None,
        )


def test_validate_dim_keys_nonnumeric_status_code_raises() -> None:
    """
    GIVEN API_HIT with a non-numeric status_code filter value
    WHEN validate_dim_keys runs
    THEN the controlled integer message is raised.
    """
    with pytest.raises(
        ValueError, match="filter value for status_code must be an integer"
    ):
        validate_dim_keys(
            event_name=EventName.API_HIT,
            dim_filter=[("status_code", "abc")],
            group_by=None,
        )


def test_validate_dim_keys_nonnumeric_device_type_raises() -> None:
    """
    GIVEN a non-API event with a non-numeric device_type filter value
    WHEN validate_dim_keys runs
    THEN the controlled integer message is raised.
    """
    with pytest.raises(
        ValueError, match="filter value for device_type must be an integer"
    ):
        validate_dim_keys(
            event_name=EventName.UI_FORM_CANCEL,
            dim_filter=[("device_type", "phone")],
            group_by=None,
        )


def test_validate_dim_keys_valid_inputs_return_none() -> None:
    """
    GIVEN valid keys and integer values for API and non-API events
    WHEN validate_dim_keys runs
    THEN it returns None.
    """
    assert (
        validate_dim_keys(
            event_name=EventName.API_HIT,
            dim_filter=[("endpoint", "urls.create_url"), ("status_code", "200")],
            group_by="method",
        )
        is None
    )
    assert (
        validate_dim_keys(
            event_name=EventName.UI_FORM_CANCEL,
            dim_filter=[("form", "utub_create"), ("device_type", "2")],
            group_by="trigger",
        )
        is None
    )


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
