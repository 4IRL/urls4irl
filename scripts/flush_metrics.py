"""Standalone Redis -> Postgres flush worker for anonymous metrics counters.

Invoked once per minute by cron in the workflow sidecar container. SCANs the
``metrics:counter:*`` namespace, atomically reads-and-removes each counter
key with ``GETDEL``, aggregates the drained values, and bulk-UPSERTs them
into ``AnonymousMetrics``. Has no Flask/SQLAlchemy dependency — only
``redis`` and ``psycopg2`` are imported.

Atomicity note: each counter key is drained with a single ``GETDEL`` round-
trip, so any ``INCR`` landing after the ``GETDEL`` lands on a fresh key (the
counter restarts at 1) and is captured by the next flush cycle — eliminating
the silent-discard TOCTOU window of the prior GET-then-DELETE design. The
Postgres UPSERT is ``ON CONFLICT DO UPDATE``, which is row-level idempotent
in the rare event the process dies between drain and commit; the only
remaining risk is double-counting the just-drained batch on retry, which is
acceptable for hobby-grade telemetry.

Concurrency note: a Redis ``SET NX EX`` lock at the start of ``run_flush``
guarantees only one worker drains the namespace per cron tick, so an
overlapping cron firing or a hung previous run cannot double-count the same
keys into Postgres.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from pathlib import Path
from types import ModuleType

import psycopg2
import psycopg2.extras
import redis


def _load_module_direct(module_name: str, file_relative_to_app: str) -> ModuleType:
    """Load a backend leaf module without triggering ``backend/__init__.py``.

    The workflow venv ships only ``redis`` and ``psycopg2`` — no Flask — so a
    normal ``from backend.extensions.metrics.buckets import ...`` would execute
    ``backend/__init__.py`` (which imports Flask) and raise. Side-loading the
    two leaf files by absolute path bypasses package import entirely. Probes
    ``/app/<rel>`` first (workflow container layout) then
    ``<project_root>/<rel>`` (pytest layout).
    """
    candidate_paths = [
        Path("/app") / file_relative_to_app,
        Path(__file__).resolve().parent.parent / file_relative_to_app,
    ]
    for module_path in candidate_paths:
        if module_path.is_file():
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            assert spec is not None and spec.loader is not None
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    raise ImportError(
        f"Could not locate {file_relative_to_app} on disk for module {module_name}"
    )


_buckets_module = _load_module_direct(
    "_metrics_buckets", "backend/extensions/metrics/buckets.py"
)
_metrics_strs_module = _load_module_direct(
    "_metrics_strs", "backend/utils/strings/metrics_strs.py"
)
epoch_to_aware_datetime = _buckets_module.epoch_to_aware_datetime
METRICS_REDIS = _metrics_strs_module.METRICS_REDIS

REDIS_COUNTER_GLOB: str = f"{METRICS_REDIS.COUNTER_KEY_PREFIX}*"
SCAN_BATCH_SIZE: int = 500
EXECUTE_VALUES_PAGE_SIZE: int = 200

# Distributed lock so two cron firings (or a hung previous run) cannot drain
# the same counter keys concurrently and double-count them into Postgres.
# TTL of 55s is shorter than the 60s cron interval, so the lock auto-expires
# before the next firing without an explicit DELETE.
FLUSH_LOCK_KEY: str = "metrics:flush:lock"
FLUSH_LOCK_TTL_SECONDS: int = 55

# Liveness sentinel — a healthcheck script (`check_flush_liveness.py`) reads
# this key and fails the workflow container's healthcheck when it is missing
# or older than `METRICS_FLUSH_LIVENESS_THRESHOLD_SECONDS`. Set ONLY after a
# successful flush completes (including empty-flush success); never set on the
# lock-held early-exit path or on Postgres commit failure. No TTL so a long
# stretch of failures naturally ages the value out past the threshold.
FLUSH_LAST_SUCCESS_KEY: str = "metrics:flush:last_success_epoch"

UPSERT_SQL: str = """
    INSERT INTO "AnonymousMetrics"
        ("eventName", "endpoint", "method", "statusCode",
         "bucketStart", "dimensions", "count")
    VALUES %s
    ON CONFLICT ("bucketStart", "eventName", "dimensions")
    DO UPDATE SET "count" = "AnonymousMetrics"."count" + EXCLUDED."count"
