"""Integration tests for the purge_audit_log retention script.

Uses a raw psycopg2 connection (via build_pg_conn) against the test DB to
verify that run_purge() deletes only rows older than the configured retention
window and returns the correct deleted row count.

Uses the ``runner`` fixture (not the ``app`` SAVEPOINT fixture) to allow the
psycopg2 connection to coexist with the test DB without SAVEPOINT conflicts,
following the pattern established by tests/integration/system/test_sample_gauges.py.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from flask import Flask
from flask.testing import FlaskCliRunner

from scripts.purge_audit_log import AUDIT_LOG_RETENTION_DAYS, run_purge
from tests.integration.system.metrics_helpers import build_pg_conn

pytestmark = pytest.mark.admin

_SEED_PASSWORD = "hashed-placeholder"
_SEED_TIMESTAMP_STR = "2025-01-01 00:00:00+00"

ACTION_EXPIRED_91D = "admin.test.d91"
ACTION_EXPIRED_90D1H = "admin.test.d90h1"
ACTION_RETAINED_89D = "admin.test.d89"
ACTION_RETAINED_NOW = "admin.test.now"

_EXPECTED_RETAINED_ACTIONS: frozenset[str] = frozenset(
    {ACTION_RETAINED_89D, ACTION_RETAINED_NOW}
)
_EXPECTED_EXPIRED_ACTIONS: frozenset[str] = frozenset(
    {ACTION_EXPIRED_91D, ACTION_EXPIRED_90D1H}
)


def _truncate_audit_logs(pg_conn: Any) -> None:
    """Remove all rows from AuditLogs and restart its identity sequence."""
    with pg_conn.cursor() as cursor:
        cursor.execute('TRUNCATE TABLE "AuditLogs" RESTART IDENTITY CASCADE')
    pg_conn.commit()


def _seed_user(pg_conn: Any, username: str) -> int:
    """Insert a minimal Users row and return its id."""
    with pg_conn.cursor() as cursor:
        cursor.execute(
            'INSERT INTO "Users" '
            '(username, email, password, "createdAt", role, "emailValidated") '
            "VALUES (%s, %s, %s, %s, 'USER', true) RETURNING id",
            (
                username,
                f"{username}@example.com",
                _SEED_PASSWORD,
                _SEED_TIMESTAMP_STR,
            ),
        )
        user_id: int = cursor.fetchone()[0]
    pg_conn.commit()
    return user_id


def _seed_audit_log(
    pg_conn: Any,
    actor_id: int,
    action: str,
    created_at: datetime,
) -> int:
    """Insert one AuditLogs row with an explicit createdAt and return its id."""
    with pg_conn.cursor() as cursor:
        cursor.execute(
            'INSERT INTO "AuditLogs" ("actorId", "action", "createdAt") '
            "VALUES (%s, %s, %s) RETURNING id",
            (actor_id, action, created_at),
        )
        audit_log_id: int = cursor.fetchone()[0]
    pg_conn.commit()
    return audit_log_id


def _count_audit_log_rows(pg_conn: Any) -> int:
    """Return the total number of rows in AuditLogs."""
    with pg_conn.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) FROM "AuditLogs"')
        return cursor.fetchone()[0]


def _fetch_remaining_actions(pg_conn: Any) -> frozenset[str]:
    """Return the set of action strings currently in AuditLogs."""
    with pg_conn.cursor() as cursor:
        cursor.execute('SELECT "action" FROM "AuditLogs"')
        return frozenset(row[0] for row in cursor.fetchall())


def test_run_purge_empty_table_returns_zero(
    runner: tuple[Flask, FlaskCliRunner],
) -> None:
    """
    GIVEN an empty AuditLogs table
    WHEN run_purge is called with the default retention window
    THEN the return value is 0 and the table remains empty.
    """
    app, _ = runner
    pg_conn = build_pg_conn(app)
    try:
        _truncate_audit_logs(pg_conn)
        assert _count_audit_log_rows(pg_conn) == 0

        deleted_count = run_purge(
            pg_conn=pg_conn, retention_days=AUDIT_LOG_RETENTION_DAYS
        )

        assert deleted_count == 0
        assert _count_audit_log_rows(pg_conn) == 0
    finally:
        _truncate_audit_logs(pg_conn)
        pg_conn.close()


def test_run_purge_deletes_only_expired_rows(
    runner: tuple[Flask, FlaskCliRunner],
) -> None:
    """
    GIVEN four AuditLogs rows with createdAt values straddling the 90-day
         boundary (91 days ago, 90 days + 1 hour ago, 89 days ago, and now)
    WHEN run_purge is called with retention_days=90
    THEN the return value equals the number of out-of-window rows (2), only
         the in-window rows remain, and the remaining rows are identified by
         action — not just by count.
    """
    app, _ = runner
    pg_conn = build_pg_conn(app)
    try:
        _truncate_audit_logs(pg_conn)
        actor_id = _seed_user(pg_conn, "purge_test_actor")

        now_utc = datetime.now(timezone.utc)
        rows_to_seed: list[tuple[str, datetime]] = [
            (ACTION_EXPIRED_91D, now_utc - timedelta(days=91)),
            (ACTION_EXPIRED_90D1H, now_utc - timedelta(days=90, hours=1)),
            (ACTION_RETAINED_89D, now_utc - timedelta(days=89)),
            (ACTION_RETAINED_NOW, now_utc),
        ]
        for action, created_at in rows_to_seed:
            _seed_audit_log(
                pg_conn, actor_id=actor_id, action=action, created_at=created_at
            )

        assert _count_audit_log_rows(pg_conn) == len(rows_to_seed)

        deleted_count = run_purge(pg_conn=pg_conn, retention_days=90)

        assert deleted_count == len(_EXPECTED_EXPIRED_ACTIONS)
        remaining_actions = _fetch_remaining_actions(pg_conn)
        assert remaining_actions == _EXPECTED_RETAINED_ACTIONS
    finally:
        _truncate_audit_logs(pg_conn)
        pg_conn.close()
