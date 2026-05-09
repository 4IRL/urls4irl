from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock

import psycopg2
import pytest
from flask import Flask
from redis import Redis

from backend.metrics.events import EVENT_CATEGORY, EVENT_DESCRIPTIONS, EventName
from backend.utils.strings.metrics_strs import METRICS_REDIS
from scripts.flush_metrics import (
    FLUSH_LAST_SUCCESS_KEY,
    FLUSH_LOCK_KEY,
    FLUSH_LOCK_TTL_SECONDS,
    run_flush,
)

pytestmark = pytest.mark.cli


_BUCKET_START_EPOCH = 1735689600  # 2025-01-01 00:00:00 UTC, hour-aligned
_BUCKET_START_DT = datetime.fromtimestamp(_BUCKET_START_EPOCH, tz=timezone.utc)


@pytest.fixture(autouse=True)
def _release_flush_lock(provide_metrics_redis: Redis):
    """Release the metrics:flush:lock and clear the liveness sentinel between
    tests so each test starts from a clean slate. Without this, the lock's 55s
    TTL would block successive flush tests within the same pytest worker, and
    a prior test's liveness stamp would pollute negative-path assertions.
    """
    provide_metrics_redis.delete(FLUSH_LOCK_KEY)
    provide_metrics_redis.delete(FLUSH_LAST_SUCCESS_KEY)
    yield
    provide_metrics_redis.delete(FLUSH_LOCK_KEY)
    provide_metrics_redis.delete(FLUSH_LAST_SUCCESS_KEY)


def _build_counter_key(bucket_epoch: int, event_value: str, dims: dict) -> str:
    canonical = json.dumps(dims, sort_keys=True, separators=(",", ":"))
    return f"{METRICS_REDIS.COUNTER_KEY_PREFIX}{bucket_epoch}:{event_value}:{canonical}"


def _seed_event_registry(pg_conn: Any, event: EventName) -> None:
    """Insert the given EventName into EventRegistry so the FK on AnonymousMetrics
    is satisfied when run_flush UPSERTs rows.
    """
    # `Enum(EventCategory, values_callable=...)` (in models/event_registry.py)
    # creates the Postgres enum using the StrEnum member values (lowercase
    # "api"/"domain"/"ui"). Writing via raw SQL must use the enum values.
    with pg_conn.cursor() as cur:
        cur.execute(
            'INSERT INTO "EventRegistry" ("name", "category", "description", "addedAt")'
            " VALUES (%s, %s, %s, NOW())"
            ' ON CONFLICT ("name") DO NOTHING',
            (event.value, EVENT_CATEGORY[event].value, EVENT_DESCRIPTIONS[event]),
        )
    pg_conn.commit()


def _build_pg_conn(app: Flask) -> Any:
    return psycopg2.connect(app.config["SQLALCHEMY_DATABASE_URI"])


def _select_metrics_rows(pg_conn: Any) -> list[tuple]:
    with pg_conn.cursor() as cur:
        cur.execute(
            'SELECT "eventName", "endpoint", "method", "statusCode",'
            ' "bucketStart", "dimensions", "count"'
            ' FROM "AnonymousMetrics" ORDER BY id'
        )
        return cur.fetchall()


def _truncate_metrics_tables(pg_conn: Any) -> None:
    with pg_conn.cursor() as cur:
        cur.execute('TRUNCATE TABLE "AnonymousMetrics" RESTART IDENTITY CASCADE')
        cur.execute('DELETE FROM "EventRegistry"')
    pg_conn.commit()


def test_flush_aggregates_single_key(
    app: Flask,
    provide_metrics_redis: Redis,
):
    """
    GIVEN a single api_hit Redis counter key with value 5
    WHEN run_flush is invoked
    THEN one AnonymousMetrics row is inserted with count=5,
        bucket_start as a UTC datetime, dimensions populated with the
        canonical JSON, and flat columns endpoint/method/status_code populated.
    """
    pg_conn = _build_pg_conn(app)
    try:
        _truncate_metrics_tables(pg_conn)
        _seed_event_registry(pg_conn, EventName.API_HIT)
        dims = {"endpoint": "/utubs", "method": "POST", "status_code": 200}
        key = _build_counter_key(_BUCKET_START_EPOCH, EventName.API_HIT.value, dims)
        provide_metrics_redis.set(key, 5)

        upserted = run_flush(redis_client=provide_metrics_redis, pg_conn=pg_conn)

        assert upserted == 1
        rows = _select_metrics_rows(pg_conn)
        assert len(rows) == 1
        event_name, endpoint, method, status_code, bucket_start, dimensions, count = (
            rows[0]
        )
        assert event_name == EventName.API_HIT.value
        assert endpoint == "/utubs"
        assert method == "POST"
        assert status_code == 200
        assert bucket_start == _BUCKET_START_DT
        assert dimensions == dims
        assert count == 5
    finally:
        _truncate_metrics_tables(pg_conn)
        pg_conn.close()


