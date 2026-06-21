from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from flask import Flask
from redis import Redis

from backend.metrics.events import DeviceType
from backend.metrics.latency import (
    LATENCY_ROLLUP_BACKFILL_DAYS,
    LATENCY_ROLLUP_RETENTION_DAYS,
    LatencyMetricName,
)
from backend.utils.strings.metrics_strs import METRICS_REDIS
from scripts.flush_metrics import (
    FLUSH_LAST_SUCCESS_KEY,
    FLUSH_LOCK_KEY,
    run_latency_rollup,
)
from tests.integration.system.metrics_helpers import (
    build_pg_conn,
    truncate_latency_rollup_tables,
    truncate_latency_tables,
)

pytestmark = pytest.mark.cli


_METRIC_VALUE = LatencyMetricName.API_REQUEST_DURATION.value
_ENDPOINT = "utubs.get_utub"
_METHOD = "GET"
_DEVICE_TYPE_INT = int(DeviceType.DESKTOP)
# Sorted [10, 20, ..., 100] (n=10). PostgreSQL percentile_cont interpolates at
# the fractional rank p*(n-1) = p*9:
#   p50 → rank 4.5  → between 50 and 60 → 55.0
#   p95 → rank 8.55 → between 90 and 100 → 95.5
#   p99 → rank 8.91 → between 90 and 100 → 99.1
_UNIFORM_DURATIONS = tuple(float(value) for value in range(10, 101, 10))
_UNIFORM_P50 = 55.0
_UNIFORM_P95 = 95.5
_UNIFORM_P99 = 99.1


@pytest.fixture(autouse=True)
def _release_flush_keys(provide_metrics_redis: Redis):
    """Release the flush lock, liveness sentinel, prune sentinel, and rollup
    sentinel between tests so each test starts from a clean slate.
    """
    provide_metrics_redis.delete(FLUSH_LOCK_KEY)
    provide_metrics_redis.delete(FLUSH_LAST_SUCCESS_KEY)
    provide_metrics_redis.delete(METRICS_REDIS.LATENCY_LAST_PRUNE_KEY)
    provide_metrics_redis.delete(METRICS_REDIS.LATENCY_LAST_ROLLUP_KEY)
    yield
    provide_metrics_redis.delete(FLUSH_LOCK_KEY)
    provide_metrics_redis.delete(FLUSH_LAST_SUCCESS_KEY)
    provide_metrics_redis.delete(METRICS_REDIS.LATENCY_LAST_PRUNE_KEY)
    provide_metrics_redis.delete(METRICS_REDIS.LATENCY_LAST_ROLLUP_KEY)


def _start_of_today_utc() -> datetime:
    return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)


def _completed_day_noon(days_back: int) -> datetime:
    """Return noon UTC of a completed day `days_back` days before today.

    Noon keeps the sample comfortably inside the UTC calendar day regardless of
    the psycopg2 session timezone, so the date_trunc('day', ... AT TIME ZONE
    'UTC') bucket lands on the intended day.
    """
    day_start = _start_of_today_utc() - timedelta(days=days_back)
    return day_start + timedelta(hours=12)


def _insert_raw_samples(
    pg_conn: Any,
    observed_at: datetime,
    durations: tuple[float, ...],
    endpoint: str = _ENDPOINT,
    method: str = _METHOD,
) -> None:
    with pg_conn.cursor() as cursor:
        for duration in durations:
            cursor.execute(
                'INSERT INTO "AnonymousLatencySamples"'
                ' ("metricName", "endpoint", "method", "observedAt",'
                ' "durationMs", "dimensions")'
                " VALUES (%s, %s, %s, %s, %s, %s::jsonb)",
                (
                    _METRIC_VALUE,
                    endpoint,
                    method,
                    observed_at,
                    duration,
                    json.dumps({"device_type": _DEVICE_TYPE_INT}),
                ),
            )
    pg_conn.commit()


