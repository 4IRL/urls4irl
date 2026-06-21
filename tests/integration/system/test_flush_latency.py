from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from flask import Flask
from redis import Redis

from backend.metrics.events import DeviceType
from backend.metrics.latency import (
    LATENCY_RAW_RETENTION_DAYS,
    LATENCY_SAMPLE_CAP_DEFAULT,
    LatencyMetricName,
)
from backend.utils.strings.metrics_strs import METRICS_REDIS
from scripts.flush_metrics import (
    FLUSH_LAST_SUCCESS_KEY,
    FLUSH_LOCK_KEY,
    parse_latency_key,
    run_flush,
)
from tests.integration.system.metrics_helpers import (
    build_latency_key,
    build_pg_conn,
    find_latency_keys,
    truncate_latency_tables,
)
from tests.utils_for_test import is_string_in_logs

pytestmark = pytest.mark.cli


# Use a current, hour-aligned bucket so drained rows fall INSIDE the retention
# window — the retention prune always runs after the drain within run_flush, and
# a far-past bucket epoch would let the prune delete the freshly-inserted rows
# before the test reads them back.
_BUCKET_START_EPOCH = (int(datetime.now(timezone.utc).timestamp()) // 3600) * 3600
_BUCKET_START_DT = datetime.fromtimestamp(_BUCKET_START_EPOCH, tz=timezone.utc)
_METRIC_VALUE = LatencyMetricName.API_REQUEST_DURATION.value
_ENDPOINT = "utubs.get_utub"
_METHOD = "GET"
_DEVICE_TYPE_INT = int(DeviceType.DESKTOP)
_PRUNE_ROW_DURATION = 42.5


@pytest.fixture(autouse=True)
def _release_flush_lock(provide_metrics_redis: Redis):
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


def _select_latency_rows(pg_conn: Any) -> list[tuple]:
    with pg_conn.cursor() as cur:
        cur.execute(
            'SELECT "metricName", "endpoint", "method", "observedAt",'
            ' "durationMs", "dimensions"'
            ' FROM "AnonymousLatencySamples" ORDER BY id'
        )
        return cur.fetchall()


def _count_latency_rows(pg_conn: Any) -> int:
    with pg_conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) FROM "AnonymousLatencySamples"')
        return cur.fetchone()[0]


def _insert_latency_row(pg_conn: Any, observed_at: datetime) -> None:
    with pg_conn.cursor() as cur:
        cur.execute(
            'INSERT INTO "AnonymousLatencySamples"'
            ' ("metricName", "endpoint", "method", "observedAt",'
            ' "durationMs", "dimensions")'
            " VALUES (%s, %s, %s, %s, %s, %s::jsonb)",
            (
                _METRIC_VALUE,
                _ENDPOINT,
                _METHOD,
                observed_at,
                _PRUNE_ROW_DURATION,
                json.dumps({"device_type": _DEVICE_TYPE_INT}),
            ),
        )
    pg_conn.commit()


def test_flush_drains_latency_samples_to_rows(
    app: Flask,
    provide_metrics_redis: Redis,
):
    """
    GIVEN a metrics:latency:* list key with three duration samples
    WHEN run_flush is invoked
    THEN three AnonymousLatencySamples rows are inserted with endpoint/method
        promoted to flat columns, device_type retained in JSONB dimensions,
        observedAt = bucket start, durationMs matching the pushed values, and
        the Redis key is drained (gone).
    """
    pg_conn = build_pg_conn(app)
    try:
        truncate_latency_tables(pg_conn)
        assert _count_latency_rows(pg_conn) == 0

        key = build_latency_key(
            _BUCKET_START_EPOCH,
            _METRIC_VALUE,
            _ENDPOINT,
            _METHOD,
            DeviceType.DESKTOP,
        )
        for duration in ("12.500", "34.000", "56.250"):
            provide_metrics_redis.lpush(key, duration)

        upserted = run_flush(redis_client=provide_metrics_redis, pg_conn=pg_conn)
        assert upserted == 0  # no counters; return value is the counter row count

        rows = _select_latency_rows(pg_conn)
        assert len(rows) == 3
        for metric_name, endpoint, method, observed_at, duration_ms, dimensions in rows:
            assert metric_name == _METRIC_VALUE
            assert endpoint == _ENDPOINT
            assert method == _METHOD
            assert observed_at == _BUCKET_START_DT
            assert dimensions == {"device_type": int(DeviceType.DESKTOP)}
        durations = sorted(float(row[4]) for row in rows)
        assert durations == [12.5, 34.0, 56.25]

        assert find_latency_keys(provide_metrics_redis, _METRIC_VALUE) == []
    finally:
        truncate_latency_tables(pg_conn)
        pg_conn.close()


