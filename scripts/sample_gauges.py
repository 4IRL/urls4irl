"""Standalone Postgres -> Postgres gauge sampler for anonymous metrics.

Invoked once per hour by cron in the workflow sidecar container. Runs each
gauge's generated aggregate SQL against the relational tables and writes one
``AnonymousGauges`` row per gauge per run (a point-in-time snapshot). Has no
Flask/SQLAlchemy dependency — only ``psycopg2`` (and optionally ``redis`` for a
best-effort liveness sentinel) are imported.

The gauge definitions and per-gauge SQL come from ``backend/metrics/gauges.py``,
a pure leaf module side-loaded by absolute path via ``_load_module_direct`` (the
same pattern ``flush_metrics.py`` uses for its leaf modules). ``gauges.py``
imports no Flask/SQLAlchemy/``EventName``, so side-loading it in the
``redis``+``psycopg2``-only workflow venv does not crash.

Atomicity note: every gauge row for one run shares a single ``sampled_at``
timestamp and is inserted in one ``execute_values`` batch under one
transaction. On any failure the whole batch is rolled back and the run fails
(non-zero exit) — there is no partial-sample state.
"""

from __future__ import annotations

import importlib.util
import logging
import os
import sys
import time
from datetime import datetime, timezone
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
logger = logging.getLogger("metrics_gauge")


def _load_module_direct(module_name: str, file_relative_to_app: str) -> ModuleType:
    """Load a backend leaf module without triggering ``backend/__init__.py``.

    The workflow venv ships only ``redis`` and ``psycopg2`` — no Flask — so a
    normal ``from backend.metrics.gauges import ...`` would execute
    ``backend/__init__.py`` (which imports Flask) and raise. Side-loading the
    leaf file by absolute path bypasses package import entirely. Probes
    ``/app/<rel>`` first (workflow container layout) then
    ``<project_root>/<rel>`` (pytest layout).

    Registers the module in ``sys.modules`` *before* ``exec_module`` so a frozen
    dataclass defined under ``from __future__ import annotations`` (as in
    ``gauges.py``) can resolve its own module during class creation — without
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


_gauges_module = _load_module_direct("_metrics_gauges", "backend/metrics/gauges.py")
_metrics_strs_module = _load_module_direct(
    "_metrics_strs", "backend/utils/strings/metrics_strs.py"
)
_notify_module = _load_module_direct("_notify", "scripts/notify.py")
GaugeName = _gauges_module.GaugeName
GAUGE_REGISTRY = _gauges_module.GAUGE_REGISTRY
build_gauge_sql = _gauges_module.build_gauge_sql
value_column_for = _gauges_module.value_column_for
METRICS_REDIS = _metrics_strs_module.METRICS_REDIS
build_message = _notify_module.build_message
send = _notify_module.send
resolve_notification_env = _notify_module.resolve_notification_env
mark_failure_and_should_notify = _notify_module.mark_failure_and_should_notify
clear_failure_and_should_notify_recovery = (
    _notify_module.clear_failure_and_should_notify_recovery
)
STATUS_FAILURE = _notify_module.STATUS_FAILURE
STATUS_RECOVERED = _notify_module.STATUS_RECOVERED

CONTAINER_ENVIRONMENT_FILE: str = "/app/container_environment"
EXECUTE_VALUES_PAGE_SIZE: int = 200

INSERT_SQL: str = (
    'INSERT INTO "AnonymousGauges" '
    '("gaugeName","sampledAt","valueInt","valueFloat","dimensions") VALUES %s'
)

# Liveness sentinel — stamped with the current epoch after a successful sample
# run for observability / `make` tooling only. The workflow container's single
# healthcheck stays check_flush_liveness.py; a dedicated gauge healthcheck is an
# explicit follow-up non-goal. Written best-effort (see _record_sample_success).
GAUGE_LAST_SUCCESS_KEY: str = METRICS_REDIS.GAUGE_LAST_SUCCESS_KEY

# Transition-throttle flag — set on the first failure of an outage and cleared
# on the first subsequent success, so Discord receives at most one failure
# message and one recovery message per outage rather than a per-run flood.
GAUGE_FAILURE_FLAG_KEY: str = "metrics:gauge:failure_notified"


def run_sample(
    *,
    pg_conn: psycopg2.extensions.connection,
    now_epoch: int,
) -> int:
    """Sample every gauge once and write one AnonymousGauges row per gauge.

    Captures a single aware-UTC ``sampled_at`` from ``now_epoch`` for the whole
    run, then for each ``GaugeName`` member executes the gauge's generated SQL,
    routes the scalar result to ``valueInt`` vs ``valueFloat`` (the other stays
    ``None``) per ``value_column_for(kind)``, and bulk-inserts every row in one
    ``execute_values`` batch under one transaction.

    Returns the number of inserted rows (always ``len(GaugeName)``). On any
    failure, calls ``rollback()`` and re-raises — there is no partial-sample
    state, since all rows share one transaction.
    """
    sampled_at = datetime.fromtimestamp(now_epoch, tz=timezone.utc)
    rows: list[tuple[object, ...]] = []
    try:
        with pg_conn.cursor() as cursor:
            for gauge_name in GaugeName:
                definition = GAUGE_REGISTRY[gauge_name]
                cursor.execute(build_gauge_sql(gauge_name))
                scalar_result = cursor.fetchone()[0]
                value_int: int | None = None
                value_float: float | None = None
                if scalar_result is not None:
                    if value_column_for(definition.kind) == "valueFloat":
                        value_float = float(scalar_result)
                    else:
                        value_int = int(scalar_result)
                rows.append(
                    (
                        gauge_name.value,
                        sampled_at,
                        value_int,
                        value_float,
                        psycopg2.extras.Json({}),
                    )
                )

            psycopg2.extras.execute_values(
                cursor,
                INSERT_SQL,
                rows,
                template=None,
                page_size=EXECUTE_VALUES_PAGE_SIZE,
            )
        pg_conn.commit()
    except Exception:
        pg_conn.rollback()
        raise
    return len(rows)


def _record_sample_success(now_epoch: int) -> None:
    """Best-effort stamp of the gauge liveness sentinel after a successful run.

    Wrapped in try/except so a transient Redis hiccup at the very end of an
    otherwise-successful sample run does not flip the whole run to failure — the
    Postgres commit has already landed. Skips silently when ``METRICS_REDIS_URI``
    is absent.
    """
    metrics_uri = os.environ.get("METRICS_REDIS_URI")
    if not metrics_uri:
        return
    try:
        redis_client = redis.Redis.from_url(metrics_uri)
        try:
            redis_client.set(GAUGE_LAST_SUCCESS_KEY, str(now_epoch))
        finally:
            redis_client.close()
    except Exception:
        logger.exception("failed to stamp gauge liveness sentinel")


def _load_env_from_container_dump(path: str = CONTAINER_ENVIRONMENT_FILE) -> None:
    """Best-effort merge of the workflow container's env dump into ``os.environ``.

    Mirrors the cron-line pattern (``set -a && . /app/container_environment &&
    set +a``) for callers that bypass cron — e.g., a manual ``docker compose
    exec workflow`` run. Parses ``KEY=value`` lines and only sets entries not
    already present in ``os.environ`` so genuine env-var overrides win. Silently
    no-ops if the file is missing.
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