def _insert_rollup_row(pg_conn: Any, rollup_date: Any) -> None:
    with pg_conn.cursor() as cursor:
        cursor.execute(
            'INSERT INTO "AnonymousLatencyDailyRollups"'
            ' ("metricName", "endpoint", "method", "rollupDate",'
            ' "p50Ms", "p95Ms", "p99Ms", "sampleCount", "dimensions")'
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)",
            (
                _METRIC_VALUE,
                _ENDPOINT,
                _METHOD,
                rollup_date,
                10.0,
                20.0,
                30.0,
                5,
                json.dumps({}),
            ),
        )
    pg_conn.commit()


def _select_rollup_rows(pg_conn: Any) -> list[tuple]:
    with pg_conn.cursor() as cursor:
        cursor.execute(
            'SELECT "metricName", "endpoint", "method", "rollupDate",'
            ' "p50Ms", "p95Ms", "p99Ms", "sampleCount"'
            ' FROM "AnonymousLatencyDailyRollups" ORDER BY "rollupDate"'
        )
        return cursor.fetchall()


def _count_rollup_rows(pg_conn: Any) -> int:
    with pg_conn.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) FROM "AnonymousLatencyDailyRollups"')
        return cursor.fetchone()[0]


def test_rollup_builds_one_row_per_day_with_hand_computed_percentiles(
    app: Flask,
    provide_metrics_redis: Redis,
):
    """
    GIVEN ten raw samples [10..100] in a single completed UTC day
    WHEN run_latency_rollup is invoked
    THEN one rollup row exists for that (endpoint, method, day) with the
        hand-computed p50/p95/p99 and sampleCount == 10.
    """
    pg_conn = build_pg_conn(app)
    try:
        truncate_latency_tables(pg_conn)
        truncate_latency_rollup_tables(pg_conn)
        assert _count_rollup_rows(pg_conn) == 0

        _insert_raw_samples(pg_conn, _completed_day_noon(1), _UNIFORM_DURATIONS)

        written = run_latency_rollup(
            redis_client=provide_metrics_redis, pg_conn=pg_conn
        )
        assert written == 1

        rows = _select_rollup_rows(pg_conn)
        assert len(rows) == 1
        _, endpoint, method, _, p50, p95, p99, sample_count = rows[0]
        assert endpoint == _ENDPOINT
        assert method == _METHOD
        assert float(p50) == pytest.approx(_UNIFORM_P50)
        assert float(p95) == pytest.approx(_UNIFORM_P95)
        assert float(p99) == pytest.approx(_UNIFORM_P99)
        assert sample_count == 10

        sentinel = provide_metrics_redis.get(METRICS_REDIS.LATENCY_LAST_ROLLUP_KEY)
        assert sentinel is not None
    finally:
        truncate_latency_tables(pg_conn)
        truncate_latency_rollup_tables(pg_conn)
        pg_conn.close()


