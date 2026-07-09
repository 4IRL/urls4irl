"""Standalone audit-log retention purge for the admin portal.

Invoked once per day by cron in the workflow sidecar container. Deletes
``AuditLogs`` rows older than the 90-day retention window. The table stores
personal data (actor ids, target user ids, and metadata that can embed
search queries), so it must not accumulate indefinitely — see
ARCHITECTURE.md for the retention policy.

Has no Flask/SQLAlchemy dependency — only ``psycopg2`` is imported, matching
the ``flush_metrics.py`` / ``sample_gauges.py`` workflow-venv precedent.

The interval arithmetic uses the psycopg2-safe ``%s * INTERVAL '1 day'``
form (never ``INTERVAL %s`` with a string parameter, which raises).
"""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

import psycopg2
import psycopg2.extensions

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("audit_purge")

CONTAINER_ENVIRONMENT_FILE: str = "/app/container_environment"

AUDIT_LOG_RETENTION_DAYS: int = 90

DELETE_SQL: str = (
    'DELETE FROM "AuditLogs" WHERE "createdAt" < now() - %s * INTERVAL \'1 day\''
)


def run_purge(
    *,
    pg_conn: psycopg2.extensions.connection,
    retention_days: int = AUDIT_LOG_RETENTION_DAYS,
) -> int:
    """Delete every ``AuditLogs`` row older than ``retention_days`` days.

    Runs a single DELETE under one transaction and returns the number of
    deleted rows. On any failure, rolls back and re-raises — there is no
    partial-purge state.

    Example: with ``retention_days=90`` and rows created 91 and 89 days ago,
    only the 91-day-old row is deleted; the 89-day-old row is retained.
    """
    try:
        with pg_conn.cursor() as cursor:
            cursor.execute(DELETE_SQL, (retention_days,))
            deleted_rows = cursor.rowcount
        pg_conn.commit()
    except Exception:
        pg_conn.rollback()
        raise
    return deleted_rows


def _load_env_from_container_dump(path: str = CONTAINER_ENVIRONMENT_FILE) -> None:
    """Best-effort merge of the workflow container's env dump into ``os.environ``.

    Mirrors the cron-line pattern (``set -a && . /app/container_environment &&
    set +a``) for callers that bypass cron — e.g., a manual ``docker compose
    exec workflow`` run. Parses ``KEY=value`` lines and only sets entries not
    already present in ``os.environ`` so genuine env-var overrides win.
    Silently no-ops if the file is missing.
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


if __name__ == "__main__":
    started_at = time.time()
    pg_conn_main: psycopg2.extensions.connection | None = None
    try:
        pg_conn_main = _build_pg_conn_from_env()
        deleted_row_count = run_purge(pg_conn=pg_conn_main)
        elapsed_ms = int((time.time() - started_at) * 1000)
        logger.info(
            "purged=%d retention_days=%d elapsed_ms=%d",
            deleted_row_count,
            AUDIT_LOG_RETENTION_DAYS,
            elapsed_ms,
        )
        sys.exit(0)
    except Exception as purge_error:
        logger.exception("audit-log purge failed: %s", purge_error)
        sys.exit(1)
    finally:
        if pg_conn_main is not None:
            try:
                pg_conn_main.close()
            except Exception:
                pass