def _build_pg_conn_from_env() -> psycopg2.extensions.connection:
    pg_user = os.environ.get("POSTGRES_USER")
    pg_password = os.environ.get("POSTGRES_PASSWORD")
    pg_db = os.environ.get("POSTGRES_DB")
    if not pg_user or not pg_password or not pg_db:
        _load_env_from_container_dump()
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


def _build_redis_client_from_env() -> redis.Redis:
    metrics_uri = os.environ.get("METRICS_REDIS_URI")
    if not metrics_uri:
        _load_env_from_container_dump()
        metrics_uri = os.environ.get("METRICS_REDIS_URI")
    if not metrics_uri:
        raise RuntimeError("METRICS_REDIS_URI environment variable is required")
    return redis.Redis.from_url(metrics_uri)


def run_sample_job(
    *,
    pg_conn: psycopg2.extensions.connection,
    redis_client: redis.Redis,
    now_epoch: int,
    notifier=send,
) -> int:
    """Run a gauge sample and emit transition-throttled failure/recovery alerts.

    Wraps ``run_sample`` with the Redis-flag transition logic from ``notify.py``:
    on success, stamps the best-effort liveness sentinel via
    ``_record_sample_success`` and, if a prior failure flag is cleared, sends
    exactly one ``RECOVERED`` alert; on failure, if the flag was absent, sends
    exactly one ``FAILURE`` alert carrying the error detail, then re-raises.

    The wrapper deliberately does NOT call ``logger.exception`` — it only fires
    the conditional notifier and re-raises so the exception is logged exactly
    once, by the ``__main__`` handler. The ``notifier`` default keeps production
    wiring; tests inject a spy.
    """
    try:
        sampled_rows = run_sample(pg_conn=pg_conn, now_epoch=now_epoch)
    except Exception as sample_error:
        if mark_failure_and_should_notify(redis_client, GAUGE_FAILURE_FLAG_KEY):
            production, notification_url = resolve_notification_env()
            message = build_message(
                job="GAUGE_SAMPLE",
                status=STATUS_FAILURE,
                detail=str(sample_error),
            )
            notifier(
                message,
                production=production,
                notification_url=notification_url,
            )
        raise

    _record_sample_success(now_epoch)
    if clear_failure_and_should_notify_recovery(redis_client, GAUGE_FAILURE_FLAG_KEY):
        production, notification_url = resolve_notification_env()
        message = build_message(job="GAUGE_SAMPLE", status=STATUS_RECOVERED)
        notifier(message, production=production, notification_url=notification_url)
    return sampled_rows


if __name__ == "__main__":
    started_at = time.time()
    redis_client_main: redis.Redis | None = None
    pg_conn_main: psycopg2.extensions.connection | None = None
    try:
        redis_client_main = _build_redis_client_from_env()
        pg_conn_main = _build_pg_conn_from_env()
        now_epoch_main = int(time.time())
        sampled_rows = run_sample_job(
            pg_conn=pg_conn_main,
            redis_client=redis_client_main,
            now_epoch=now_epoch_main,
        )
        elapsed_ms = int((time.time() - started_at) * 1000)
        logger.info("sampled=%d elapsed_ms=%d", sampled_rows, elapsed_ms)
        sys.exit(0)
    except Exception as sample_error:
        logger.exception("gauge sample failed: %s", sample_error)
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
