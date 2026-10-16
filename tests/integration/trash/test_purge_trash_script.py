"""Integration tests for the scripts/purge_trash.py Trash sweep.

Uses a raw psycopg2 connection (via build_pg_conn) against the test DB, mirroring
tests/integration/admin/test_purge_audit_log.py. Uses the ``runner`` fixture (not the
``app`` SAVEPOINT fixture), which would deadlock against a raw connection.

Rows are seeded with local raw-SQL helpers so ``deletedAt`` can be back-dated:
``trash_utub()`` / ``trash_utub_url()`` hardcode ``utc_now()``.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import psycopg2.errors
import pytest
from flask import Flask
from flask.testing import FlaskCliRunner

from scripts.purge_trash import (
    DELETE_UTUBS_SQL,
    PURGE_EXPIRED_URLS_SQL,
    SET_LOCK_TIMEOUT_SQL,
    TrashPurgeResult,
    run_trash_purge,
)
from scripts.trash_retention import TRASH_RETENTION_DAYS
from tests.integration.system.metrics_helpers import build_pg_conn

pytestmark = pytest.mark.trash

_SEED_PASSWORD: str = "hashed-placeholder"
_SEED_TIMESTAMP: str = "2025-01-01 00:00:00+00"


def _ago(*, days: int = 0, hours: int = 0) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days, hours=hours)


def _truncate_all(pg_conn: Any) -> None:
    with pg_conn.cursor() as cursor:
        cursor.execute(
            'TRUNCATE TABLE "Users", "Utubs", "Urls" RESTART IDENTITY CASCADE'
        )
    pg_conn.commit()


def _seed_user(pg_conn: Any, username: str) -> int:
    with pg_conn.cursor() as cursor:
        cursor.execute(
            'INSERT INTO "Users" '
            '(username, email, password, "createdAt", role, "emailValidated") '
            "VALUES (%s, %s, %s, %s, 'USER', true) RETURNING id",
            (username, f"{username}@example.com", _SEED_PASSWORD, _SEED_TIMESTAMP),
        )
        user_id: int = cursor.fetchone()[0]
    pg_conn.commit()
    return user_id


def _seed_utub(
    pg_conn: Any,
    *,
    name: str,
    creator_id: int,
    deleted_at: datetime | None = None,
    deleted_by: int | None = None,
    is_locked: bool = False,
) -> int:
    with pg_conn.cursor() as cursor:
        cursor.execute(
            'INSERT INTO "Utubs" '
            '("utubName", "utubCreator", "createdAt", "lastUpdated", '
            '"deletedAt", "deletedBy", "isLocked") '
            "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (
                name,
                creator_id,
                _SEED_TIMESTAMP,
                _SEED_TIMESTAMP,
                deleted_at,
                deleted_by,
                is_locked,
            ),
        )
        utub_id: int = cursor.fetchone()[0]
    pg_conn.commit()
    return utub_id


def _seed_member(pg_conn: Any, utub_id: int, user_id: int, role: str) -> None:
    with pg_conn.cursor() as cursor:
        cursor.execute(
            'INSERT INTO "UtubMembers" ("utubID", "userID", "memberRole") '
            "VALUES (%s, %s, %s)",
            (utub_id, user_id, role),
        )
    pg_conn.commit()


def _seed_tag(pg_conn: Any, utub_id: int, user_id: int, tag_string: str) -> int:
    with pg_conn.cursor() as cursor:
        cursor.execute(
            'INSERT INTO "UtubTags" ("tagString", "utubID", "createdBy", "createdAt") '
            "VALUES (%s, %s, %s, %s) RETURNING id",
            (tag_string, utub_id, user_id, _SEED_TIMESTAMP),
        )
        tag_id: int = cursor.fetchone()[0]
    pg_conn.commit()
    return tag_id


def _seed_url(pg_conn: Any, url_string: str, creator_id: int) -> int:
    with pg_conn.cursor() as cursor:
        cursor.execute(
            'INSERT INTO "Urls" ("urlString", "createdBy", "createdAt") '
            "VALUES (%s, %s, %s) RETURNING id",
            (url_string, creator_id, _SEED_TIMESTAMP),
        )
        url_id: int = cursor.fetchone()[0]
    pg_conn.commit()
    return url_id


def _seed_utub_url(
    pg_conn: Any,
    *,
    utub_id: int,
    url_id: int,
    user_id: int,
    deleted_at: datetime | None = None,
    deleted_by: int | None = None,
) -> int:
    with pg_conn.cursor() as cursor:
        cursor.execute(
            'INSERT INTO "UtubUrls" '
            '("utubID", "urlID", "userID", "urlTitle", "addedAt", "lastAccessed", '
            '"deletedAt", "deletedBy") '
            "VALUES (%s, %s, %s, '', %s, %s, %s, %s) RETURNING id",
            (
                utub_id,
                url_id,
                user_id,
                _SEED_TIMESTAMP,
                _SEED_TIMESTAMP,
                deleted_at,
                deleted_by,
            ),
        )
        utub_url_id: int = cursor.fetchone()[0]
    pg_conn.commit()
    return utub_url_id


def _seed_url_tag(
    pg_conn: Any, *, utub_id: int, utub_url_id: int, utub_tag_id: int, user_id: int
) -> int:
    with pg_conn.cursor() as cursor:
        cursor.execute(
            'INSERT INTO "UtubUrlTags" '
            '("utubID", "utubUrlID", "utubTagID", "userID", "addedAt") '
            "VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (utub_id, utub_url_id, utub_tag_id, user_id, _SEED_TIMESTAMP),
        )
        url_tag_id: int = cursor.fetchone()[0]
    pg_conn.commit()
    return url_tag_id


def _count(pg_conn: Any, table: str, column: str, value: int) -> int:
    with pg_conn.cursor() as cursor:
        cursor.execute(
            f'SELECT count(*) FROM "{table}" WHERE "{column}" = %s', (value,)
        )
        return cursor.fetchone()[0]


class _FailingCursor:
    """Cursor proxy that records executed SQL and raises on one chosen statement."""

    def __init__(self, cursor: Any, executed_sql: list[str], failing_sql: str) -> None:
        self._cursor = cursor
        self._executed_sql = executed_sql
        self._failing_sql = failing_sql

    def __enter__(self) -> _FailingCursor:
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self._cursor.close()

    def execute(self, sql: str, params: Any = None) -> None:
        self._executed_sql.append(sql)
        if sql == self._failing_sql:
            raise RuntimeError("simulated failure on the final purge statement")
        self._cursor.execute(sql, params)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._cursor, name)


class _FailingConnection:
    """Connection proxy whose cursors fail on ``failing_sql``; the rest is delegated."""

    def __init__(self, pg_conn: Any, failing_sql: str) -> None:
        self._pg_conn = pg_conn
        self._failing_sql = failing_sql
        self.executed_sql: list[str] = []

    def cursor(self) -> _FailingCursor:
        return _FailingCursor(
            self._pg_conn.cursor(), self.executed_sql, self._failing_sql
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._pg_conn, name)


def test_run_trash_purge_empty_returns_zero(
    runner: tuple[Flask, FlaskCliRunner],
) -> None:
    """
    GIVEN a database with no trashed rows
    WHEN run_trash_purge runs
    THEN the result is TrashPurgeResult(utubs=0, urls=0)
    """
    app, _ = runner
    pg_conn = build_pg_conn(app)
    try:
        _truncate_all(pg_conn)
        assert run_trash_purge(pg_conn=pg_conn) == TrashPurgeResult(utubs=0, urls=0)
    finally:
        pg_conn.close()


def test_purges_expired_standalone_url_in_live_utub(
    runner: tuple[Flask, FlaskCliRunner],
) -> None:
    """
    GIVEN a live UTub with one URL trashed past retention, one trashed inside it,
        and one live URL
    WHEN run_trash_purge runs
    THEN only the expired UtubUrls row (and its UtubUrlTags) is deleted, the shared
        Urls row remains, and the result is urls=1, utubs=0
    """
    app, _ = runner
    pg_conn = build_pg_conn(app)
    try:
        _truncate_all(pg_conn)
        user_id = _seed_user(pg_conn, "purge_user")
        utub_id = _seed_utub(pg_conn, name="live", creator_id=user_id)
        _seed_member(pg_conn, utub_id, user_id, "CREATOR")
        tag_id = _seed_tag(pg_conn, utub_id, user_id, "tag")

        expired_url_id = _seed_url(pg_conn, "https://expired.example.com", user_id)
        recent_url_id = _seed_url(pg_conn, "https://recent.example.com", user_id)
        live_url_id = _seed_url(pg_conn, "https://live.example.com", user_id)

        expired_utub_url_id = _seed_utub_url(
            pg_conn,
            utub_id=utub_id,
            url_id=expired_url_id,
            user_id=user_id,
            deleted_at=_ago(days=TRASH_RETENTION_DAYS, hours=1),
            deleted_by=user_id,
        )
        recent_utub_url_id = _seed_utub_url(
            pg_conn,
            utub_id=utub_id,
            url_id=recent_url_id,
            user_id=user_id,
            deleted_at=_ago(days=TRASH_RETENTION_DAYS) + timedelta(hours=1),
            deleted_by=user_id,
        )
        live_utub_url_id = _seed_utub_url(
            pg_conn, utub_id=utub_id, url_id=live_url_id, user_id=user_id
        )
        for utub_url_id in (
            expired_utub_url_id,
            recent_utub_url_id,
            live_utub_url_id,
        ):
            _seed_url_tag(
                pg_conn,
                utub_id=utub_id,
                utub_url_id=utub_url_id,
                utub_tag_id=tag_id,
                user_id=user_id,
            )

        result = run_trash_purge(pg_conn=pg_conn)

        assert result == TrashPurgeResult(utubs=0, urls=1)
        assert _count(pg_conn, "UtubUrls", "id", expired_utub_url_id) == 0
        assert _count(pg_conn, "UtubUrlTags", "utubUrlID", expired_utub_url_id) == 0
        assert _count(pg_conn, "UtubUrls", "id", recent_utub_url_id) == 1
        assert _count(pg_conn, "UtubUrls", "id", live_utub_url_id) == 1
        assert _count(pg_conn, "UtubUrlTags", "utubID", utub_id) == 2
        assert _count(pg_conn, "Urls", "id", expired_url_id) == 1
        assert _count(pg_conn, "Utubs", "id", utub_id) == 1
    finally:
        pg_conn.close()


def test_purges_expired_utub_with_all_children(
    runner: tuple[Flask, FlaskCliRunner],
) -> None:
    """
    GIVEN a UTub trashed 31 days ago with two members, a tag, a live-clock URL and
        an individually trashed URL, each with a url-tag
    WHEN run_trash_purge runs
    THEN every child row is gone without an FK error, both shared Urls rows remain,
        and the result is utubs=1, urls=2
    """
    app, _ = runner
    pg_conn = build_pg_conn(app)
    try:
        _truncate_all(pg_conn)
        creator_id = _seed_user(pg_conn, "purge_creator")
        member_id = _seed_user(pg_conn, "purge_member")
        utub_id = _seed_utub(
            pg_conn,
            name="trashed",
            creator_id=creator_id,
            deleted_at=_ago(days=31),
            deleted_by=creator_id,
        )
        _seed_member(pg_conn, utub_id, creator_id, "CREATOR")
        _seed_member(pg_conn, utub_id, member_id, "MEMBER")
        tag_id = _seed_tag(pg_conn, utub_id, creator_id, "tag")

        first_url_id = _seed_url(pg_conn, "https://first.example.com", creator_id)
        second_url_id = _seed_url(pg_conn, "https://second.example.com", creator_id)
        first_utub_url_id = _seed_utub_url(
            pg_conn, utub_id=utub_id, url_id=first_url_id, user_id=creator_id
        )
        second_utub_url_id = _seed_utub_url(
            pg_conn,
            utub_id=utub_id,
            url_id=second_url_id,
            user_id=creator_id,
            deleted_at=_ago(days=10),
            deleted_by=creator_id,
        )
        for utub_url_id in (first_utub_url_id, second_utub_url_id):
            _seed_url_tag(
                pg_conn,
                utub_id=utub_id,
                utub_url_id=utub_url_id,
                utub_tag_id=tag_id,
                user_id=creator_id,
            )

        result = run_trash_purge(pg_conn=pg_conn)

        assert result == TrashPurgeResult(utubs=1, urls=2)
        assert _count(pg_conn, "Utubs", "id", utub_id) == 0
        for table in ("UtubMembers", "UtubTags", "UtubUrls", "UtubUrlTags"):
            assert _count(pg_conn, table, "utubID", utub_id) == 0, table
        assert _count(pg_conn, "Urls", "id", first_url_id) == 1
        assert _count(pg_conn, "Urls", "id", second_url_id) == 1
    finally:
        pg_conn.close()


def test_keeps_utub_within_retention(runner: tuple[Flask, FlaskCliRunner]) -> None:
    """
    GIVEN a UTub trashed 29 days ago holding a URL trashed 10 days ago
    WHEN run_trash_purge runs
    THEN nothing is deleted
    """
    app, _ = runner
    pg_conn = build_pg_conn(app)
    try:
        _truncate_all(pg_conn)
        user_id = _seed_user(pg_conn, "keep_user")
        utub_id = _seed_utub(
            pg_conn,
            name="recent trash",
            creator_id=user_id,
            deleted_at=_ago(days=29),
            deleted_by=user_id,
        )
        _seed_member(pg_conn, utub_id, user_id, "CREATOR")
        url_id = _seed_url(pg_conn, "https://keep.example.com", user_id)
        utub_url_id = _seed_utub_url(
            pg_conn,
            utub_id=utub_id,
            url_id=url_id,
            user_id=user_id,
            deleted_at=_ago(days=10),
            deleted_by=user_id,
        )

        result = run_trash_purge(pg_conn=pg_conn)

        assert result == TrashPurgeResult(utubs=0, urls=0)
        assert _count(pg_conn, "Utubs", "id", utub_id) == 1
        assert _count(pg_conn, "UtubMembers", "utubID", utub_id) == 1
        assert _count(pg_conn, "UtubUrls", "id", utub_url_id) == 1
    finally:
        pg_conn.close()


def test_url_own_earlier_clock_expires_inside_live_trashed_utub(
    runner: tuple[Flask, FlaskCliRunner],
) -> None:
    """
    GIVEN a UTub trashed 5 days ago holding a URL individually trashed 40 days ago
        and another URL with no clock of its own
    WHEN run_trash_purge runs
    THEN only the 40-day URL is purged (the COALESCE rule); the UTub and the other
        URL stay
    """
    app, _ = runner
    pg_conn = build_pg_conn(app)
    try:
        _truncate_all(pg_conn)
        user_id = _seed_user(pg_conn, "coalesce_user")
        utub_id = _seed_utub(
            pg_conn,
            name="trashed recently",
            creator_id=user_id,
            deleted_at=_ago(days=5),
            deleted_by=user_id,
        )
        _seed_member(pg_conn, utub_id, user_id, "CREATOR")
        old_url_id = _seed_url(pg_conn, "https://old.example.com", user_id)
        other_url_id = _seed_url(pg_conn, "https://other.example.com", user_id)
        old_utub_url_id = _seed_utub_url(
            pg_conn,
            utub_id=utub_id,
            url_id=old_url_id,
            user_id=user_id,
            deleted_at=_ago(days=40),
            deleted_by=user_id,
        )
        other_utub_url_id = _seed_utub_url(
            pg_conn, utub_id=utub_id, url_id=other_url_id, user_id=user_id
        )

        result = run_trash_purge(pg_conn=pg_conn)

        assert result == TrashPurgeResult(utubs=0, urls=1)
        assert _count(pg_conn, "UtubUrls", "id", old_utub_url_id) == 0
        assert _count(pg_conn, "UtubUrls", "id", other_utub_url_id) == 1
        assert _count(pg_conn, "Utubs", "id", utub_id) == 1
    finally:
        pg_conn.close()


def test_skips_locked_utub(runner: tuple[Flask, FlaskCliRunner]) -> None:
    """
    GIVEN a locked UTub trashed 31 days ago, and a live locked UTub holding a URL
        trashed 31 days ago
    WHEN run_trash_purge runs
    THEN neither UTub nor any of their rows (members included) is touched
    """
    app, _ = runner
    pg_conn = build_pg_conn(app)
    try:
        _truncate_all(pg_conn)
        user_id = _seed_user(pg_conn, "locked_user")

        trashed_utub_id = _seed_utub(
            pg_conn,
            name="locked trashed",
            creator_id=user_id,
            deleted_at=_ago(days=31),
            deleted_by=user_id,
            is_locked=True,
        )
        _seed_member(pg_conn, trashed_utub_id, user_id, "CREATOR")
        trashed_url_id = _seed_url(pg_conn, "https://locked1.example.com", user_id)
        trashed_utub_url = _seed_utub_url(
            pg_conn, utub_id=trashed_utub_id, url_id=trashed_url_id, user_id=user_id
        )

        live_utub_id = _seed_utub(
            pg_conn, name="locked live", creator_id=user_id, is_locked=True
        )
        _seed_member(pg_conn, live_utub_id, user_id, "CREATOR")
        live_url_id = _seed_url(pg_conn, "https://locked2.example.com", user_id)
        live_locked_utub_url = _seed_utub_url(
            pg_conn,
            utub_id=live_utub_id,
            url_id=live_url_id,
            user_id=user_id,
            deleted_at=_ago(days=31),
            deleted_by=user_id,
        )

        result = run_trash_purge(pg_conn=pg_conn)

        assert result == TrashPurgeResult(utubs=0, urls=0)
        assert _count(pg_conn, "Utubs", "id", trashed_utub_id) == 1
        assert _count(pg_conn, "UtubMembers", "utubID", trashed_utub_id) == 1
        assert _count(pg_conn, "UtubUrls", "id", trashed_utub_url) == 1
        assert _count(pg_conn, "Utubs", "id", live_utub_id) == 1
        assert _count(pg_conn, "UtubUrls", "id", live_locked_utub_url) == 1
    finally:
        pg_conn.close()


def test_retention_days_override(runner: tuple[Flask, FlaskCliRunner]) -> None:
    """
    GIVEN a URL trashed 6 days ago in a live UTub
    WHEN run_trash_purge runs with retention_days=5
    THEN the URL is purged
    """
    app, _ = runner
    pg_conn = build_pg_conn(app)
    try:
        _truncate_all(pg_conn)
        user_id = _seed_user(pg_conn, "override_user")
        utub_id = _seed_utub(pg_conn, name="live", creator_id=user_id)
        _seed_member(pg_conn, utub_id, user_id, "CREATOR")
        url_id = _seed_url(pg_conn, "https://override.example.com", user_id)
        utub_url_id = _seed_utub_url(
            pg_conn,
            utub_id=utub_id,
            url_id=url_id,
            user_id=user_id,
            deleted_at=_ago(days=6),
            deleted_by=user_id,
        )

        result = run_trash_purge(pg_conn=pg_conn, retention_days=5)

        assert result == TrashPurgeResult(utubs=0, urls=1)
        assert _count(pg_conn, "UtubUrls", "id", utub_url_id) == 0
    finally:
        pg_conn.close()


@pytest.mark.parametrize("invalid_retention_days", [0, -1])
def test_rejects_retention_days_below_one_without_touching_the_database(
    runner: tuple[Flask, FlaskCliRunner], invalid_retention_days: int
) -> None:
    """
    GIVEN a UTub trashed 31 days ago and a URL trashed 31 days ago in a live UTub
    WHEN run_trash_purge runs with retention_days of 0 or a negative value
    THEN it raises ValueError before executing any statement and nothing is deleted
    """
    app, _ = runner
    pg_conn = build_pg_conn(app)
    try:
        _truncate_all(pg_conn)
        user_id = _seed_user(pg_conn, "invalid_retention_user")
        live_utub_id = _seed_utub(pg_conn, name="live", creator_id=user_id)
        _seed_member(pg_conn, live_utub_id, user_id, "CREATOR")
        url_id = _seed_url(pg_conn, "https://invalid.example.com", user_id)
        trashed_utub_url_id = _seed_utub_url(
            pg_conn,
            utub_id=live_utub_id,
            url_id=url_id,
            user_id=user_id,
            deleted_at=_ago(days=31),
            deleted_by=user_id,
        )
        trashed_utub_id = _seed_utub(
            pg_conn,
            name="trashed",
            creator_id=user_id,
            deleted_at=_ago(days=31),
            deleted_by=user_id,
        )
        _seed_member(pg_conn, trashed_utub_id, user_id, "CREATOR")
        recording_conn = _FailingConnection(pg_conn, failing_sql="")

        with pytest.raises(ValueError, match="retention_days"):
            run_trash_purge(
                pg_conn=recording_conn, retention_days=invalid_retention_days
            )

        assert recording_conn.executed_sql == []
        assert _count(pg_conn, "UtubUrls", "id", trashed_utub_url_id) == 1
        assert _count(pg_conn, "Utubs", "id", trashed_utub_id) == 1
        assert _count(pg_conn, "UtubMembers", "utubID", trashed_utub_id) == 1
    finally:
        pg_conn.close()


def test_rolls_back_every_delete_when_the_final_statement_fails(
    runner: tuple[Flask, FlaskCliRunner],
) -> None:
    """
    GIVEN a live UTub holding an expired URL (pass A) and a UTub trashed 31 days ago
        with a member (pass B), and a connection whose UTub delete raises
    WHEN run_trash_purge runs
    THEN the error is re-raised, pass A's deleted URL row is restored by the rollback,
        and the UTub and its members all still exist
    """
    app, _ = runner
    pg_conn = build_pg_conn(app)
    try:
        _truncate_all(pg_conn)
        user_id = _seed_user(pg_conn, "rollback_user")
        live_utub_id = _seed_utub(pg_conn, name="live", creator_id=user_id)
        _seed_member(pg_conn, live_utub_id, user_id, "CREATOR")
        expired_url_id = _seed_url(pg_conn, "https://rollback1.example.com", user_id)
        expired_utub_url_id = _seed_utub_url(
            pg_conn,
            utub_id=live_utub_id,
            url_id=expired_url_id,
            user_id=user_id,
            deleted_at=_ago(days=TRASH_RETENTION_DAYS, hours=1),
            deleted_by=user_id,
        )
        trashed_utub_id = _seed_utub(
            pg_conn,
            name="trashed",
            creator_id=user_id,
            deleted_at=_ago(days=31),
            deleted_by=user_id,
        )
        _seed_member(pg_conn, trashed_utub_id, user_id, "CREATOR")

        failing_conn = _FailingConnection(pg_conn, DELETE_UTUBS_SQL)
        with pytest.raises(RuntimeError, match="simulated failure"):
            run_trash_purge(pg_conn=failing_conn)

        # Pass A really ran inside the transaction before the failure.
        assert PURGE_EXPIRED_URLS_SQL in failing_conn.executed_sql
        assert _count(pg_conn, "UtubUrls", "id", expired_utub_url_id) == 1
        assert _count(pg_conn, "Utubs", "id", trashed_utub_id) == 1
        assert _count(pg_conn, "UtubMembers", "utubID", trashed_utub_id) == 1
    finally:
        pg_conn.close()


def test_sets_a_transaction_local_lock_timeout_before_any_delete(
    runner: tuple[Flask, FlaskCliRunner],
) -> None:
    """
    GIVEN a database with no trashed rows
    WHEN run_trash_purge runs
    THEN the first statement executed is the transaction-local lock_timeout, ahead of
        the pass-A delete
    """
    app, _ = runner
    pg_conn = build_pg_conn(app)
    try:
        _truncate_all(pg_conn)
        recording_conn = _FailingConnection(pg_conn, failing_sql="")

        run_trash_purge(pg_conn=recording_conn)

        assert recording_conn.executed_sql[0] == SET_LOCK_TIMEOUT_SQL
        assert recording_conn.executed_sql[1] == PURGE_EXPIRED_URLS_SQL
    finally:
        pg_conn.close()


def test_lock_wait_times_out_and_rolls_back_the_whole_purge(
    runner: tuple[Flask, FlaskCliRunner], monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    GIVEN an expired UTub whose row is locked by another open transaction, plus an
        expired URL in a live UTub (pass A) and a shortened lock timeout
    WHEN run_trash_purge runs
    THEN it raises LockNotAvailable instead of blocking, and pass A's deleted URL row
        is restored by the rollback
    """
    monkeypatch.setattr("scripts.purge_trash.LOCK_TIMEOUT_MS", 300)
    app, _ = runner
    pg_conn = build_pg_conn(app)
    blocker_conn = build_pg_conn(app)
    try:
        _truncate_all(pg_conn)
        user_id = _seed_user(pg_conn, "timeout_user")
        live_utub_id = _seed_utub(pg_conn, name="live", creator_id=user_id)
        _seed_member(pg_conn, live_utub_id, user_id, "CREATOR")
        url_id = _seed_url(pg_conn, "https://timeout.example.com", user_id)
        expired_utub_url_id = _seed_utub_url(
            pg_conn,
            utub_id=live_utub_id,
            url_id=url_id,
            user_id=user_id,
            deleted_at=_ago(days=TRASH_RETENTION_DAYS, hours=1),
            deleted_by=user_id,
        )
        trashed_utub_id = _seed_utub(
            pg_conn,
            name="contended",
            creator_id=user_id,
            deleted_at=_ago(days=31),
            deleted_by=user_id,
        )
        _seed_member(pg_conn, trashed_utub_id, user_id, "CREATOR")

        with blocker_conn.cursor() as blocker_cursor:
            blocker_cursor.execute(
                'SELECT id FROM "Utubs" WHERE id = %s FOR UPDATE', (trashed_utub_id,)
            )

        with pytest.raises(psycopg2.errors.LockNotAvailable):
            run_trash_purge(pg_conn=pg_conn)

        blocker_conn.rollback()
        assert _count(pg_conn, "UtubUrls", "id", expired_utub_url_id) == 1
        assert _count(pg_conn, "Utubs", "id", trashed_utub_id) == 1
    finally:
        blocker_conn.close()
        pg_conn.close()