def test_flush_drains_redis_keys(
    app: Flask,
    provide_metrics_redis: Redis,
):
    """
    GIVEN counter keys present in the metrics Redis DB
    WHEN run_flush completes successfully
    THEN no metrics:counter:* keys remain in Redis.
    """
    pg_conn = _build_pg_conn(app)
    try:
        _truncate_metrics_tables(pg_conn)
        _seed_event_registry(pg_conn, EventName.API_HIT)
        key = _build_counter_key(
            _BUCKET_START_EPOCH,
            EventName.API_HIT.value,
            {"endpoint": "/x", "method": "GET", "status_code": 200},
        )
        provide_metrics_redis.set(key, 3)

        run_flush(redis_client=provide_metrics_redis, pg_conn=pg_conn)

        remaining = list(
            provide_metrics_redis.scan_iter(
                match=f"{METRICS_REDIS.COUNTER_KEY_PREFIX}*"
            )
        )
        assert remaining == []
    finally:
        _truncate_metrics_tables(pg_conn)
        pg_conn.close()


def test_flush_skips_batch_keys(
    app: Flask,
    provide_metrics_redis: Redis,
):
    """
    GIVEN both a counter key and a metrics:batch:* key in Redis
    WHEN run_flush completes
    THEN the counter key is deleted but the batch key remains
        (batch keys self-expire via TTL, never via flush).
    """
    pg_conn = _build_pg_conn(app)
    try:
        _truncate_metrics_tables(pg_conn)
        _seed_event_registry(pg_conn, EventName.API_HIT)
        counter_key = _build_counter_key(
            _BUCKET_START_EPOCH,
            EventName.API_HIT.value,
            {"endpoint": "/y", "method": "GET", "status_code": 200},
        )
        provide_metrics_redis.set(counter_key, 1)
        batch_key = f"{METRICS_REDIS.BATCH_KEY_PREFIX}abc"
        provide_metrics_redis.set(batch_key, "1", ex=120)

        run_flush(redis_client=provide_metrics_redis, pg_conn=pg_conn)

        assert provide_metrics_redis.get(counter_key) is None
        assert provide_metrics_redis.get(batch_key) == b"1"
    finally:
        _truncate_metrics_tables(pg_conn)
        pg_conn.close()


def test_flush_aggregates_multiple_keys_to_distinct_rows(
    app: Flask,
    provide_metrics_redis: Redis,
):
    """
    GIVEN three counter keys with three distinct (bucket, event, dims) triples
    WHEN run_flush is invoked
    THEN three distinct rows are inserted into AnonymousMetrics.
    """
    pg_conn = _build_pg_conn(app)
    try:
        _truncate_metrics_tables(pg_conn)
        _seed_event_registry(pg_conn, EventName.API_HIT)
        _seed_event_registry(pg_conn, EventName.UI_URL_COPY)
        keys = [
            (
                EventName.API_HIT.value,
                {"endpoint": "/a", "method": "GET", "status_code": 200},
                2,
            ),
            (
                EventName.API_HIT.value,
                {"endpoint": "/b", "method": "POST", "status_code": 201},
                4,
            ),
            (
                EventName.UI_URL_COPY.value,
                {"result": "success"},
                7,
            ),
        ]
        for event_value, dims, count in keys:
            key = _build_counter_key(_BUCKET_START_EPOCH, event_value, dims)
            provide_metrics_redis.set(key, count)

        upserted = run_flush(redis_client=provide_metrics_redis, pg_conn=pg_conn)

        assert upserted == 3
        rows = _select_metrics_rows(pg_conn)
        assert len(rows) == 3
    finally:
        _truncate_metrics_tables(pg_conn)
        pg_conn.close()