def test_rollup_is_idempotent_and_merges_late_samples(
    app: Flask,
    provide_metrics_redis: Redis,
):
    """
    GIVEN three raw samples [100, 200, 300] in a completed UTC day
    WHEN run_latency_rollup runs, then runs again immediately
    THEN the sentinel guard skips the second run (no duplicate rows); after
        force-clearing the sentinel, adding a late sample [150], and re-running,
        the SAME row is UPDATED — merged ordered set [100, 150, 200, 300] (n=4)
        gives p50 = 175.0 and sampleCount == 4.
    """
    pg_conn = build_pg_conn(app)
    try:
        truncate_latency_tables(pg_conn)
        truncate_latency_rollup_tables(pg_conn)

        observed_at = _completed_day_noon(1)
        _insert_raw_samples(pg_conn, observed_at, (100.0, 200.0, 300.0))

        first_written = run_latency_rollup(
            redis_client=provide_metrics_redis, pg_conn=pg_conn
        )
        assert first_written == 1
        assert _count_rollup_rows(pg_conn) == 1
        sentinel = provide_metrics_redis.get(METRICS_REDIS.LATENCY_LAST_ROLLUP_KEY)
        assert sentinel is not None

        # Second immediate run is skipped by the sentinel guard.
        second_written = run_latency_rollup(
            redis_client=provide_metrics_redis, pg_conn=pg_conn
        )
        assert second_written == 0
        assert _count_rollup_rows(pg_conn) == 1

        # Force-clear the sentinel, add a late sample to the same day, re-run.
        provide_metrics_redis.delete(METRICS_REDIS.LATENCY_LAST_ROLLUP_KEY)
        _insert_raw_samples(pg_conn, observed_at, (150.0,))

        third_written = run_latency_rollup(
            redis_client=provide_metrics_redis, pg_conn=pg_conn
        )
        assert third_written == 1
        assert _count_rollup_rows(pg_conn) == 1

        rows = _select_rollup_rows(pg_conn)
        _, _, _, _, p50, _, _, sample_count = rows[0]
        assert float(p50) == pytest.approx(175.0)
        assert sample_count == 4
    finally:
        truncate_latency_tables(pg_conn)
        truncate_latency_rollup_tables(pg_conn)
        pg_conn.close()


def test_rollup_backfill_window_only_rolls_last_n_completed_days(
    app: Flask,
    provide_metrics_redis: Redis,
):
    """
    GIVEN raw samples across the last 4 completed UTC days (one endpoint/method)
    WHEN run_latency_rollup is invoked
    THEN exactly LATENCY_ROLLUP_BACKFILL_DAYS (3) rollup rows exist, the oldest
        of the 4 seeded days has NO rollup row, and a spot-checked bucket's p95
        matches the seeded [10..100] distribution (95.5).
    """
    pg_conn = build_pg_conn(app)
    try:
        truncate_latency_tables(pg_conn)
        truncate_latency_rollup_tables(pg_conn)

        oldest_days_back = LATENCY_ROLLUP_BACKFILL_DAYS + 1
        for days_back in range(1, oldest_days_back + 1):
            _insert_raw_samples(
                pg_conn, _completed_day_noon(days_back), _UNIFORM_DURATIONS
            )

        run_latency_rollup(redis_client=provide_metrics_redis, pg_conn=pg_conn)

        rows = _select_rollup_rows(pg_conn)
        assert len(rows) == LATENCY_ROLLUP_BACKFILL_DAYS

        rolled_dates = {row[3] for row in rows}
        oldest_seeded_date = _completed_day_noon(oldest_days_back).date()
        assert oldest_seeded_date not in rolled_dates

        # Spot-check the most recent bucket's p95 against the seeded distribution.
        _, _, _, _, _, p95, _, sample_count = rows[-1]
        assert float(p95) == pytest.approx(_UNIFORM_P95)
        assert sample_count == 10
    finally:
        truncate_latency_tables(pg_conn)
        truncate_latency_rollup_tables(pg_conn)
        pg_conn.close()


def test_rollup_prunes_rows_older_than_retention(
    app: Flask,
    provide_metrics_redis: Redis,
):
    """
    GIVEN one rollup row older than LATENCY_ROLLUP_RETENTION_DAYS
    WHEN run_latency_rollup is invoked
    THEN the stale rollup row is deleted.
    """
    pg_conn = build_pg_conn(app)
    try:
        truncate_latency_tables(pg_conn)
        truncate_latency_rollup_tables(pg_conn)

        stale_date = (
            _start_of_today_utc() - timedelta(days=LATENCY_ROLLUP_RETENTION_DAYS + 1)
        ).date()
        _insert_rollup_row(pg_conn, stale_date)
        assert _count_rollup_rows(pg_conn) == 1

        run_latency_rollup(redis_client=provide_metrics_redis, pg_conn=pg_conn)

        assert _count_rollup_rows(pg_conn) == 0
    finally:
        truncate_latency_tables(pg_conn)
        truncate_latency_rollup_tables(pg_conn)
        pg_conn.close()
