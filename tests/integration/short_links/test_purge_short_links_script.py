"""Integration tests for the scripts/purge_short_links.py expired-link sweep.

Uses a raw psycopg2 connection (via build_pg_conn) against the test DB, mirroring
tests/integration/admin/test_purge_audit_log.py. Uses the ``runner`` fixture (not the
``app`` SAVEPOINT fixture), which would deadlock against a raw connection.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from flask import Flask
from flask.testing import FlaskCliRunner

from scripts.purge_short_links import run_purge
from tests.integration.short_links.short_link_helpers import (
    CREATED_KEY,
    SHORT_URL_KEY,
    anonymous_client,
    code_from_short_url,
    get_share_page,
    logged_in_as,
    normalized_body,
    post_mint,
)
from tests.integration.system.metrics_helpers import build_pg_conn

pytestmark = pytest.mark.short_links

_SEED_PASSWORD: str = "hashed-placeholder"
_SEED_TIMESTAMP: str = "2025-01-01 00:00:00+00"

CODE_EXPIRED: str = "ExpiredAAA"
CODE_JUST_EXPIRED: str = "JustExpBBB"
CODE_ACTIVE: str = "ActiveCCCC"
CODE_LOCKED_EXPIRED: str = "LockedDDDD"
CODE_TRASHED_EXPIRED: str = "TrashedEEE"
CODE_UNKNOWN: str = "NeverMadeX"


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


def _seed_utub_with_url(
    pg_conn: Any,
    *,
    name: str,
    user_id: int,
    is_locked: bool = False,
    deleted_at: datetime | None = None,
) -> int:
    """Seed a UTub (creator = ``user_id``) holding one URL and return the UtubUrls id."""
    with pg_conn.cursor() as cursor:
        cursor.execute(
            'INSERT INTO "Utubs" '
            '("utubName", "utubCreator", "createdAt", "lastUpdated", '
            '"deletedAt", "deletedBy", "isLocked") '
            "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (
                name,
                user_id,
                _SEED_TIMESTAMP,
                _SEED_TIMESTAMP,
                deleted_at,
                user_id if deleted_at is not None else None,
                is_locked,
            ),
        )
        utub_id: int = cursor.fetchone()[0]
        cursor.execute(
            'INSERT INTO "UtubMembers" ("utubID", "userID", "memberRole") '
            "VALUES (%s, %s, 'CREATOR')",
            (utub_id, user_id),
        )
        cursor.execute(
            'INSERT INTO "Urls" ("urlString", "createdBy", "createdAt") '
            "VALUES (%s, %s, %s) RETURNING id",
            (f"https://{name}.example.com", user_id, _SEED_TIMESTAMP),
        )
        url_id: int = cursor.fetchone()[0]
        cursor.execute(
            'INSERT INTO "UtubUrls" '
            '("utubID", "urlID", "userID", "urlTitle", "addedAt", "lastAccessed") '
            "VALUES (%s, %s, %s, '', %s, %s) RETURNING id",
            (utub_id, url_id, user_id, _SEED_TIMESTAMP, _SEED_TIMESTAMP),
        )
        utub_url_id: int = cursor.fetchone()[0]
    pg_conn.commit()
    return utub_url_id


def _seed_short_link(
    pg_conn: Any, *, utub_url_id: int, code: str, expires_at_sql: str, user_id: int
) -> None:
    """Insert a ShortLinks row; ``expires_at_sql`` is a trusted SQL expression."""
    with pg_conn.cursor() as cursor:
        cursor.execute(
            'INSERT INTO "ShortLinks" '
            '("utubUrlID", code, "createdBy", "createdAt", "expiresAt") '
            f"VALUES (%s, %s, %s, now(), {expires_at_sql})",
            (utub_url_id, code, user_id),
        )
    pg_conn.commit()


def _remaining_codes(pg_conn: Any) -> frozenset[str]:
    with pg_conn.cursor() as cursor:
        cursor.execute('SELECT code FROM "ShortLinks"')
        return frozenset(row[0] for row in cursor.fetchall())


def test_run_purge_empty_table_returns_zero(
    runner: tuple[Flask, FlaskCliRunner],
) -> None:
    """
    GIVEN an empty ShortLinks table
    WHEN run_purge is called
    THEN the return value is 0.
    """
    app, _ = runner
    pg_conn = build_pg_conn(app)
    try:
        _truncate_all(pg_conn)
        assert run_purge(pg_conn=pg_conn) == 0
    finally:
        _truncate_all(pg_conn)
        pg_conn.close()


def test_run_purge_deletes_exactly_the_expired_rows_and_is_idempotent(
    runner: tuple[Flask, FlaskCliRunner],
) -> None:
    """
    GIVEN an expired, a just-expired (expiresAt = now) and an active link
    WHEN run_purge runs
    THEN exactly the two expired rows are deleted and counted, the active row is
         untouched, and a second run deletes 0.
    """
    app, _ = runner
    pg_conn = build_pg_conn(app)
    try:
        _truncate_all(pg_conn)
        user_id = _seed_user(pg_conn, "purge_links_user")
        for name, code, expires_at_sql in (
            ("expired", CODE_EXPIRED, "now() - interval '1 day'"),
            ("justexpired", CODE_JUST_EXPIRED, "now()"),
            ("active", CODE_ACTIVE, "now() + interval '6 days'"),
        ):
            utub_url_id = _seed_utub_with_url(pg_conn, name=name, user_id=user_id)
            _seed_short_link(
                pg_conn,
                utub_url_id=utub_url_id,
                code=code,
                expires_at_sql=expires_at_sql,
                user_id=user_id,
            )

        assert run_purge(pg_conn=pg_conn) == 2
        assert _remaining_codes(pg_conn) == {CODE_ACTIVE}
        assert run_purge(pg_conn=pg_conn) == 0
        assert _remaining_codes(pg_conn) == {CODE_ACTIVE}
    finally:
        _truncate_all(pg_conn)
        pg_conn.close()


def test_run_purge_deletes_expired_rows_in_locked_and_trashed_utubs(
    runner: tuple[Flask, FlaskCliRunner],
) -> None:
    """
    GIVEN expired links in an admin-locked UTub and in a trashed UTub
    WHEN run_purge runs
    THEN both are deleted: the sweep skips no UTub.
    """
    app, _ = runner
    pg_conn = build_pg_conn(app)
    try:
        _truncate_all(pg_conn)
        user_id = _seed_user(pg_conn, "purge_links_user")
        locked_url_id = _seed_utub_with_url(
            pg_conn, name="locked", user_id=user_id, is_locked=True
        )
        trashed_url_id = _seed_utub_with_url(
            pg_conn,
            name="trashed",
            user_id=user_id,
            deleted_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        _seed_short_link(
            pg_conn,
            utub_url_id=locked_url_id,
            code=CODE_LOCKED_EXPIRED,
            expires_at_sql="now() - interval '1 hour'",
            user_id=user_id,
        )
        _seed_short_link(
            pg_conn,
            utub_url_id=trashed_url_id,
            code=CODE_TRASHED_EXPIRED,
            expires_at_sql="now() - interval '1 hour'",
            user_id=user_id,
        )

        assert run_purge(pg_conn=pg_conn) == 2
        assert _remaining_codes(pg_conn) == frozenset()
    finally:
        _truncate_all(pg_conn)
        pg_conn.close()


def test_after_purge_mint_inserts_a_fresh_row_and_old_code_stays_404(
    runner: tuple[Flask, FlaskCliRunner],
) -> None:
    """
    GIVEN an expired link whose row is purged
    WHEN a member mints for the same URL and the purged code is opened
    THEN a new row with a new code is created (created: true) and the purged code
         renders the identical 404 page an unknown code does.
    """
    app, _ = runner
    pg_conn = build_pg_conn(app)
    try:
        _truncate_all(pg_conn)
        user_id = _seed_user(pg_conn, "purge_links_user")
        utub_url_id = _seed_utub_with_url(pg_conn, name="remint", user_id=user_id)
        utub_id = 1
        _seed_short_link(
            pg_conn,
            utub_url_id=utub_url_id,
            code=CODE_EXPIRED,
            expires_at_sql="now() - interval '1 day'",
            user_id=user_id,
        )

        assert run_purge(pg_conn=pg_conn) == 1

        with logged_in_as(app, user_id) as (client, csrf_token):
            response = post_mint(
                client, csrf_token, utub_id=utub_id, utub_url_id=utub_url_id
            )
        assert response.status_code == 200
        body = response.get_json()
        assert body[CREATED_KEY] is True
        assert code_from_short_url(body[SHORT_URL_KEY]) != CODE_EXPIRED

        with app.test_request_context():
            purged_page = get_share_page(anonymous_client(app), CODE_EXPIRED)
            unknown_page = get_share_page(anonymous_client(app), CODE_UNKNOWN)
        assert purged_page.status_code == unknown_page.status_code == 404
        assert normalized_body(purged_page) == normalized_body(unknown_page)
    finally:
        _truncate_all(pg_conn)
        pg_conn.close()
