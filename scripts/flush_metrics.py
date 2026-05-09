"""Standalone Redis -> Postgres flush worker for anonymous metrics counters.

Invoked once per minute by cron in the workflow sidecar container. SCANs the
``metrics:counter:*`` namespace, aggregates pending counts, bulk-UPSERTs into
``AnonymousMetrics``, and deletes the flushed Redis keys after the Postgres
commit succeeds. Has no Flask/SQLAlchemy dependency — only ``redis`` and
``psycopg2`` are imported.

Atomicity note: Postgres commit and the subsequent Redis DEL are independent
operations. If the process dies between commit and delete, the next flush
re-processes the same keys via the ``ON CONFLICT DO UPDATE`` UPSERT — the
addition is idempotent at the row level but counts may be added twice. This
is acceptable for hobby-grade telemetry.
"""

from __future__ import annotations

import sys

# Required when run from the workflow container where backend/ lives at
# /app/backend/. No-op in pytest where the project root is already on sys.path.
sys.path.insert(0, "/app")

import importlib.util  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402
from types import ModuleType  # noqa: E402

import psycopg2  # noqa: E402
import psycopg2.extras  # noqa: E402
import redis  # noqa: E402


def _load_module_direct(module_name: str, file_relative_to_app: str) -> ModuleType:
    """Load a backend submodule without triggering ``backend/__init__.py``.

    The workflow venv ships only ``redis`` and ``psycopg2`` — no Flask. Importing
    ``backend.extensions.metrics.buckets`` via the normal machinery would run
    ``backend/__init__.py`` (which imports Flask) and fail. The two helper
    modules used here are pure-Python with zero Flask deps, so we side-load
    them directly. In pytest, where Flask is on the path, the standard
    ``backend.*`` imports work — this fallback only fires under
    ``ModuleNotFoundError``.
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


try:
    from backend.extensions.metrics.buckets import epoch_to_aware_datetime  # noqa: E402
    from backend.utils.strings.metrics_strs import METRICS_REDIS  # noqa: E402
except ModuleNotFoundError:
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
DELETE_BATCH_SIZE: int = 500
EXECUTE_VALUES_PAGE_SIZE: int = 200

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

    Returns the number of UPSERTed rows. On Postgres failure, calls rollback()
    and re-raises — Redis keys are NOT deleted, guaranteeing no data loss.
    """
    try:
        flushed_keys: list[bytes] = []
        rows: list[tuple] = []
        for raw_key in redis_client.scan_iter(
            match=REDIS_COUNTER_GLOB, count=SCAN_BATCH_SIZE
        ):
            raw_value = redis_client.get(raw_key)
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
            flushed_keys.append(raw_key)

        if not rows:
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

        for batch_start in range(0, len(flushed_keys), DELETE_BATCH_SIZE):
            batch = flushed_keys[batch_start : batch_start + DELETE_BATCH_SIZE]
            redis_client.delete(*batch)

        return len(rows)
    except Exception:
        pg_conn.rollback()
        raise


def _build_redis_client_from_env() -> redis.Redis:
    redis_uri = os.environ.get("REDIS_URI")
    metrics_db = os.environ.get("METRICS_REDIS_DB")
    if not redis_uri:
        raise RuntimeError("REDIS_URI environment variable is required")
    if metrics_db is None:
        raise RuntimeError("METRICS_REDIS_DB environment variable is required")
    base, _trailing_db = redis_uri.rsplit("/", 1)
    metrics_uri = f"{base}/{metrics_db}"
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
