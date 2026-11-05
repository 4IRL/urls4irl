"""Integration tests for the scripts/purge_invite_links.py nightly purge.

Uses a raw psycopg2 connection (via build_pg_conn) and the ``runner`` fixture (not the
``app`` SAVEPOINT fixture, which would deadlock against a raw connection). Rows are
seeded with raw SQL so ``revokedAt`` / ``expiresAt`` can be back-dated.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from flask import Flask
from flask.testing import FlaskCliRunner

from scripts.purge_invite_links import (
    INVITE_LINK_PURGE_RETENTION_DAYS,
    PURGE_DEAD_INVITE_LINKS_SQL,
    run_purge,
)
from tests.integration.system.metrics_helpers import build_pg_conn

pytestmark = pytest.mark.invite_links

_SEED_TIMESTAMP: str = "2025-01-01 00:00:00+00"
_PAST_BEYOND = timedelta(days=INVITE_LINK_PURGE_RETENTION_DAYS, hours=1)
_PAST_WITHIN = timedelta(days=INVITE_LINK_PURGE_RETENTION_DAYS) - timedelta(hours=1)


def _ago(delta: timedelta) -> datetime:
    return datetime.now(timezone.utc) - delta


def _from_now(delta: timedelta) -> datetime:
    return datetime.now(timezone.utc) + delta


def _truncate_all(pg_conn: Any) -> None:
    with pg_conn.cursor() as cursor:
        cursor.execute('TRUNCATE TABLE "Users", "Utubs" RESTART IDENTITY CASCADE')
    pg_conn.commit()


def _seed_user(pg_conn: Any, username: str) -> int:
    with pg_conn.cursor() as cursor:
        cursor.execute(
            'INSERT INTO "Users" '
            '(username, email, password, "createdAt", role, "emailValidated") '
            "VALUES (%s, %s, 'hashed-placeholder', %s, 'USER', true) RETURNING id",
            (username, f"{username}@example.com", _SEED_TIMESTAMP),
        )
        user_id: int = cursor.fetchone()[0]
    pg_conn.commit()
    return user_id


def _seed_utub(pg_conn: Any, *, creator_id: int) -> int:
    with pg_conn.cursor() as cursor:
        cursor.execute(
            'INSERT INTO "Utubs" ("utubName", "utubCreator", "createdAt", '
            '"lastUpdated") VALUES (%s, %s, %s, %s) RETURNING id',
            ("purge utub", creator_id, _SEED_TIMESTAMP, _SEED_TIMESTAMP),
        )
        utub_id: int = cursor.fetchone()[0]
    pg_conn.commit()
    return utub_id


def _seed_link(
    pg_conn: Any,
    *,
    utub_id: int,
    creator_id: int,
    token: str,
    expires_at: datetime,
    revoked_at: datetime | None = None,
    max_uses: int | None = None,
    use_count: int = 0,
) -> int:
    with pg_conn.cursor() as cursor:
        cursor.execute(
            'INSERT INTO "UtubInviteLinks" ("utubID", token, "createdBy", '
            '"createdAt", "expiresAt", "maxUses", "useCount", "revokedAt") '
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (
                utub_id,
                token,
                creator_id,
                _SEED_TIMESTAMP,
                expires_at,
                max_uses,
                use_count,
                revoked_at,
            ),
        )
        link_id: int = cursor.fetchone()[0]
    pg_conn.commit()
    return link_id


def _link_count(pg_conn: Any, link_id: int) -> int:
    with pg_conn.cursor() as cursor:
        cursor.execute(
            'SELECT count(*) FROM "UtubInviteLinks" WHERE id = %s', (link_id,)
        )
        return cursor.fetchone()[0]


class _FailingCursor:
    def __init__(self, cursor: Any, failing_sql: str) -> None:
        self._cursor = cursor
        self._failing_sql = failing_sql

    def __enter__(self) -> _FailingCursor:
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self._cursor.close()

    def execute(self, sql: str, params: Any = None) -> None:
        if sql == self._failing_sql:
            raise RuntimeError("simulated failure on the purge delete")
        self._cursor.execute(sql, params)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._cursor, name)


class _FailingConnection:
    def __init__(self, pg_conn: Any, failing_sql: str) -> None:
        self._pg_conn = pg_conn
        self._failing_sql = failing_sql
        self.rollback_calls = 0

    def rollback(self) -> None:
        self.rollback_calls += 1
        self._pg_conn.rollback()

    def cursor(self) -> _FailingCursor:
        return _FailingCursor(self._pg_conn.cursor(), self._failing_sql)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._pg_conn, name)


@pytest.mark.parametrize(
    "expires_delta, revoked_delta, max_uses, use_count, should_be_deleted",
    [
        # expired 30 days + 1 hour, never revoked -> deleted
        (-_PAST_BEYOND, None, None, 0, True),
        # expired 30 days - 1 hour -> kept
        (-_PAST_WITHIN, None, None, 0, False),
        # revoked 30 days + 1 hour ago, future expiry -> deleted on revokedAt alone
        (timedelta(days=5), -_PAST_BEYOND, None, 0, True),
        # revoked recently, future expiry -> kept
        (timedelta(days=5), -timedelta(hours=1), None, 0, False),
        # revoked 1 day ago, expired 60 days ago -> kept (revokedAt is the clock)
        (-timedelta(days=60), -timedelta(days=1), None, 0, False),
        # live -> kept
        (timedelta(days=5), None, None, 0, False),
        # used up but unexpired -> kept
        (timedelta(days=5), None, 3, 3, False),
    ],
    ids=[
        "expired-beyond-grace",
        "expired-within-grace",
        "revoked-beyond-grace-future-expiry",
        "revoked-recently",
        "revoked-recently-expired-long-ago",
        "live",
        "used-up-unexpired",
    ],
)
def test_purge_deletes_only_rows_dead_beyond_retention(
    runner: tuple[Flask, FlaskCliRunner],
    expires_delta: timedelta,
    revoked_delta: timedelta | None,
    max_uses: int | None,
    use_count: int,
    should_be_deleted: bool,
) -> None:
    """
    GIVEN one invite link in a given lifecycle state
    WHEN run_purge runs with the default retention
    THEN it is deleted only when dead for more than 30 days, and a second run is a no-op
    """
    app, _ = runner
    pg_conn = build_pg_conn(app)
    try:
        _truncate_all(pg_conn)
        user_id = _seed_user(pg_conn, "purge_user")
        utub_id = _seed_utub(pg_conn, creator_id=user_id)
        link_id = _seed_link(
            pg_conn,
            utub_id=utub_id,
            creator_id=user_id,
            token="purge-token-0000000001",
            expires_at=_from_now(expires_delta),
            revoked_at=None if revoked_delta is None else _from_now(revoked_delta),
            max_uses=max_uses,
            use_count=use_count,
        )

        assert run_purge(pg_conn=pg_conn) == (1 if should_be_deleted else 0)
        assert _link_count(pg_conn, link_id) == (0 if should_be_deleted else 1)
        assert run_purge(pg_conn=pg_conn) == 0
    finally:
        _truncate_all(pg_conn)
        pg_conn.close()


@pytest.mark.parametrize("revoked", [False, True], ids=["expired", "revoked"])
def test_purge_keeps_old_dead_row_with_acceptance(
    runner: tuple[Flask, FlaskCliRunner], revoked: bool
) -> None:
    """
    GIVEN an old-dead (expired or revoked) invite link that has an acceptance row
    WHEN run_purge runs
    THEN the link and its acceptance row both survive
    """
    app, _ = runner
    pg_conn = build_pg_conn(app)
    try:
        _truncate_all(pg_conn)
        user_id = _seed_user(pg_conn, "accept_user")
        utub_id = _seed_utub(pg_conn, creator_id=user_id)
        link_id = _seed_link(
            pg_conn,
            utub_id=utub_id,
            creator_id=user_id,
            token="purge-token-0000000002",
            expires_at=_ago(_PAST_BEYOND)
            if not revoked
            else _from_now(timedelta(days=5)),
            revoked_at=_ago(_PAST_BEYOND) if revoked else None,
        )
        with pg_conn.cursor() as cursor:
            cursor.execute(
                'INSERT INTO "UtubInviteAcceptances" '
                '("inviteID", "utubID", "userID", "acceptedAt") '
                "VALUES (%s, %s, %s, %s)",
                (link_id, utub_id, user_id, _SEED_TIMESTAMP),
            )
        pg_conn.commit()

        assert run_purge(pg_conn=pg_conn) == 0

        assert _link_count(pg_conn, link_id) == 1
        with pg_conn.cursor() as cursor:
            cursor.execute(
                'SELECT count(*) FROM "UtubInviteAcceptances" WHERE "inviteID" = %s',
                (link_id,),
            )
            assert cursor.fetchone()[0] == 1
    finally:
        _truncate_all(pg_conn)
        pg_conn.close()


def test_purge_nulls_pending_invite_reference_without_error(
    runner: tuple[Flask, FlaskCliRunner],
) -> None:
    """
    GIVEN an old-dead invite link referenced by an EmailValidations pendingInviteID
    WHEN run_purge runs
    THEN the link is deleted without error and the reference becomes NULL
    """
    app, _ = runner
    pg_conn = build_pg_conn(app)
    try:
        _truncate_all(pg_conn)
        creator_id = _seed_user(pg_conn, "pending_creator")
        pending_user_id = _seed_user(pg_conn, "pending_user")
        utub_id = _seed_utub(pg_conn, creator_id=creator_id)
        link_id = _seed_link(
            pg_conn,
            utub_id=utub_id,
            creator_id=creator_id,
            token="purge-token-0000000003",
            expires_at=_ago(_PAST_BEYOND),
        )
        with pg_conn.cursor() as cursor:
            cursor.execute(
                'INSERT INTO "EmailValidations" '
                '("userID", "validationToken", "isValidated", attempts, '
                '"createdAt", "pendingInviteID") '
                "VALUES (%s, 'tok', false, 0, %s, %s) RETURNING id",
                (pending_user_id, _SEED_TIMESTAMP, link_id),
            )
            validation_id = cursor.fetchone()[0]
        pg_conn.commit()

        assert run_purge(pg_conn=pg_conn) == 1

        assert _link_count(pg_conn, link_id) == 0
        with pg_conn.cursor() as cursor:
            cursor.execute(
                'SELECT "pendingInviteID" FROM "EmailValidations" WHERE id = %s',
                (validation_id,),
            )
            assert cursor.fetchone()[0] is None
    finally:
        _truncate_all(pg_conn)
        pg_conn.close()


@pytest.mark.parametrize("invalid_retention_days", [0, -1])
def test_purge_invalid_retention_raises_before_touching_db(
    runner: tuple[Flask, FlaskCliRunner], invalid_retention_days: int
) -> None:
    """
    GIVEN an old-dead invite link and a retention below 1
    WHEN run_purge runs
    THEN ValueError is raised, no statement executes, and the row remains
    """
    app, _ = runner
    pg_conn = build_pg_conn(app)
    try:
        _truncate_all(pg_conn)
        user_id = _seed_user(pg_conn, "retention_user")
        utub_id = _seed_utub(pg_conn, creator_id=user_id)
        link_id = _seed_link(
            pg_conn,
            utub_id=utub_id,
            creator_id=user_id,
            token="purge-token-0000000004",
            expires_at=_ago(_PAST_BEYOND),
        )

        # A connection whose cursor() raises proves the DB is never touched.
        class _NoCursorConnection:
            def cursor(self) -> Any:
                raise AssertionError("cursor must not be opened")

        with pytest.raises(ValueError, match="retention_days"):
            run_purge(
                pg_conn=_NoCursorConnection(),  # type: ignore[arg-type]
                retention_days=invalid_retention_days,
            )

        assert _link_count(pg_conn, link_id) == 1
    finally:
        _truncate_all(pg_conn)
        pg_conn.close()


def test_purge_rolls_back_when_the_delete_fails(
    runner: tuple[Flask, FlaskCliRunner],
) -> None:
    """
    GIVEN an old-dead invite link and a connection whose delete statement raises
    WHEN run_purge runs
    THEN the error is re-raised and the row still exists
    """
    app, _ = runner
    pg_conn = build_pg_conn(app)
    try:
        _truncate_all(pg_conn)
        user_id = _seed_user(pg_conn, "rollback_user")
        utub_id = _seed_utub(pg_conn, creator_id=user_id)
        link_id = _seed_link(
            pg_conn,
            utub_id=utub_id,
            creator_id=user_id,
            token="purge-token-0000000005",
            expires_at=_ago(_PAST_BEYOND),
        )

        failing_conn = _FailingConnection(pg_conn, PURGE_DEAD_INVITE_LINKS_SQL)
        with pytest.raises(RuntimeError, match="simulated failure"):
            run_purge(pg_conn=failing_conn)  # type: ignore[arg-type]

        assert failing_conn.rollback_calls == 1
        assert _link_count(pg_conn, link_id) == 1
    finally:
        _truncate_all(pg_conn)
        pg_conn.close()