def test_flush_latency_uses_split_maxsplit_6(
    app: Flask,
    provide_metrics_redis: Redis,
):
    """
    GIVEN a hand-constructed 7-segment latency key whose JSON dims contain a colon
    WHEN parse_latency_key parses it with split(":", 6)
    THEN the flat fields and the trailing JSON dims are extracted intact, and a
        :draining-suffixed key returns None.
    """
    key = (
        b"metrics:latency:1735689600:api_request_duration:"
        b'utubs.get_utub:GET:{"device_type":2}'
    )
    parsed = parse_latency_key(key)
    assert parsed is not None
    assert parsed.bucket_epoch == 1735689600
    assert parsed.metric_name == "api_request_duration"
    assert parsed.endpoint == "utubs.get_utub"
    assert parsed.method == "GET"
    assert parsed.dimensions_dict == {"device_type": 2}

    draining = key + b":draining"
    assert parse_latency_key(draining) is None


def test_flush_latency_emits_cap_warning(
    app: Flask,
    provide_metrics_redis: Redis,
    caplog: pytest.LogCaptureFixture,
):
    """
    GIVEN exactly LATENCY_SAMPLE_CAP_DEFAULT duration strings in a single
        latency list key
    WHEN run_flush drains it
    THEN exactly cap rows are inserted (not more) AND a WARNING-level
        latency_sample_cap_hit log is emitted.
    """
    pg_conn = build_pg_conn(app)
    try:
        truncate_latency_tables(pg_conn)
        assert _count_latency_rows(pg_conn) == 0

        key = build_latency_key(
            _BUCKET_START_EPOCH,
            _METRIC_VALUE,
            _ENDPOINT,
            _METHOD,
            DeviceType.DESKTOP,
        )
        for index in range(LATENCY_SAMPLE_CAP_DEFAULT):
            provide_metrics_redis.lpush(key, f"{index}.000")

        with caplog.at_level(logging.WARNING, logger="metrics_flush"):
            run_flush(redis_client=provide_metrics_redis, pg_conn=pg_conn)

        assert _count_latency_rows(pg_conn) == LATENCY_SAMPLE_CAP_DEFAULT
        assert is_string_in_logs("latency_sample_cap_hit", caplog.records)
        assert any(
            record.levelno == logging.WARNING
            and "latency_sample_cap_hit" in record.getMessage()
            for record in caplog.records
        )
    finally:
        truncate_latency_tables(pg_conn)
        pg_conn.close()


def test_flush_prunes_old_latency_rows(
    app: Flask,
    provide_metrics_redis: Redis,
):
    """
    GIVEN one AnonymousLatencySamples row older than LATENCY_RAW_RETENTION_DAYS and
        one recent row, with the prune sentinel absent (stale)
    WHEN run_flush is invoked
    THEN the old row is deleted, the recent row is retained, and the prune
        sentinel is stamped so a second immediate run does NOT re-prune.
    """
    pg_conn = build_pg_conn(app)
    try:
        truncate_latency_tables(pg_conn)
        provide_metrics_redis.delete(METRICS_REDIS.LATENCY_LAST_PRUNE_KEY)

        now = datetime.now(timezone.utc)
        old_observed = now - timedelta(days=LATENCY_RAW_RETENTION_DAYS + 1)
        recent_observed = now - timedelta(days=1)
        _insert_latency_row(pg_conn, old_observed)
        _insert_latency_row(pg_conn, recent_observed)
        assert _count_latency_rows(pg_conn) == 2

        run_flush(redis_client=provide_metrics_redis, pg_conn=pg_conn)

        rows = _select_latency_rows(pg_conn)
        assert len(rows) == 1
        retained_observed = rows[0][3]
        assert retained_observed == recent_observed

        sentinel = provide_metrics_redis.get(METRICS_REDIS.LATENCY_LAST_PRUNE_KEY)
        assert sentinel is not None
    finally:
        truncate_latency_tables(pg_conn)
        pg_conn.close()
