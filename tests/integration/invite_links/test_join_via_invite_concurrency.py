"""Real-Postgres concurrency proof for ``join_via_invite``.

The default ``db_transaction`` harness runs on one SAVEPOINT connection, so locks never
block there. These tests depend on ``build_app`` only (via ``committed_invite_utub``),
commit real data and use the held-lock pattern of the short-link race tests: a second
raw connection holds a row lock, ``pg_stat_activity`` confirms the exact number of
contenders is queued, then the lock is released. Each worker thread opens its own app
context. Tests assert sets and counts, never which thread won.
"""

from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from typing import Any, Callable, Generator

import psycopg2
import psycopg2.errors
import pytest
from flask import Flask

from backend import db
from backend.invite_links.constants import InviteJoinOutcome
from backend.invite_links.services.join_via_invite import join_via_invite
from backend.models.users import Users
from backend.models.utub_invite_links import Utub_Invite_Links
from backend.utubs.guards import lock_utub_for_update
from tests.integration.invite_links.conftest import COMMITTED_INVITE_TOKEN
from tests.integration.short_links.test_mint_short_link_concurrency import (
    POLL_INTERVAL_SECONDS,
    POST_TERMINATE_JOIN_SECONDS,
    THREAD_JOIN_TIMEOUT_SECONDS,
    _blocked_backend_count,
    _terminate_stuck_backends,
)
from tests.integration.system.metrics_helpers import build_pg_conn

pytestmark = pytest.mark.invite_links

BLOCK_WAIT_SECONDS: float = 20.0
CREATOR_INDEX: int = 0
MEMBER_INDEX: int = 1
LOCK_UTUB_SQL: str = 'SELECT id FROM "Utubs" WHERE id = %s FOR UPDATE'
LOCK_INVITE_SQL: str = 'SELECT id FROM "UtubInviteLinks" WHERE id = %s FOR UPDATE'
NOWAIT_UTUB_SQL: str = 'SELECT id FROM "Utubs" WHERE id = %s FOR UPDATE NOWAIT'
NOWAIT_INVITE_SQL: str = (
    'SELECT id FROM "UtubInviteLinks" WHERE id = %s FOR UPDATE NOWAIT'
)
ERROR_OUTCOME: str = "error"

JoinOutcomeTuple = tuple[str, int | None]
Box = list[Any]


def _add_users(app: Flask, count: int) -> list[int]:
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


def _exec(app: Flask, statement: str, params: tuple[Any, ...]) -> None:
    pg_conn = build_pg_conn(app)
    try:
        with pg_conn.cursor() as cursor:
            cursor.execute(statement, params)
        pg_conn.commit()
    finally:
        pg_conn.close()


def _scalar(app: Flask, statement: str, params: tuple[Any, ...]) -> Any:
    pg_conn = build_pg_conn(app)
    try:
        with pg_conn.cursor() as cursor:
            cursor.execute(statement, params)
            return cursor.fetchone()[0]
    finally:
        pg_conn.rollback()
        pg_conn.close()


def _member_count(app: Flask, utub_id: int) -> int:
    return _scalar(
        app, 'SELECT count(*) FROM "UtubMembers" WHERE "utubID" = %s', (utub_id,)
    )


def _acceptance_count(app: Flask, invite_id: int) -> int:
    return _scalar(
        app,
        'SELECT count(*) FROM "UtubInviteAcceptances" WHERE "inviteID" = %s',
        (invite_id,),
    )


def _use_count(app: Flask, invite_id: int) -> int:
    return _scalar(
        app, 'SELECT "useCount" FROM "UtubInviteLinks" WHERE id = %s', (invite_id,)
    )


def _max_uses(app: Flask, invite_id: int) -> int | None:
    return _scalar(
        app, 'SELECT "maxUses" FROM "UtubInviteLinks" WHERE id = %s', (invite_id,)
    )


@contextmanager
def _held_lock(app: Flask, statement: str, row_id: int) -> Generator[None, None, None]:
    """Hold a row lock on a second raw connection; always rolled back and closed."""
    holder = build_pg_conn(app)
    try:
        with holder.cursor() as cursor:
            cursor.execute(statement, (row_id,))
        yield
    finally:
        holder.rollback()
        holder.close()