def test_flush_upserts_existing_row(
    app: Flask,
    provide_metrics_redis: Redis,
):
    """
    GIVEN an AnonymousMetrics row already exists with count=10
    WHEN run_flush is invoked with a Redis key matching the same
        (bucket, event, dims) triple with value 5
    THEN the row's count is incremented to 15 (ON CONFLICT DO UPDATE).
    """
    pg_conn = _build_pg_conn(app)
    try:
        _truncate_metrics_tables(pg_conn)
        _seed_event_registry(pg_conn, EventName.API_HIT)
        dims = {"endpoint": "/zz", "method": "GET", "status_code": 200}
        with pg_conn.cursor() as cur:
            cur.execute(
                'INSERT INTO "AnonymousMetrics"'
                ' ("eventName", "endpoint", "method", "statusCode",'
                ' "bucketStart", "dimensions", "count")'
                " VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s)",
                (
                    EventName.API_HIT.value,
                    "/zz",
                    "GET",
                    200,
                    _BUCKET_START_DT,
                    json.dumps(dims),
                    10,
                ),
            )
        pg_conn.commit()
        key = _build_counter_key(_BUCKET_START_EPOCH, EventName.API_HIT.value, dims)
        provide_metrics_redis.set(key, 5)

        run_flush(redis_client=provide_metrics_redis, pg_conn=pg_conn)

        rows = _select_metrics_rows(pg_conn)
        assert len(rows) == 1
        assert rows[0][-1] == 15
    finally:
        _truncate_metrics_tables(pg_conn)
        pg_conn.close()


def test_flush_uses_split_maxsplit_4(
    app: Flask,
    provide_metrics_redis: Redis,
):
    """
    GIVEN a counter key whose JSON dimensions segment contains a colon
    WHEN run_flush parses the key with split(":", 4)
    THEN the JSON segment is preserved intact (not split inside the JSON).
    """
    pg_conn = _build_pg_conn(app)
    try:
        _truncate_metrics_tables(pg_conn)
        _seed_event_registry(pg_conn, EventName.API_HIT)
        dims = {"endpoint": "/api/v1:foo", "method": "GET", "status_code": 200}
        key = _build_counter_key(_BUCKET_START_EPOCH, EventName.API_HIT.value, dims)
        provide_metrics_redis.set(key, 1)

        run_flush(redis_client=provide_metrics_redis, pg_conn=pg_conn)

        rows = _select_metrics_rows(pg_conn)
        assert len(rows) == 1
        assert rows[0][5] == dims
        assert rows[0][1] == "/api/v1:foo"
    finally:
        _truncate_metrics_tables(pg_conn)
        pg_conn.close()


def test_flush_promotes_api_hit_dims_to_flat_columns(
    app: Flask,
    provide_metrics_redis: Redis,
):
    """
    GIVEN a Redis counter for api_hit and one for a non-api UI event
    WHEN run_flush is invoked
    THEN the api_hit row has flat columns populated from dimensions,
        and the non-api row has NULL flat columns.
    """
    pg_conn = _build_pg_conn(app)
    try:
        _truncate_metrics_tables(pg_conn)
        _seed_event_registry(pg_conn, EventName.API_HIT)
        _seed_event_registry(pg_conn, EventName.UI_URL_COPY)
        api_dims = {"endpoint": "/utubs", "method": "POST", "status_code": 201}
        ui_dims = {"result": "success"}
        provide_metrics_redis.set(
            _build_counter_key(_BUCKET_START_EPOCH, EventName.API_HIT.value, api_dims),
            3,
        )
        provide_metrics_redis.set(
            _build_counter_key(
                _BUCKET_START_EPOCH, EventName.UI_URL_COPY.value, ui_dims
            ),
            1,
        )

        run_flush(redis_client=provide_metrics_redis, pg_conn=pg_conn)

        rows_by_event = {row[0]: row for row in _select_metrics_rows(pg_conn)}
        api_row = rows_by_event[EventName.API_HIT.value]
        ui_row = rows_by_event[EventName.UI_URL_COPY.value]
        assert api_row[1] == "/utubs"
        assert api_row[2] == "POST"
        assert api_row[3] == 201
        assert ui_row[1] is None
        assert ui_row[2] is None
        assert ui_row[3] is None
    finally:
        _truncate_metrics_tables(pg_conn)
        pg_conn.close()


