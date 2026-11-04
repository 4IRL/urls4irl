"""Shared held-lock and thread helpers for the invite link concurrency tests.

The default ``db_transaction`` harness runs on one SAVEPOINT connection, so locks never
block there. The concurrency tests depend on ``build_app`` only, commit real data and
hold a row lock on a second raw connection while ``pg_stat_activity`` confirms the exact
number of queued contenders. Tests assert sets and counts, never which thread won.

This is the one place that reaches into the short-link race module for its private
request/backend helpers, so the invite tests import only public names from here.
"""

from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from typing import Any, Callable, Generator

from flask import Flask

from backend import db
from backend.models.users import Users
from tests.integration.short_links.test_mint_short_link_concurrency import (
    POLL_INTERVAL_SECONDS,
    POST_TERMINATE_JOIN_SECONDS,
    THREAD_JOIN_TIMEOUT_SECONDS,
    UNEXPECTED_ERROR_STATUS,
    ThreadResult,
    _blocked_backend_count,
    _prepare_request,
    _terminate_stuck_backends,
)
from tests.integration.system.metrics_helpers import build_pg_conn

BLOCK_WAIT_SECONDS: float = 20.0
LOCK_UTUB_SQL: str = 'SELECT id FROM "Utubs" WHERE id = %s FOR UPDATE'
LOCK_INVITE_SQL: str = 'SELECT id FROM "UtubInviteLinks" WHERE id = %s FOR UPDATE'
ERROR_OUTCOME: str = "error"
SERVER_ERROR_FLOOR: int = 500

Box = list[Any]

prepare_request = _prepare_request


def assert_no_server_error(*results: ThreadResult) -> None:
    """Fail when any request was a 5xx or an exception caught in its thread (599)."""
    for status, body in results:
        assert status != UNEXPECTED_ERROR_STATUS, f"thread exception: {body}"
        assert status < SERVER_ERROR_FLOOR, f"server error {status}: {body}"


def add_users(app: Flask, count: int) -> list[int]:
    """Commit ``count`` extra validated, non-member users; returns their ids."""
    user_ids: list[int] = []
    with app.app_context():
        for index in range(count):
            new_user = Users(
                username=f"racer{index}",
                email=f"racer{index}@urls4irl.app",
                plaintext_password=f"Racer{index}@urls4irl.app",
            )
            new_user.email_validated = True
            db.session.add(new_user)
            db.session.commit()
            user_ids.append(new_user.id)
    return user_ids


def exec_sql(app: Flask, statement: str, params: tuple[Any, ...]) -> None:
    pg_conn = build_pg_conn(app)
    try:
        with pg_conn.cursor() as cursor:
            cursor.execute(statement, params)
        pg_conn.commit()
    finally:
        pg_conn.close()


def scalar(app: Flask, statement: str, params: tuple[Any, ...]) -> Any:
    pg_conn = build_pg_conn(app)
    try:
        with pg_conn.cursor() as cursor:
            cursor.execute(statement, params)
            return cursor.fetchone()[0]
    finally:
        pg_conn.rollback()
        pg_conn.close()


def member_count(app: Flask, utub_id: int) -> int:
    return scalar(
        app, 'SELECT count(*) FROM "UtubMembers" WHERE "utubID" = %s', (utub_id,)
    )


def acceptance_count(app: Flask, invite_id: int) -> int:
    return scalar(
        app,
        'SELECT count(*) FROM "UtubInviteAcceptances" WHERE "inviteID" = %s',
        (invite_id,),
    )


def use_count(app: Flask, invite_id: int) -> int:
    return scalar(
        app, 'SELECT "useCount" FROM "UtubInviteLinks" WHERE id = %s', (invite_id,)
    )


def max_uses(app: Flask, invite_id: int) -> int | None:
    return scalar(
        app, 'SELECT "maxUses" FROM "UtubInviteLinks" WHERE id = %s', (invite_id,)
    )


def invite_rows(app: Flask, utub_id: int) -> list[tuple[int, str, bool]]:
    """Every invite row of a UTub as (id, token, revoked), oldest first."""
    pg_conn = build_pg_conn(app)
    try:
        with pg_conn.cursor() as cursor:
            cursor.execute(
                'SELECT id, token, "revokedAt" IS NOT NULL FROM "UtubInviteLinks" '
                'WHERE "utubID" = %s ORDER BY id',
                (utub_id,),
            )
            return [(row[0], row[1], row[2]) for row in cursor.fetchall()]
    finally:
        pg_conn.rollback()
        pg_conn.close()


@contextmanager
def held_lock(app: Flask, statement: str, row_id: int) -> Generator[None, None, None]:
    """Hold a row lock on a second raw connection; always rolled back and closed."""
    holder = build_pg_conn(app)
    try:
        with holder.cursor() as cursor:
            cursor.execute(statement, (row_id,))
        yield
    finally:
        holder.rollback()
        holder.close()


def spawn(target: Callable[[], Any]) -> tuple[threading.Thread, Box]:
    """Start ``target`` on a daemon thread; its return value lands in the box."""
    box: Box = []

    def _run() -> None:
        box.append(target())

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return thread, box


def wait_until_blocked(
    app: Flask, threads: list[threading.Thread], expected: int
) -> None:
    """Wait until exactly ``expected`` backends wait on a lock; fail if a thread ends
    first (never queued), more backends than expected block, or the wait times out."""
    deadline = time.monotonic() + BLOCK_WAIT_SECONDS
    while time.monotonic() < deadline:
        if not all(thread.is_alive() for thread in threads):
            raise AssertionError("a thread finished before blocking on a lock")
        blocked = _blocked_backend_count(app)
        assert blocked <= expected, f"{blocked} backends blocked, expected {expected}"
        if blocked == expected:
            return
        time.sleep(POLL_INTERVAL_SECONDS)
    raise AssertionError(f"never reached {expected} blocked backends")


def join_all(app: Flask, threads: list[threading.Thread]) -> None:
    for thread in threads:
        thread.join(timeout=THREAD_JOIN_TIMEOUT_SECONDS)
    if any(thread.is_alive() for thread in threads):
        _terminate_stuck_backends(app)
        for thread in threads:
            thread.join(timeout=POST_TERMINATE_JOIN_SECONDS)
    assert not any(thread.is_alive() for thread in threads), "a thread hung"
