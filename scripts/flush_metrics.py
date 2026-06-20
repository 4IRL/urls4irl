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

from collections import namedtuple
import importlib.util
import json
import logging
import os
import sys
import time
from pathlib import Path
from types import ModuleType

import psycopg2
import psycopg2.extras
import redis

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("metrics_flush")


def _load_module_direct(module_name: str, file_relative_to_app: str) -> ModuleType:
    """Load a backend leaf module without triggering ``backend/__init__.py``.

    The workflow venv ships only ``redis`` and ``psycopg2`` — no Flask — so a
    normal ``from backend.extensions.metrics.buckets import ...`` would execute
    ``backend/__init__.py`` (which imports Flask) and raise. Side-loading the
    leaf files by absolute path bypasses package import entirely. Probes
    ``/app/<rel>`` first (workflow container layout) then
    ``<project_root>/<rel>`` (pytest layout).

    Registers the module in ``sys.modules`` *before* ``exec_module`` so a frozen
    dataclass defined under ``from __future__ import annotations`` (as in
    ``latency.py``) can resolve its own module during class creation — without
    this, ``dataclasses._is_type`` raises ``AttributeError`` for the
    side-loaded module.
    """
    candidate_paths = [
        Path("/app") / file_relative_to_app,
        Path(__file__).resolve().parent.parent / file_relative_to_app,
    ]
    for module_path in candidate_paths:
        if module_path.is_file():
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            if spec is None or spec.loader is None:
                raise ImportError(f"Could not load spec for {module_path}")
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
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
_latency_module = _load_module_direct("_metrics_latency", "backend/metrics/latency.py")
epoch_to_aware_datetime = _buckets_module.epoch_to_aware_datetime
METRICS_REDIS = _metrics_strs_module.METRICS_REDIS
LATENCY_SAMPLE_CAP_PER_BUCKET = _latency_module.LATENCY_SAMPLE_CAP_PER_BUCKET
LATENCY_RETENTION_DAYS = _latency_module.LATENCY_RETENTION_DAYS
LATENCY_PRUNE_INTERVAL_SECONDS = _latency_module.LATENCY_PRUNE_INTERVAL_SECONDS

CONTAINER_ENVIRONMENT_FILE: str = "/app/container_environment"
DEFAULT_BUCKET_SECONDS: int = 3600
EXECUTE_VALUES_PAGE_SIZE: int = 200
LATENCY_GLOB: str = f"{METRICS_REDIS.LATENCY_KEY_PREFIX}*"
REDIS_COUNTER_GLOB: str = f"{METRICS_REDIS.COUNTER_KEY_PREFIX}*"
SCAN_BATCH_SIZE: int = 500

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
# stretch of failures naturally ages the value out past the threshold. Same
# key is read by the admin dashboard's summary endpoint to surface "Last flush"
# accurately even during low-traffic stretches.
FLUSH_LAST_SUCCESS_KEY: str = METRICS_REDIS.FLUSH_LAST_SUCCESS_KEY

# Parsed latency-key fields. endpoint/method are flat key segments promoted to
# flat columns at flush; dimensions_dict holds the device-only JSONB blob.
LatencyKey = namedtuple(
    "LatencyKey",
    ["bucket_epoch", "metric_name", "endpoint", "method", "dimensions_dict"],
)

UPSERT_SQL: str = """
    INSERT INTO "AnonymousMetrics"
        ("eventName", "endpoint", "method", "statusCode",
         "bucketStart", "dimensions", "count")
    VALUES %s
    ON CONFLICT ("bucketStart", "eventName", "dimensions")
    DO UPDATE SET "count" = "AnonymousMetrics"."count" + EXCLUDED."count"
"""

# Append-only: latency samples are immutable raw observations, so there is no
# ON CONFLICT clause (mirrors the gauge INSERT_SQL shape, not the counter UPSERT).
LATENCY_INSERT_SQL: str = """
    INSERT INTO "AnonymousLatencySamples"
        ("metricName", "endpoint", "method", "observedAt",
         "durationMs", "dimensions")
    VALUES %s
"""