def test_flush_handles_empty_redis_no_op(
    app: Flask,
    provide_metrics_redis: Redis,
):
    """
    GIVEN no counter keys exist in Redis
    WHEN run_flush is invoked
    THEN it returns 0 and no rows are written to AnonymousMetrics.
    """
    pg_conn = _build_pg_conn(app)
    try:
        _truncate_metrics_tables(pg_conn)

        upserted = run_flush(redis_client=provide_metrics_redis, pg_conn=pg_conn)

        assert upserted == 0
        assert _select_metrics_rows(pg_conn) == []
    finally:
        _truncate_metrics_tables(pg_conn)
        pg_conn.close()


def test_flush_rolls_back_on_postgres_error(
    app: Flask,
    provide_metrics_redis: Redis,
):
    """
    GIVEN a MagicMock pg_conn that wraps a real psycopg2 connection but
        overrides commit() to raise (psycopg2 connection methods are
        read-only C-extension attributes, so the mock-wrapping pattern is
        used instead of patch.object)
    WHEN run_flush is invoked
    THEN the exception propagates, rollback() is invoked, and no
        AnonymousMetrics rows are committed.

    Note: with the GETDEL atomic-drain design, the just-drained batch IS
    consumed before commit, so the Redis key is gone on commit failure. This
    is the documented trade-off of the GETDEL TOCTOU fix; subsequent INCRs
    continue on fresh keys and are captured by the next flush.
    """
    seeder_conn = _build_pg_conn(app)
    try:
        _truncate_metrics_tables(seeder_conn)
        _seed_event_registry(seeder_conn, EventName.API_HIT)
    finally:
        seeder_conn.close()

    dims = {"endpoint": "/zz", "method": "GET", "status_code": 200}
    key = _build_counter_key(_BUCKET_START_EPOCH, EventName.API_HIT.value, dims)
    provide_metrics_redis.set(key, 4)

    real_conn = _build_pg_conn(app)
    try:
        # Wrap the real connection in a MagicMock so commit() can be
        # overridden (psycopg2's connection.commit is a read-only C-method
        # and cannot be patched directly via patch.object). cursor() and
        # rollback() delegate to the live connection so execute_values has
        # a real cursor/encoding chain to build the INSERT against.
        mock_pg_conn = MagicMock(wraps=real_conn)
        mock_pg_conn.commit.side_effect = RuntimeError("simulated postgres failure")

        with pytest.raises(RuntimeError, match="simulated postgres failure"):
            run_flush(redis_client=provide_metrics_redis, pg_conn=mock_pg_conn)

        mock_pg_conn.commit.assert_called_once()
        mock_pg_conn.rollback.assert_called()

        # Use a fresh connection because the wrapped one had its transaction
        # rolled back via the mock; verify no AnonymousMetrics rows landed.
        verify_conn = _build_pg_conn(app)
        try:
            with verify_conn.cursor() as cur:
                cur.execute('SELECT COUNT(*) FROM "AnonymousMetrics"')
                assert cur.fetchone()[0] == 0
        finally:
            verify_conn.close()
    finally:
        cleanup_conn = _build_pg_conn(app)
        try:
            _truncate_metrics_tables(cleanup_conn)
        finally:
            cleanup_conn.close()
        real_conn.close()


def test_flush_getdel_captures_concurrent_incr_in_next_cycle(
    app: Flask,
    provide_metrics_redis: Redis,
):
    """
    GIVEN a counter key that is INCRd after run_flush completes its GETDEL
        but before the next cycle starts (simulating a concurrent INCR that
        would have been silently discarded by the prior GET-then-DELETE
        design)
    WHEN run_flush is invoked a second time
    THEN the post-GETDEL INCR is captured as a fresh key and UPSERTed,
        proving the atomic GETDEL eliminates the silent-discard window.
    """
    pg_conn = _build_pg_conn(app)
    try:
        _truncate_metrics_tables(pg_conn)
        _seed_event_registry(pg_conn, EventName.API_HIT)
        dims = {"endpoint": "/concurrent", "method": "GET", "status_code": 200}
        key = _build_counter_key(_BUCKET_START_EPOCH, EventName.API_HIT.value, dims)

        # First flush drains an initial counter value of 3.
        provide_metrics_redis.set(key, 3)
        first_upserted = run_flush(redis_client=provide_metrics_redis, pg_conn=pg_conn)
        assert first_upserted == 1

        # An INCR landing AFTER the GETDEL lands on a fresh key (counter
        # restarts at 1). This is exactly the case the prior GET-then-DELETE
        # design would have silently discarded.
        provide_metrics_redis.incr(key)

        # The first run_flush left the lock in place (TTL 55s); release it so
        # the second simulated cron firing can acquire it. In production the
        # 55s TTL expires before the next 60s cron tick.
        provide_metrics_redis.delete(FLUSH_LOCK_KEY)

        # Second flush captures the post-GETDEL increment and UPSERTs it,
        # adding to the existing row (count: 3 + 1 = 4).
        second_upserted = run_flush(redis_client=provide_metrics_redis, pg_conn=pg_conn)
        assert second_upserted == 1

        rows = _select_metrics_rows(pg_conn)
        assert len(rows) == 1
        assert rows[0][-1] == 4
    finally:
        _truncate_metrics_tables(pg_conn)
        pg_conn.close()


