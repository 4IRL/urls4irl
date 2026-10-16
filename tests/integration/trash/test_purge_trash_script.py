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

import pytest
from flask import Flask
from flask.testing import FlaskCliRunner

from scripts.purge_trash import TrashPurgeResult, run_trash_purge
from scripts.trash_retention import TRASH_RETENTION_DAYS
from tests.integration.system.metrics_helpers import build_pg_conn

pytestmark = pytest.mark.trash

_SEED_PASSWORD = "hashed-placeholder"
_SEED_TIMESTAMP = "2025-01-01 00:00:00+00"


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


def _count_where_id(pg_conn: Any, table: str, row_id: int) -> int:
    with pg_conn.cursor() as cursor:
        cursor.execute(f'SELECT count(*) FROM "{table}" WHERE id = %s', (row_id,))
        return cursor.fetchone()[0]


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

        expired = _seed_utub_url(
            pg_conn,
            utub_id=utub_id,
            url_id=expired_url_id,
            user_id=user_id,
            deleted_at=_ago(days=TRASH_RETENTION_DAYS, hours=1),
            deleted_by=user_id,
        )
        recent = _seed_utub_url(
            pg_conn,
            utub_id=utub_id,
            url_id=recent_url_id,
            user_id=user_id,
            deleted_at=_ago(days=TRASH_RETENTION_DAYS) + timedelta(hours=1),
            deleted_by=user_id,
        )
        live = _seed_utub_url(
            pg_conn, utub_id=utub_id, url_id=live_url_id, user_id=user_id
        )
        for utub_url_id in (expired, recent, live):
            _seed_url_tag(
                pg_conn,
                utub_id=utub_id,
                utub_url_id=utub_url_id,
                utub_tag_id=tag_id,
                user_id=user_id,
            )

        result = run_trash_purge(pg_conn=pg_conn)

        assert result == TrashPurgeResult(utubs=0, urls=1)
        assert _count_where_id(pg_conn, "UtubUrls", expired) == 0
        assert _count(pg_conn, "UtubUrlTags", "utubUrlID", expired) == 0
        assert _count_where_id(pg_conn, "UtubUrls", recent) == 1
        assert _count_where_id(pg_conn, "UtubUrls", live) == 1
        assert _count(pg_conn, "UtubUrlTags", "utubID", utub_id) == 2
        assert _count_where_id(pg_conn, "Urls", expired_url_id) == 1
        assert _count_where_id(pg_conn, "Utubs", utub_id) == 1
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
        first = _seed_utub_url(
            pg_conn, utub_id=utub_id, url_id=first_url_id, user_id=creator_id
        )
        second = _seed_utub_url(
            pg_conn,
            utub_id=utub_id,
            url_id=second_url_id,
            user_id=creator_id,
            deleted_at=_ago(days=10),
            deleted_by=creator_id,
        )
        for utub_url_id in (first, second):
            _seed_url_tag(
                pg_conn,
                utub_id=utub_id,
                utub_url_id=utub_url_id,
                utub_tag_id=tag_id,
                user_id=creator_id,
            )

        result = run_trash_purge(pg_conn=pg_conn)

        assert result == TrashPurgeResult(utubs=1, urls=2)
        assert _count_where_id(pg_conn, "Utubs", utub_id) == 0
        for table in ("UtubMembers", "UtubTags", "UtubUrls", "UtubUrlTags"):
            assert _count(pg_conn, table, "utubID", utub_id) == 0, table
        assert _count_where_id(pg_conn, "Urls", first_url_id) == 1
        assert _count_where_id(pg_conn, "Urls", second_url_id) == 1
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
        assert _count_where_id(pg_conn, "Utubs", utub_id) == 1
        assert _count(pg_conn, "UtubMembers", "utubID", utub_id) == 1
        assert _count_where_id(pg_conn, "UtubUrls", utub_url_id) == 1
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
        old = _seed_utub_url(
            pg_conn,
            utub_id=utub_id,
            url_id=old_url_id,
            user_id=user_id,
            deleted_at=_ago(days=40),
            deleted_by=user_id,
        )
        other = _seed_utub_url(
            pg_conn, utub_id=utub_id, url_id=other_url_id, user_id=user_id
        )

        result = run_trash_purge(pg_conn=pg_conn)

        assert result == TrashPurgeResult(utubs=0, urls=1)
        assert _count_where_id(pg_conn, "UtubUrls", old) == 0
        assert _count_where_id(pg_conn, "UtubUrls", other) == 1
        assert _count_where_id(pg_conn, "Utubs", utub_id) == 1
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
        assert _count_where_id(pg_conn, "Utubs", trashed_utub_id) == 1
        assert _count(pg_conn, "UtubMembers", "utubID", trashed_utub_id) == 1
        assert _count_where_id(pg_conn, "UtubUrls", trashed_utub_url) == 1
        assert _count_where_id(pg_conn, "Utubs", live_utub_id) == 1
        assert _count_where_id(pg_conn, "UtubUrls", live_locked_utub_url) == 1
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
        assert _count_where_id(pg_conn, "UtubUrls", utub_url_id) == 0
    finally:
        pg_conn.close()
