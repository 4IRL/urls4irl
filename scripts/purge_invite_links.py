"""Standalone nightly purge of long-dead UTub invite links.

Invoked once per day by cron in the workflow sidecar container. Hard-deletes
``UtubInviteLinks`` rows that have been dead (revoked, or unrevoked and expired) for
longer than ``INVITE_LINK_PURGE_RETENTION_DAYS``.

Design notes:

* **A row any acceptance references is never deleted.** ``UtubInviteAcceptances.inviteID``
  is ``ON DELETE CASCADE``, so an unguarded delete would silently wipe the join audit
  trail; the ``NOT EXISTS`` guard keeps those rows.
* ``EmailValidations.pendingInviteID`` is ``ON DELETE SET NULL``, so a pending signup that
  referenced a purged link just loses the reference and lands on ``/home``.
* No metrics event is emitted: ``record_event`` no-ops outside a Flask app context.

Has no Flask/SQLAlchemy dependency, only ``psycopg2`` (the workflow venv has only
``redis`` and ``psycopg2-binary``). The interval arithmetic uses the psycopg2-safe
``%s * INTERVAL '1 day'`` form (never ``INTERVAL %s`` with a string parameter).
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
logger = logging.getLogger("invite_link_purge")

CONTAINER_ENVIRONMENT_FILE: str = "/app/container_environment"

INVITE_LINK_PURGE_RETENTION_DAYS: int = 30

# Bounds how long the DELETE waits on a row lock held by another transaction.
LOCK_TIMEOUT_MS: int = 30_000

SET_LOCK_TIMEOUT_SQL: str = "SET LOCAL lock_timeout = %s"

# ``now()`` is fixed for the whole transaction.
_CUTOFF: str = "now() - %(days)s * INTERVAL '1 day'"

PURGE_DEAD_INVITE_LINKS_SQL: str = (
    'DELETE FROM "UtubInviteLinks" l '
    f'WHERE (l."revokedAt" < {_CUTOFF} '
    f'OR (l."revokedAt" IS NULL AND l."expiresAt" < {_CUTOFF})) '
    'AND NOT EXISTS (SELECT 1 FROM "UtubInviteAcceptances" a WHERE a."inviteID" = l.id)'
)


def run_purge(
    *,
    pg_conn: psycopg2.extensions.connection,
    retention_days: int = INVITE_LINK_PURGE_RETENTION_DAYS,
) -> int:
    """Delete invite links dead for more than ``retention_days`` days; return the count.

    Runs in one transaction; on any failure, rolls back and re-raises.

    Raises:
        ValueError: ``retention_days`` is below 1, checked before touching the DB.
    """
    if retention_days < 1:
        raise ValueError(f"retention_days must be at least 1, got {retention_days}")
    try:
        with pg_conn.cursor() as cursor:
            cursor.execute(SET_LOCK_TIMEOUT_SQL, (LOCK_TIMEOUT_MS,))
            cursor.execute(PURGE_DEAD_INVITE_LINKS_SQL, {"days": retention_days})
            purged: int = cursor.rowcount
        pg_conn.commit()
    except Exception:
        try:
            pg_conn.rollback()
        except Exception as rollback_error:
            logger.warning("invite link purge rollback failed: %s", rollback_error)
        raise
    return purged


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
        purged_count = run_purge(pg_conn=pg_conn_main)
        elapsed_ms = int((time.time() - started_at) * 1000)
        logger.info(
            "purged=%d retention_days=%d elapsed_ms=%d",
            purged_count,
            INVITE_LINK_PURGE_RETENTION_DAYS,
            elapsed_ms,
        )
        sys.exit(0)
    except Exception as purge_error:
        logger.exception("invite link purge failed: %s", purge_error)
        sys.exit(1)
    finally:
        if pg_conn_main is not None:
            try:
                pg_conn_main.close()
            except Exception as close_error:
                logger.warning("connection close failed: %s", close_error)