def _spawn(target: Callable[[], Any]) -> tuple[threading.Thread, Box]:
    """Start ``target`` on a daemon thread; its return value lands in the box."""
    box: Box = []

    def _run() -> None:
        box.append(target())

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return thread, box


def _join_worker(app: Flask, actor_id: int, invite_id: int) -> JoinOutcomeTuple:
    """Open an own app context, load actor and invite by id, join, return primitives."""
    try:
        with app.app_context():
            actor = db.session.get(Users, actor_id)
            invite = db.session.get(Utub_Invite_Links, invite_id)
            result = join_via_invite(actor, invite)
            return result.outcome.value, result.utub_id
    except Exception as join_error:
        return ERROR_OUTCOME, repr(join_error)


def _wait_until_blocked(
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


def _join_all(app: Flask, threads: list[threading.Thread]) -> None:
    for thread in threads:
        thread.join(timeout=THREAD_JOIN_TIMEOUT_SECONDS)
    if any(thread.is_alive() for thread in threads):
        _terminate_stuck_backends(app)
        for thread in threads:
            thread.join(timeout=POST_TERMINATE_JOIN_SECONDS)
    assert not any(thread.is_alive() for thread in threads), "a thread hung"


def _manager_lowers_uses(
    app: Flask,
    utub_id: int,
    invite_id: int,
    new_max: int,
    *,
    while_locked: Callable[[], None] | None = None,
) -> tuple[bool, int]:
    """Stand-in for the manager's "change Uses" write (master Step 3 swaps in the real
    service): lock Utubs, then the invite, reject ``new_max`` below ``useCount``,
    update and commit. ``while_locked`` runs once both locks are held. Returns
    (applied, use_count_seen_under_lock)."""
    pg_conn = build_pg_conn(app)
    try:
        with pg_conn.cursor() as cursor:
            cursor.execute(LOCK_UTUB_SQL, (utub_id,))
            cursor.execute(LOCK_INVITE_SQL, (invite_id,))
            if while_locked is not None:
                while_locked()
            cursor.execute(
                'SELECT "useCount" FROM "UtubInviteLinks" WHERE id = %s', (invite_id,)
            )
            use_count: int = cursor.fetchone()[0]
            if new_max < use_count:
                pg_conn.rollback()
                return False, use_count
            cursor.execute(
                'UPDATE "UtubInviteLinks" SET "maxUses" = %s WHERE id = %s',
                (new_max, invite_id),
            )
        pg_conn.commit()
        return True, use_count
    finally:
        pg_conn.rollback()
        pg_conn.close()


def _manager_target(
    app: Flask, utub_id: int, invite_id: int, new_max: int
) -> Callable[[], Any]:
    def _target() -> Any:
        try:
            return _manager_lowers_uses(app, utub_id, invite_id, new_max)
        except Exception as manager_error:
            return ERROR_OUTCOME, repr(manager_error)

    return _target


@pytest.mark.parametrize("limit", [1, 3])
def test_use_limit_admits_exactly_n_joiners(committed_invite_utub, limit: int) -> None:
    """
    GIVEN a link limited to N uses and N+2 joiners queued behind the Utubs row lock
    WHEN the lock is released
    THEN exactly N joined and the rest are DEAD, with N member rows beyond the creator,
         N acceptance rows and use_count == N, and no exception
    """
    app, utub_id, invite_id, _ = committed_invite_utub
    joiner_ids = _add_users(app, limit + 2)
    _exec(
        app,
        'UPDATE "UtubInviteLinks" SET "maxUses" = %s WHERE id = %s',
        (limit, invite_id),
    )

    spawned: list[tuple[threading.Thread, Box]] = []
    with _held_lock(app, LOCK_UTUB_SQL, utub_id):
        for joiner_id in joiner_ids:
            spawned.append(
                _spawn(lambda uid=joiner_id: _join_worker(app, uid, invite_id))
            )
        threads = [thread for thread, _ in spawned]
        _wait_until_blocked(app, threads, expected=len(threads))
    _join_all(app, threads)

    results = [box[0] for _, box in spawned]
    outcomes = [outcome for outcome, _ in results]
    assert ERROR_OUTCOME not in outcomes, results
    assert outcomes.count(InviteJoinOutcome.JOINED.value) == limit, results
    assert outcomes.count(InviteJoinOutcome.DEAD.value) == len(joiner_ids) - limit
    assert _member_count(app, utub_id) == 1 + limit
    assert _acceptance_count(app, invite_id) == limit
    assert _use_count(app, invite_id) == limit


def test_manager_lowering_uses_wins_over_queued_join(committed_invite_utub) -> None:
    """
    GIVEN use_count=2, max_uses=5 and a manager holding Utubs then the invite lock
    WHEN a join queues on the Utubs row and the manager lowers max_uses to 2
    THEN the join is DEAD with no acceptance and use_count stays 2
    """
    app, utub_id, invite_id, user_ids = committed_invite_utub
    _exec(
        app,
        'UPDATE "UtubInviteLinks" SET "useCount" = 2, "maxUses" = 5 WHERE id = %s',
        (invite_id,),
    )
    spawned: list[tuple[threading.Thread, Box]] = []

    def _queue_join() -> None:
        spawned.append(
            _spawn(lambda: _join_worker(app, user_ids[MEMBER_INDEX], invite_id))
        )
        _wait_until_blocked(app, [spawned[0][0]], expected=1)

    applied, seen = _manager_lowers_uses(
        app, utub_id, invite_id, 2, while_locked=_queue_join
    )
    _join_all(app, [spawned[0][0]])

    assert (applied, seen) == (True, 2)
    assert spawned[0][1] == [(InviteJoinOutcome.DEAD.value, None)]
    assert _acceptance_count(app, invite_id) == 0
    assert _use_count(app, invite_id) == 2
    assert _max_uses(app, invite_id) == 2
    assert _member_count(app, utub_id) == 1


def test_join_in_progress_wins_over_queued_manager(committed_invite_utub) -> None:
    """
    GIVEN use_count=2, max_uses=5 and a holder on only the invite row
    WHEN a join takes Utubs and blocks on the invite, then the manager blocks on Utubs
    THEN after release the join is JOINED, the manager sees useCount=3, rejects
         new_max=2 and max_uses stays 5 (fails if the join ever locked the invite first)
    """
    app, utub_id, invite_id, user_ids = committed_invite_utub
    _exec(
        app,
        'UPDATE "UtubInviteLinks" SET "useCount" = 2, "maxUses" = 5 WHERE id = %s',
        (invite_id,),
    )
    with _held_lock(app, LOCK_INVITE_SQL, invite_id):
        join_thread, join_box = _spawn(
            lambda: _join_worker(app, user_ids[MEMBER_INDEX], invite_id)
        )
        _wait_until_blocked(app, [join_thread], expected=1)
        manager_thread, manager_box = _spawn(
            _manager_target(app, utub_id, invite_id, 2)
        )
        _wait_until_blocked(app, [join_thread, manager_thread], expected=2)
    _join_all(app, [join_thread, manager_thread])

    assert join_box == [(InviteJoinOutcome.JOINED.value, utub_id)]
    assert manager_box == [(False, 3)]
    assert _max_uses(app, invite_id) == 5
    assert _use_count(app, invite_id) == 3
    assert _acceptance_count(app, invite_id) == 1


def test_double_submit_counts_once(committed_invite_utub) -> None:
    """
    GIVEN one actor submitting Join twice, both queued behind the Utubs row lock
    WHEN the lock is released
    THEN one is JOINED and the other ALREADY_MEMBER, with one member row, one
         acceptance, use_count == 1 and no integrity error
    """
    app, utub_id, invite_id, user_ids = committed_invite_utub
    actor_id = user_ids[MEMBER_INDEX]
    with _held_lock(app, LOCK_UTUB_SQL, utub_id):
        spawned = [
            _spawn(lambda: _join_worker(app, actor_id, invite_id)) for _ in range(2)
        ]
        threads = [thread for thread, _ in spawned]
        _wait_until_blocked(app, threads, expected=2)
    _join_all(app, threads)

    results = sorted(box[0] for _, box in spawned)
    assert results == sorted(
        [
            (InviteJoinOutcome.JOINED.value, utub_id),
            (InviteJoinOutcome.ALREADY_MEMBER.value, utub_id),
        ]
    ), results
    assert _member_count(app, utub_id) == 2
    assert _acceptance_count(app, invite_id) == 1
    assert _use_count(app, invite_id) == 1


def _assert_rows_lockable(
    app: Flask, utub_id: int, invite_id: int, *, include_invite: bool
) -> None:
    """NOWAIT-lock the Utubs row (and the invite row) on a fresh raw connection."""
    probe = build_pg_conn(app)
    try:
        with probe.cursor() as cursor:
            cursor.execute(NOWAIT_UTUB_SQL, (utub_id,))
            if include_invite:
                cursor.execute(NOWAIT_INVITE_SQL, (invite_id,))
    finally:
        probe.rollback()
        probe.close()


# (case id, actor index, mutation, expected outcome, rows locked: "none"|"utub"|"both")
PROBE_CASES = [
    ("actor_gate", MEMBER_INDEX, "unvalidate", InviteJoinOutcome.ACTOR_UNVALIDATED, 0),
    ("trashed_utub", MEMBER_INDEX, "trash", InviteJoinOutcome.DEAD, 1),
    ("dead_revoked", MEMBER_INDEX, "revoke", InviteJoinOutcome.DEAD, 2),
    ("dead_missing_invite", MEMBER_INDEX, "purge", InviteJoinOutcome.DEAD, 1),
    ("already_member_live", CREATOR_INDEX, "none", InviteJoinOutcome.ALREADY_MEMBER, 2),
    (
        "already_member_purged",
        CREATOR_INDEX,
        "purge",
        InviteJoinOutcome.ALREADY_MEMBER,
        1,
    ),
    ("joined", MEMBER_INDEX, "none", InviteJoinOutcome.JOINED, 2),
]


@pytest.mark.parametrize(
    "actor_index,mutation,expected,locked_rows",
    [case[1:] for case in PROBE_CASES],
    ids=[case[0] for case in PROBE_CASES],
)
def test_every_return_path_releases_its_locks(
    committed_invite_utub,
    actor_index: int,
    mutation: str,
    expected: InviteJoinOutcome,
    locked_rows: int,
) -> None:
    """
    GIVEN committed data and one return path of ``join_via_invite``
    WHEN the service returns while its app context is still open
    THEN a second connection can NOWAIT-lock every row that path locked
    """
    app, utub_id, invite_id, user_ids = committed_invite_utub
    if mutation == "unvalidate":
        _exec(
            app,
            'UPDATE "Users" SET "emailValidated" = false WHERE id = %s',
            (user_ids[actor_index],),
        )
    elif mutation == "trash":
        _exec(
            app,
            'UPDATE "Utubs" SET "deletedAt" = now() WHERE id = %s',
            (utub_id,),
        )
    elif mutation == "revoke":
        _exec(
            app,
            'UPDATE "UtubInviteLinks" SET "revokedAt" = now() WHERE id = %s',
            (invite_id,),
        )

    with app.app_context():
        actor = db.session.get(Users, user_ids[actor_index])
        invite = db.session.get(Utub_Invite_Links, invite_id)
        assert invite.token == COMMITTED_INVITE_TOKEN
        if mutation == "purge":
            _exec(app, 'DELETE FROM "UtubInviteLinks" WHERE id = %s', (invite_id,))
        result = join_via_invite(actor, invite)
        assert result.outcome == expected
        if locked_rows:
            _assert_rows_lockable(
                app, utub_id, invite_id, include_invite=locked_rows == 2
            )


def test_probe_fails_when_a_lock_is_left_held(committed_invite_utub) -> None:
    """
    GIVEN the Utubs row locked in the app context and never rolled back
    WHEN the NOWAIT probe runs on a second connection
    THEN it fails, proving the probe can detect a skipped rollback
    """
    app, utub_id, invite_id, _ = committed_invite_utub
    with app.app_context():
        try:
            assert lock_utub_for_update(utub_id=utub_id) is not None
            with pytest.raises(psycopg2.errors.LockNotAvailable):
                _assert_rows_lockable(app, utub_id, invite_id, include_invite=False)
        finally:
            db.session.rollback()