def test_flush_lock_prevents_concurrent_double_count(
    app: Flask,
    provide_metrics_redis: Redis,
):
    """
    GIVEN the metrics:flush:lock key is already held by a simulated other
        worker
    WHEN run_flush is invoked
    THEN it returns 0 without performing any GETDELs or Postgres writes,
        the counter key remains intact, and no AnonymousMetrics rows are
        inserted.
    """
    pg_conn = _build_pg_conn(app)
    try:
        _truncate_metrics_tables(pg_conn)
        _seed_event_registry(pg_conn, EventName.API_HIT)
        dims = {"endpoint": "/locked", "method": "GET", "status_code": 200}
        key = _build_counter_key(_BUCKET_START_EPOCH, EventName.API_HIT.value, dims)
        provide_metrics_redis.set(key, 9)

        # Pre-acquire the lock to simulate a hung previous run (or an
        # overlapping cron firing that is still mid-drain).
        provide_metrics_redis.set(FLUSH_LOCK_KEY, "1", ex=FLUSH_LOCK_TTL_SECONDS)

        upserted = run_flush(redis_client=provide_metrics_redis, pg_conn=pg_conn)

        assert upserted == 0
        # Counter key is untouched — the locked-out worker must NOT GETDEL.
        assert provide_metrics_redis.get(key) == b"9"
        # No rows committed.
        assert _select_metrics_rows(pg_conn) == []
    finally:
        provide_metrics_redis.delete(FLUSH_LOCK_KEY)
        _truncate_metrics_tables(pg_conn)
        pg_conn.close()


def test_flush_can_be_invoked_idempotently(
    app: Flask,
    provide_metrics_redis: Redis,
):
    """
    GIVEN run_flush has already drained Redis once
    WHEN it is invoked a second time with no new INCRs in between
    THEN it returns 0 upserted rows and the AnonymousMetrics row count
        is unchanged.
    """
    pg_conn = _build_pg_conn(app)
    try:
        _truncate_metrics_tables(pg_conn)
        _seed_event_registry(pg_conn, EventName.API_HIT)
        dims = {"endpoint": "/u", "method": "GET", "status_code": 200}
        key = _build_counter_key(_BUCKET_START_EPOCH, EventName.API_HIT.value, dims)
        provide_metrics_redis.set(key, 2)

        first = run_flush(redis_client=provide_metrics_redis, pg_conn=pg_conn)
        rows_after_first = _select_metrics_rows(pg_conn)

        # Release the lock between simulated cron firings so the second
        # invocation actually executes the drain path (and returns 0 because
        # Redis is empty, not because the lock blocked it).
        provide_metrics_redis.delete(FLUSH_LOCK_KEY)

        second = run_flush(redis_client=provide_metrics_redis, pg_conn=pg_conn)
        rows_after_second = _select_metrics_rows(pg_conn)

        assert first == 1
        assert second == 0
        assert rows_after_first == rows_after_second
    finally:
        _truncate_metrics_tables(pg_conn)
        pg_conn.close()


