"""Standalone expired short-link purge.

Invoked once per day by cron in the workflow sidecar container. Hard-deletes
every ``ShortLinks`` row whose ``expiresAt`` has passed. An expired link already
resolves to the dead-link 404 page, so the sweep only keeps the table small and
removes stale bearer codes; it deliberately skips no UTub (not even admin-locked
or trashed ones) because an expired link is not content.

Has no Flask/SQLAlchemy dependency — only ``psycopg2`` is imported, matching
the ``purge_audit_log.py`` workflow-venv precedent.
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
logger = logging.getLogger("short_link_purge")

CONTAINER_ENVIRONMENT_FILE: str = "/app/container_environment"

# ``<=`` matches Short_Links.is_expired() (``now >= expires_at``).
DELETE_SQL: str = 'DELETE FROM "ShortLinks" WHERE "expiresAt" <= now()'


def run_purge(*, pg_conn: psycopg2.extensions.connection) -> int:
    """Delete every expired ``ShortLinks`` row and return how many were deleted.

    Runs a single DELETE under one transaction. On any failure, rolls back and
    re-raises — there is no partial-purge state.

    Example: with rows expiring 1 day ago, exactly now, and 6 days from now,
    the first two are deleted (returns 2) and the third is retained.
    """
    try:
        with pg_conn.cursor() as cursor:
            cursor.execute(DELETE_SQL)
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
        logger.info("purged=%d elapsed_ms=%d", deleted_row_count, elapsed_ms)
        sys.exit(0)
    except Exception as purge_error:
        logger.exception("short-link purge failed: %s", purge_error)
        sys.exit(1)
    finally:
        if pg_conn_main is not None:
            try:
                pg_conn_main.close()
            except Exception:
                pass