# Retention prune: delete samples older than the retention window. The integer
# day count is bound as a parameter and multiplied by INTERVAL '1 day' — the
# psycopg2-safe form (never `INTERVAL %s` with a string parameter, which raises
# ProgrammingError at runtime).
LATENCY_PRUNE_SQL: str = """
    DELETE FROM "AnonymousLatencySamples"
    WHERE "observedAt" < NOW() - (%s * INTERVAL '1 day')
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


def parse_latency_key(key: bytes) -> LatencyKey | None:
    """Parse a 7-segment latency list key into its flat fields.

    Key shape:
    ``metrics:latency:<bucket_epoch>:<metric_name>:<endpoint>:<method>:<canonical_device_dims_json>``

    Returns a ``LatencyKey`` on success, or ``None`` if the key shape is
    unexpected (logged and skipped by the caller). Returns ``None`` immediately
    for an orphaned ``:draining`` key — those are self-healing via EXPIRE and
    must never be parsed as fresh sample keys.

    Uses ``split(":", 6)`` (maxsplit=6) so the trailing canonical-dims JSON —
    which itself contains a colon (``{"device_type":2}``) — is captured intact
    in ``parts[6]`` rather than split apart.
    """
    try:
        decoded = key.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if decoded.endswith(":draining"):
        return None
    parts = decoded.split(":", 6)
    if len(parts) != 7:
        return None
    if parts[0] != "metrics" or parts[1] != "latency":
        return None
    try:
        bucket_epoch = int(parts[2])
    except ValueError:
        return None
    metric_name = parts[3]
    endpoint = parts[4]
    method = parts[5]
    try:
        dimensions_dict = json.loads(parts[6])
    except json.JSONDecodeError:
        return None
    if not isinstance(dimensions_dict, dict):
        return None
    return LatencyKey(bucket_epoch, metric_name, endpoint, method, dimensions_dict)


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
        logger.warning("another flush is in progress, skipping")
        return 0

    try:
        rows: list[tuple[object, ...]] = []
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
            # Latency drain + prune still run on an empty counter namespace —
            # latency lists accumulate independently of counters.
            run_latency_flush(redis_client=redis_client, pg_conn=pg_conn)
            prune_latency_samples(redis_client=redis_client, pg_conn=pg_conn)
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
        # Counter drain commits first (preserving existing behavior) so a later
        # latency INSERT failure cannot roll back already-committed counter rows.
        pg_conn.commit()

        # Latency drain + prune run inside the same lock hold but with their own
        # commits, AFTER the counter commit. _record_flush_success moves to AFTER
        # both so the sentinel only advances on a fully-successful flush cycle.
        run_latency_flush(redis_client=redis_client, pg_conn=pg_conn)
        prune_latency_samples(redis_client=redis_client, pg_conn=pg_conn)

        _record_flush_success(redis_client)
        return len(rows)
    except Exception:
        pg_conn.rollback()
        raise


def _resolve_bucket_seconds() -> int:
    """Read METRICS_BUCKET_SECONDS from the worker env, defaulting to one hour.

    The Flask-less worker has no app.config; it reads the same env var the
    writer's bucket math uses so the draining-key EXPIRE TTL grace matches the
    sample keys' bucket granularity.
    """
    try:
        return int(os.environ.get("METRICS_BUCKET_SECONDS", DEFAULT_BUCKET_SECONDS))
    except (TypeError, ValueError):
        return DEFAULT_BUCKET_SECONDS


def run_latency_flush(
    *,
    redis_client: redis.Redis,
    pg_conn: psycopg2.extensions.connection,
) -> int:
    """Drain the latency-sample lists from Redis into AnonymousLatencySamples.

    Called from ``run_flush`` AFTER the counter drain commits, inside the same
    ``metrics:flush:lock`` hold. Issues its own ``pg_conn.commit()`` so a latency
    INSERT failure cannot roll back already-committed counter rows.

    Atomic drain that does not lose concurrent LPUSHes: each key is parsed first,
    then RENAMEd to ``<key>:draining`` and EXPIREd in a single atomic pipeline.
    Because RENAME + EXPIRE are pipelined atomically, the crash window where a key
    is renamed but has no TTL does not exist — both apply or neither does. New
    LPUSHes after the RENAME recreate the original key for the next flush cycle.

    Returns the number of inserted sample rows.
    """
    bucket_seconds = _resolve_bucket_seconds()
    draining_ttl = bucket_seconds + 60
    rows: list[tuple[object, ...]] = []
    for raw_key in redis_client.scan_iter(match=LATENCY_GLOB, count=SCAN_BATCH_SIZE):
        # Orphaned draining key from a previous worker crash — self-healing via
        # EXPIRE, never re-drained here.
        if raw_key.endswith(b":draining"):
            continue
        parsed = parse_latency_key(raw_key)
        if parsed is None:
            continue
        draining_key = raw_key + b":draining"
        try:
            pipe = redis_client.pipeline()
            pipe.rename(raw_key, draining_key)
            pipe.expire(draining_key, draining_ttl)
            pipe.execute()
        except redis.ResponseError:
            # Source key expired between scan and rename — RENAME raises
            # ResponseError when the source does not exist; nothing to drain.
            continue
        drained_values = redis_client.lrange(draining_key, 0, -1)
        if len(drained_values) == LATENCY_SAMPLE_CAP_PER_BUCKET:
            logger.warning(
                "latency_sample_cap_hit: key=%s — drained exactly cap (%d) samples;"
                " older samples discarded",
                raw_key,
                LATENCY_SAMPLE_CAP_PER_BUCKET,
            )
        # observedAt is the bucket start, not the exact request instant — bucket
        # granularity is sufficient for percentile aggregation on the time axis.
        observed_at = epoch_to_aware_datetime(parsed.bucket_epoch)
        dimensions_json = psycopg2.extras.Json(parsed.dimensions_dict)
        for raw_duration in drained_values:
            try:
                duration_value = float(raw_duration)
            except (TypeError, ValueError):
                continue
            rows.append(
                (
                    parsed.metric_name,
                    parsed.endpoint,
                    parsed.method,
                    observed_at,
                    duration_value,
                    dimensions_json,
                )
            )
        redis_client.delete(draining_key)

    if not rows:
        return 0

    with pg_conn.cursor() as cursor:
        psycopg2.extras.execute_values(
            cursor,
            LATENCY_INSERT_SQL,
            rows,
            template=None,
            page_size=EXECUTE_VALUES_PAGE_SIZE,
        )
    pg_conn.commit()
    return len(rows)


def prune_latency_samples(
    *,
    redis_client: redis.Redis,
    pg_conn: psycopg2.extensions.connection,
) -> None:
    """Delete latency samples older than the retention window, at most once/day.

    Sentinel-guarded by ``metrics:prune:latency_last_epoch`` (a key under the
    ``metrics:prune:`` prefix so it can never match the ``metrics:latency:*`` drain
    glob). Runs the DELETE only if the sentinel is absent or older than
    ``LATENCY_PRUNE_INTERVAL_SECONDS``. Best-effort on the Redis sentinel reads/
    writes: a Redis hiccup is swallowed-and-logged so the prune still runs but
    won't spam, while the Postgres DELETE+commit remains the authoritative work.
    """
    now_epoch = int(time.time())
    try:
        raw_last_prune = redis_client.get(METRICS_REDIS.LATENCY_LAST_PRUNE_KEY)
    except Exception:
        logger.exception("failed to read latency prune sentinel")
        raw_last_prune = None
    if raw_last_prune is not None:
        try:
            last_prune_epoch = int(raw_last_prune)
        except (TypeError, ValueError):
            last_prune_epoch = 0
        if now_epoch - last_prune_epoch < LATENCY_PRUNE_INTERVAL_SECONDS:
            return

    with pg_conn.cursor() as cursor:
        cursor.execute(LATENCY_PRUNE_SQL, (LATENCY_RETENTION_DAYS,))
    pg_conn.commit()

    try:
        redis_client.set(METRICS_REDIS.LATENCY_LAST_PRUNE_KEY, str(now_epoch))
    except Exception:
        logger.exception("failed to stamp latency prune sentinel")


def _record_flush_success(redis_client: redis.Redis) -> None:
    """Stamp the liveness sentinel with the current epoch after a successful flush.

    Wrapped in try/except so a transient Redis hiccup at the very end of an
    otherwise-successful flush does not flip the whole run to failure (Postgres
    commit has already landed). The healthcheck will fail on the *next* tick if
    Redis genuinely stays down — which is the correct signal.
    """
    try:
        redis_client.set(FLUSH_LAST_SUCCESS_KEY, str(int(time.time())))
    except Exception:
        logger.exception("failed to stamp liveness sentinel")


def _load_env_from_container_dump(path: str = CONTAINER_ENVIRONMENT_FILE) -> None:
    """Best-effort merge of the workflow container's env dump into ``os.environ``.

    Mirrors the cron-line pattern (``set -a && . /app/container_environment &&
    set +a``) for callers that bypass cron — e.g., a manual ``docker compose
    exec workflow`` run. Parses ``KEY=value`` lines (the KEY=value format
    written by startup-workflow.sh) and only sets entries not already present
    in ``os.environ`` so genuine env-var overrides win. Silently no-ops if the
    file is missing.
    """
    dump_path = Path(path)
    if not dump_path.is_file():
        return
    try:
        for raw_line in dump_path.read_text(encoding="utf-8").splitlines():
            stripped_line = raw_line.strip()
            if not stripped_line or stripped_line.startswith("#"):
                continue
            if "=" not in stripped_line:
                continue
            key, _, value = stripped_line.partition("=")
            key = key.strip()
            if not key or key in os.environ:
                continue
            os.environ[key] = value
    except OSError:
        return


def _build_redis_client_from_env() -> redis.Redis:
    metrics_uri = os.environ.get("METRICS_REDIS_URI")
    if not metrics_uri:
        _load_env_from_container_dump()
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
        logger.info("upserted=%d elapsed_ms=%d", upserted_rows, elapsed_ms)
        sys.exit(0)
    except Exception as flush_error:
        logger.exception("flush failed: %s", flush_error)
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