def test_flush_stamps_liveness_sentinel_after_successful_drain(
    app: Flask,
    provide_metrics_redis: Redis,
):
    """
    GIVEN a Redis counter key drained by a successful run_flush
    WHEN the function returns
    THEN metrics:flush:last_success_epoch is set in Redis to the current
        epoch (within ~5 seconds of int(time.time())).
    """
    pg_conn = _build_pg_conn(app)
    try:
        _truncate_metrics_tables(pg_conn)
        _seed_event_registry(pg_conn, EventName.API_HIT)
        dims = {"endpoint": "/live", "method": "GET", "status_code": 200}
        key = _build_counter_key(_BUCKET_START_EPOCH, EventName.API_HIT.value, dims)
        provide_metrics_redis.set(key, 1)

        before_epoch = int(time.time())
        run_flush(redis_client=provide_metrics_redis, pg_conn=pg_conn)
        after_epoch = int(time.time())

        raw_sentinel = provide_metrics_redis.get(FLUSH_LAST_SUCCESS_KEY)
        assert raw_sentinel is not None
        stamped_epoch = int(raw_sentinel)
        assert before_epoch <= stamped_epoch <= after_epoch
    finally:
        _truncate_metrics_tables(pg_conn)
        pg_conn.close()


def test_flush_stamps_liveness_sentinel_on_empty_drain(
    app: Flask,
    provide_metrics_redis: Redis,
):
    """
    GIVEN no counter keys in Redis
    WHEN run_flush is invoked (early-returns 0 with no Postgres write)
    THEN the liveness sentinel IS still stamped — an empty flush is a
        successful flush and the worker is making progress.
    """
    pg_conn = _build_pg_conn(app)
    try:
        _truncate_metrics_tables(pg_conn)

        before_epoch = int(time.time())
        upserted = run_flush(redis_client=provide_metrics_redis, pg_conn=pg_conn)
        after_epoch = int(time.time())

        assert upserted == 0
        raw_sentinel = provide_metrics_redis.get(FLUSH_LAST_SUCCESS_KEY)
        assert raw_sentinel is not None
        stamped_epoch = int(raw_sentinel)
        assert before_epoch <= stamped_epoch <= after_epoch
    finally:
        _truncate_metrics_tables(pg_conn)
        pg_conn.close()


def test_flush_does_not_stamp_liveness_sentinel_on_postgres_commit_failure(
    app: Flask,
    provide_metrics_redis: Redis,
):
    """
    GIVEN run_flush has rows to upsert and Postgres commit() raises
    WHEN run_flush propagates the exception
    THEN metrics:flush:last_success_epoch is NOT set in Redis — the
        healthcheck must NOT report success when commits are failing.
    """
    seeder_conn = _build_pg_conn(app)
    try:
        _truncate_metrics_tables(seeder_conn)
        _seed_event_registry(seeder_conn, EventName.API_HIT)
    finally:
        seeder_conn.close()

    dims = {"endpoint": "/fail", "method": "GET", "status_code": 200}
    key = _build_counter_key(_BUCKET_START_EPOCH, EventName.API_HIT.value, dims)
    provide_metrics_redis.set(key, 4)

    real_conn = _build_pg_conn(app)
    try:
        mock_pg_conn = MagicMock(wraps=real_conn)
        mock_pg_conn.commit.side_effect = RuntimeError("simulated postgres failure")

        with pytest.raises(RuntimeError, match="simulated postgres failure"):
            run_flush(redis_client=provide_metrics_redis, pg_conn=mock_pg_conn)

        assert provide_metrics_redis.get(FLUSH_LAST_SUCCESS_KEY) is None
    finally:
        cleanup_conn = _build_pg_conn(app)
        try:
            _truncate_metrics_tables(cleanup_conn)
        finally:
            cleanup_conn.close()
        real_conn.close()


def test_flush_does_not_stamp_liveness_sentinel_when_lock_held(
    app: Flask,
    provide_metrics_redis: Redis,
):
    """
    GIVEN the metrics:flush:lock key is already held (simulating a hung or
        overlapping worker)
    WHEN run_flush is invoked
    THEN it returns 0 without stamping the liveness sentinel — being
        locked-out is NOT progress; another worker must succeed for the
        sentinel to advance.
    """
    pg_conn = _build_pg_conn(app)
    try:
        _truncate_metrics_tables(pg_conn)
        provide_metrics_redis.set(FLUSH_LOCK_KEY, "1", ex=FLUSH_LOCK_TTL_SECONDS)

        upserted = run_flush(redis_client=provide_metrics_redis, pg_conn=pg_conn)

        assert upserted == 0
        assert provide_metrics_redis.get(FLUSH_LAST_SUCCESS_KEY) is None
    finally:
        provide_metrics_redis.delete(FLUSH_LOCK_KEY)
        _truncate_metrics_tables(pg_conn)
        pg_conn.close()
