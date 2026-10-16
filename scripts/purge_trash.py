"""Standalone Trash retention sweep for soft-deleted UTubs and URLs.

Invoked once per day by cron in the workflow sidecar container (beside the audit-log
purge), and in-process by the admin "Purge Expired Trash" trigger. Hard-deletes trashed
rows whose effective trash clock is older than ``TRASH_RETENTION_DAYS``, so the 30-day
window the Privacy Policy promises is actually enforced.

Design notes:

* **Two passes implement the effective clock** ``COALESCE(UtubUrls.deletedAt,
  Utubs.deletedAt)``. Pass A deletes URL rows whose *own* ``deletedAt`` is past the
  cutoff (a URL trashed individually keeps its own, earlier clock even inside a trashed
  UTub). Pass B deletes expired UTubs; a URL with a NULL ``deletedAt`` inside a trashed
  UTub rides the UTub's clock and goes with it.
* **``UtubMembers`` is deleted explicitly.** It has no DB-level ``ON DELETE CASCADE``
  (only the ORM ``Utubs.members`` cascade cleans it, which raw SQL never fires). The
  other children (``UtubUrls``, ``UtubTags``, ``UtubUrlTags``) cascade off ``Utubs.id``.
* **Locked UTubs are skipped** by both passes, matching the Trash lock rule that a lock
  blocks Delete and Empty trash. Their rows are swept on the first run after an unlock.
* Shared ``Urls`` rows are kept (other UTubs may reference them). Tag counts are not
  recomputed: trashed rows never count.
* No metrics event is emitted: ``record_event`` no-ops outside a Flask app context.
* Row locks (``FOR UPDATE`` on expired UTubs; the DELETE's own row lock for URLs) make a
  concurrent restore either win cleanly or find the row gone.

Has no Flask/SQLAlchemy dependency, only ``psycopg2`` (the ``purge_audit_log.py``
workflow-venv precedent). The interval arithmetic uses the psycopg2-safe
``%s * INTERVAL '1 day'`` form (never ``INTERVAL %s`` with a string parameter, which
raises).
"""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path
from typing import NamedTuple

import psycopg2
import psycopg2.extensions

from scripts.trash_retention import TRASH_RETENTION_DAYS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("trash_purge")

CONTAINER_ENVIRONMENT_FILE: str = "/app/container_environment"

# ``now()`` is fixed for the whole transaction, so every statement agrees on the cutoff.
_CUTOFF: str = "now() - %s * INTERVAL '1 day'"

PURGE_EXPIRED_URLS_SQL: str = (
    'DELETE FROM "UtubUrls" AS u USING "Utubs" AS t '
    'WHERE u."utubID" = t.id '
    'AND u."deletedAt" IS NOT NULL '
    f'AND u."deletedAt" < {_CUTOFF} '
    'AND t."isLocked" = false'
)

SELECT_EXPIRED_UTUBS_SQL: str = (
    'SELECT id FROM "Utubs" '
    'WHERE "deletedAt" IS NOT NULL '
    f'AND "deletedAt" < {_CUTOFF} '
    'AND "isLocked" = false '
    "FOR UPDATE"
)

COUNT_UTUB_URLS_SQL: str = 'SELECT count(*) FROM "UtubUrls" WHERE "utubID" = ANY(%s)'

DELETE_UTUB_MEMBERS_SQL: str = 'DELETE FROM "UtubMembers" WHERE "utubID" = ANY(%s)'

DELETE_UTUBS_SQL: str = 'DELETE FROM "Utubs" WHERE id = ANY(%s)'


class TrashPurgeResult(NamedTuple):
    utubs: int
    urls: int


def run_trash_purge(
    *,
    pg_conn: psycopg2.extensions.connection,
    retention_days: int = TRASH_RETENTION_DAYS,
) -> TrashPurgeResult:
    """Hard-delete every unlocked trashed URL and UTub past ``retention_days`` days.

    Runs both passes in one transaction and returns how many UTubs and URL rows were
    deleted (URLs cascaded with an expired UTub are included). On any failure, rolls
    back and re-raises, so there is no partial-purge state.

    Example: with ``retention_days=30``, a URL trashed 31 days ago is deleted and one
    trashed 29 days ago is kept; a UTub trashed 31 days ago is deleted with its members,
    tags and URLs, unless it is admin-locked.
    """
    try:
        with pg_conn.cursor() as cursor:
            cursor.execute(PURGE_EXPIRED_URLS_SQL, (retention_days,))
            purged_urls = cursor.rowcount

            cursor.execute(SELECT_EXPIRED_UTUBS_SQL, (retention_days,))
            expired_utub_ids = [row[0] for row in cursor.fetchall()]
            if expired_utub_ids:
                cursor.execute(COUNT_UTUB_URLS_SQL, (expired_utub_ids,))
                purged_urls += cursor.fetchone()[0]
                cursor.execute(DELETE_UTUB_MEMBERS_SQL, (expired_utub_ids,))
                cursor.execute(DELETE_UTUBS_SQL, (expired_utub_ids,))
        pg_conn.commit()
    except Exception:
        try:
            pg_conn.rollback()
        except Exception as rollback_error:
            logger.warning("trash purge rollback failed: %s", rollback_error)
        raise
    return TrashPurgeResult(utubs=len(expired_utub_ids), urls=purged_urls)


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
        purge_result = run_trash_purge(pg_conn=pg_conn_main)
        elapsed_ms = int((time.time() - started_at) * 1000)
        logger.info(
            "purged_utubs=%d purged_urls=%d retention_days=%d elapsed_ms=%d",
            purge_result.utubs,
            purge_result.urls,
            TRASH_RETENTION_DAYS,
            elapsed_ms,
        )
        sys.exit(0)
    except Exception as purge_error:
        logger.exception("trash purge failed: %s", purge_error)
        sys.exit(1)
    finally:
        if pg_conn_main is not None:
            try:
                pg_conn_main.close()
            except Exception:
                pass