"""


def parse_counter_key(key: bytes) -> tuple[int, str, dict] | None:
    """Parse a ``metrics:counter:<bucket>:<event>:<canonical_dims_json>`` key.

    Returns ``(bucket_epoch, event_name, dims_dict)`` on success, or ``None``
    if the key shape is unexpected (logged and skipped by the caller).
    """
    try:
        decoded = key.decode("utf-8")
    except UnicodeDecodeError:
        return None
    parts = decoded.split(":", 4)
    if len(parts) != 5:
        return None
    if parts[0] != "metrics" or parts[1] != "counter":
        return None
    try:
        bucket_epoch = int(parts[2])
    except ValueError:
        return None
    event_name = parts[3]
    try:
        dims = json.loads(parts[4])
    except json.JSONDecodeError:
        return None
    if not isinstance(dims, dict):
        return None
    return (bucket_epoch, event_name, dims)


def run_flush(
    *,
    redis_client: redis.Redis,
    pg_conn: psycopg2.extensions.connection,
) -> int:
    """Drain the metrics counter namespace from Redis into AnonymousMetrics.

    Acquires a Redis ``SET NX EX`` lock so concurrent cron firings cannot
    double-count the same keys; if another worker holds the lock, returns 0
    immediately without performing any Postgres writes.

    Returns the number of UPSERTed rows. On Postgres failure, calls rollback()
    and re-raises — note that the keys have already been removed by ``GETDEL``
    at this point, so the just-drained batch is lost; this matches the prior
    design's behavior on commit failure and is acceptable for hobby-grade
    telemetry. Subsequent INCRs continue on fresh keys.
    """
    lock_acquired = redis_client.set(
        FLUSH_LOCK_KEY, "1", nx=True, ex=FLUSH_LOCK_TTL_SECONDS
    )
    if not lock_acquired:
        print(
            "metrics flush: another flush is in progress, skipping",
            file=sys.stdout,
        )
        return 0

    try:
        rows: list[tuple] = []
        for raw_key in redis_client.scan_iter(
            match=REDIS_COUNTER_GLOB, count=SCAN_BATCH_SIZE
        ):
            raw_value = redis_client.getdel(raw_key)
            if raw_value is None:
                continue
            parsed = parse_counter_key(raw_key)
            if parsed is None:
                continue
            bucket_epoch, event_name, dims = parsed
            try:
                count_value = int(raw_value)
            except (TypeError, ValueError):
                continue
            bucket_start_dt = epoch_to_aware_datetime(bucket_epoch)
            if event_name == "api_hit":
                endpoint_value = dims.get("endpoint")
                method_value = dims.get("method")
                status_code_value = dims.get("status_code")
            else:
                endpoint_value = None
                method_value = None
                status_code_value = None
            rows.append(
                (
                    event_name,
                    endpoint_value,
                    method_value,
                    status_code_value,
                    bucket_start_dt,
                    psycopg2.extras.Json(dims),
                    count_value,
                )
            )

        if not rows:
            _record_flush_success(redis_client)
            return 0

        with pg_conn.cursor() as cursor:
            psycopg2.extras.execute_values(
                cursor,
                UPSERT_SQL,
                rows,
                template=None,
                page_size=EXECUTE_VALUES_PAGE_SIZE,
            )
        pg_conn.commit()

        _record_flush_success(redis_client)
        return len(rows)
    except Exception:
        pg_conn.rollback()
        raise


def _record_flush_success(redis_client: redis.Redis) -> None:
    """Stamp the liveness sentinel with the current epoch after a successful flush.

    Wrapped in try/except so a transient Redis hiccup at the very end of an
    otherwise-successful flush does not flip the whole run to failure (Postgres
    commit has already landed). The healthcheck will fail on the *next* tick if
    Redis genuinely stays down — which is the correct signal.
    """
    try:
        redis_client.set(FLUSH_LAST_SUCCESS_KEY, str(int(time.time())))
    except Exception as sentinel_error:
        print(
            f"metrics flush: failed to stamp liveness sentinel: {sentinel_error}",
            file=sys.stderr,
        )


def _build_redis_client_from_env() -> redis.Redis:
    metrics_uri = os.environ.get("METRICS_REDIS_URI")
    if not metrics_uri:
        raise RuntimeError("METRICS_REDIS_URI environment variable is required")
    return redis.Redis.from_url(metrics_uri)


def _build_pg_conn_from_env() -> psycopg2.extensions.connection:
    pg_user = os.environ.get("POSTGRES_USER")
    pg_password = os.environ.get("POSTGRES_PASSWORD")
    pg_db = os.environ.get("POSTGRES_DB")
    if not pg_user or not pg_password or not pg_db:
        raise RuntimeError(
            "POSTGRES_USER, POSTGRES_PASSWORD, and POSTGRES_DB are required"
        )
    pg_host = os.environ.get("POSTGRES_HOST", "db")
    pg_port = int(os.environ.get("POSTGRES_PORT", "5432"))
    return psycopg2.connect(
        host=pg_host,
        port=pg_port,
        user=pg_user,
        password=pg_password,
        dbname=pg_db,
    )


if __name__ == "__main__":
    started_at = time.time()
    redis_client_main: redis.Redis | None = None
    pg_conn_main: psycopg2.extensions.connection | None = None
    try:
        redis_client_main = _build_redis_client_from_env()
        pg_conn_main = _build_pg_conn_from_env()
        upserted_rows = run_flush(redis_client=redis_client_main, pg_conn=pg_conn_main)
        elapsed_ms = int((time.time() - started_at) * 1000)
        print(
            f"metrics flush: upserted={upserted_rows} elapsed_ms={elapsed_ms}",
            file=sys.stdout,
        )
        sys.exit(0)
    except Exception as flush_error:
        print(f"metrics flush failed: {flush_error}", file=sys.stderr)
        sys.exit(1)
    finally:
        if pg_conn_main is not None:
            try:
                pg_conn_main.close()
            except Exception:
                pass
        if redis_client_main is not None:
            try:
                redis_client_main.close()
            except Exception:
                pass
