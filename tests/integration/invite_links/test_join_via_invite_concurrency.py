"""Real-Postgres concurrency proof for ``join_via_invite``.

The default ``db_transaction`` harness runs on one SAVEPOINT connection, so locks never
block there. These tests depend on ``build_app`` only (via ``committed_invite_utub``),
commit real data and use the held-lock pattern of the short-link race tests: a second
raw connection holds a row lock, ``pg_stat_activity`` confirms the exact number of
contenders is queued, then the lock is released. Each worker thread opens its own app
context. Tests assert sets and counts, never which thread won. The manager's "change
Uses" write is the real ``PATCH`` route. Shared helpers live in
``concurrency_helpers``.
"""

from __future__ import annotations

import threading
from typing import Callable

import psycopg2
import psycopg2.errors
import pytest
from flask import Flask, url_for

from backend import db
from backend.invite_links.constants import InviteJoinOutcome, InviteLinkErrorCodes
from backend.invite_links.guards import lock_current_invite_for_update
from backend.invite_links.services import manage_invite_link
from backend.invite_links.services.join_via_invite import join_via_invite
from backend.models.users import Users
from backend.models.utub_invite_links import Utub_Invite_Links
from backend.utils.all_routes import ROUTES
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utubs.guards import lock_utub_for_update
from tests.integration.invite_links.concurrency_helpers import (
    ERROR_OUTCOME,
    LOCK_INVITE_SQL,
    LOCK_UTUB_SQL,
    Box,
    ThreadResult,
    acceptance_count,
    add_users,
    assert_no_server_error,
    exec_sql,
    held_lock,
    join_all,
    max_uses,
    member_count,
    prepare_request,
    spawn,
    use_count,
    wait_until_blocked,
)
from tests.integration.invite_links.conftest import COMMITTED_INVITE_TOKEN
from tests.integration.system.metrics_helpers import build_pg_conn

pytestmark = pytest.mark.invite_links

CREATOR_INDEX: int = 0
MEMBER_INDEX: int = 1
NOWAIT_UTUB_SQL: str = 'SELECT id FROM "Utubs" WHERE id = %s FOR UPDATE NOWAIT'
NOWAIT_INVITE_SQL: str = (
    'SELECT id FROM "UtubInviteLinks" WHERE id = %s FOR UPDATE NOWAIT'
)
SEEDED_USE_COUNT: int = 1
SEEDED_MAX_USES: int = 5
LOWERED_MAX_USES: int = 1

JoinOutcomeTuple = tuple[str, int | None]


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


def _prepare_lower_uses(
    app: Flask, utub_id: int, user_id: int, new_max: int
) -> Callable[[], ThreadResult]:
    """A logged-in callable that sends the real ``PATCH`` lowering ``max_uses``."""
    with app.test_request_context():
        patch_url = url_for(ROUTES.INVITE_LINKS.UPDATE_INVITE_LINK, utub_id=utub_id)
    return prepare_request(app, user_id, "patch", patch_url, {"max_uses": new_max})


def _assert_patch_outcome(
    result: ThreadResult, *, status: int, error_code: InviteLinkErrorCodes | None
) -> None:
    assert_no_server_error(result)
    response_status, body = result
    assert response_status == status, result
    assert (body or {}).get(STD_JSON.ERROR_CODE) == (
        int(error_code) if error_code is not None else None
    ), result


@pytest.mark.parametrize("limit", [1, 3])
def test_use_limit_admits_exactly_n_joiners(committed_invite_utub, limit: int) -> None:
    """
    GIVEN a link limited to N uses and N+2 joiners queued behind the Utubs row lock
    WHEN the lock is released
    THEN exactly N joined and the rest are DEAD, with N member rows beyond the creator,
         N acceptance rows and use_count == N, and no exception
    """
    app, utub_id, invite_id, _ = committed_invite_utub
    joiner_ids = add_users(app, limit + 2)
    exec_sql(
        app,
        'UPDATE "UtubInviteLinks" SET "maxUses" = %s WHERE id = %s',
        (limit, invite_id),
    )

    spawned: list[tuple[threading.Thread, Box]] = []
    with held_lock(app, LOCK_UTUB_SQL, utub_id):
        for joiner_id in joiner_ids:
            spawned.append(
                spawn(lambda uid=joiner_id: _join_worker(app, uid, invite_id))
            )
        threads = [thread for thread, _ in spawned]
        wait_until_blocked(app, threads, expected=len(threads))
    join_all(app, threads)

    results = [box[0] for _, box in spawned]
    outcomes = [outcome for outcome, _ in results]
    assert ERROR_OUTCOME not in outcomes, results
    assert outcomes.count(InviteJoinOutcome.JOINED.value) == limit, results
    assert outcomes.count(InviteJoinOutcome.DEAD.value) == len(joiner_ids) - limit
    assert member_count(app, utub_id) == 1 + limit
    assert acceptance_count(app, invite_id) == limit
    assert use_count(app, invite_id) == limit


def test_manager_lowering_uses_wins_over_queued_join(
    committed_invite_utub, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    GIVEN use_count=1, max_uses=5 and the real PATCH holding Utubs then the invite lock
    WHEN a join queues on the Utubs row and the PATCH lowers max_uses to 1
    THEN the PATCH is 200, the join is DEAD with no acceptance and use_count stays 1
    """
    app, utub_id, invite_id, user_ids = committed_invite_utub
    exec_sql(
        app,
        'UPDATE "UtubInviteLinks" SET "useCount" = %s, "maxUses" = %s WHERE id = %s',
        (SEEDED_USE_COUNT, SEEDED_MAX_USES, invite_id),
    )
    spawned: list[tuple[threading.Thread, Box]] = []
    hook_errors: list[AssertionError] = []

    def _lock_then_queue_join(*, utub_id: int) -> Utub_Invite_Links | None:
        """Real invite lock, then (both locks held) queue the join behind Utubs."""
        locked = lock_current_invite_for_update(utub_id=utub_id)
        try:
            spawned.append(
                spawn(lambda: _join_worker(app, user_ids[MEMBER_INDEX], invite_id))
            )
            wait_until_blocked(app, [spawned[0][0]], expected=1)
        except AssertionError as queue_error:
            # The request would swallow this into a 500; surface it from the test.
            hook_errors.append(queue_error)
        return locked

    monkeypatch.setattr(
        manage_invite_link, "lock_current_invite_for_update", _lock_then_queue_join
    )
    patch = _prepare_lower_uses(app, utub_id, user_ids[CREATOR_INDEX], LOWERED_MAX_USES)
    patch_result = patch()
    assert not hook_errors, hook_errors
    join_all(app, [spawned[0][0]])

    _assert_patch_outcome(patch_result, status=200, error_code=None)
    assert spawned[0][1] == [(InviteJoinOutcome.DEAD.value, None)]
    assert acceptance_count(app, invite_id) == 0
    assert use_count(app, invite_id) == SEEDED_USE_COUNT
    assert max_uses(app, invite_id) == LOWERED_MAX_USES
    assert member_count(app, utub_id) == 1


def test_join_in_progress_wins_over_queued_manager(committed_invite_utub) -> None:
    """
    GIVEN use_count=1, max_uses=5 and a holder on only the invite row
    WHEN a join takes Utubs and blocks on the invite, then the real PATCH blocks on Utubs
    THEN after release the join is JOINED and the PATCH sees use_count=2, so lowering
         max_uses to 1 is 400 USES_BELOW_JOINED and max_uses stays 5 (fails if the join
         ever locked the invite first)
    """
    app, utub_id, invite_id, user_ids = committed_invite_utub
    exec_sql(
        app,
        'UPDATE "UtubInviteLinks" SET "useCount" = %s, "maxUses" = %s WHERE id = %s',
        (SEEDED_USE_COUNT, SEEDED_MAX_USES, invite_id),
    )
    patch = _prepare_lower_uses(app, utub_id, user_ids[CREATOR_INDEX], LOWERED_MAX_USES)
    with held_lock(app, LOCK_INVITE_SQL, invite_id):
        join_thread, join_box = spawn(
            lambda: _join_worker(app, user_ids[MEMBER_INDEX], invite_id)
        )
        wait_until_blocked(app, [join_thread], expected=1)
        patch_thread, patch_box = spawn(patch)
        wait_until_blocked(app, [join_thread, patch_thread], expected=2)
    join_all(app, [join_thread, patch_thread])

    assert join_box == [(InviteJoinOutcome.JOINED.value, utub_id)]
    _assert_patch_outcome(
        patch_box[0], status=400, error_code=InviteLinkErrorCodes.USES_BELOW_JOINED
    )
    assert max_uses(app, invite_id) == SEEDED_MAX_USES
    assert use_count(app, invite_id) == SEEDED_USE_COUNT + 1
    assert acceptance_count(app, invite_id) == 1


def test_double_submit_counts_once(committed_invite_utub) -> None:
    """
    GIVEN one actor submitting Join twice, both queued behind the Utubs row lock
    WHEN the lock is released
    THEN one is JOINED and the other ALREADY_MEMBER, with one member row, one
         acceptance, use_count == 1 and no integrity error
    """
    app, utub_id, invite_id, user_ids = committed_invite_utub
    actor_id = user_ids[MEMBER_INDEX]
    with held_lock(app, LOCK_UTUB_SQL, utub_id):
        spawned = [
            spawn(lambda: _join_worker(app, actor_id, invite_id)) for _ in range(2)
        ]
        threads = [thread for thread, _ in spawned]
        wait_until_blocked(app, threads, expected=2)
    join_all(app, threads)

    results = sorted(box[0] for _, box in spawned)
    assert results == sorted(
        [
            (InviteJoinOutcome.JOINED.value, utub_id),
            (InviteJoinOutcome.ALREADY_MEMBER.value, utub_id),
        ]
    ), results
    assert member_count(app, utub_id) == 2
    assert acceptance_count(app, invite_id) == 1
    assert use_count(app, invite_id) == 1


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


# (case id, actor index, mutation, expected outcome, rows locked: 0 none, 1 Utubs, 2 Utubs and invite)
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
        exec_sql(
            app,
            'UPDATE "Users" SET "emailValidated" = false WHERE id = %s',
            (user_ids[actor_index],),
        )
    elif mutation == "trash":
        exec_sql(
            app,
            'UPDATE "Utubs" SET "deletedAt" = now() WHERE id = %s',
            (utub_id,),
        )
    elif mutation == "revoke":
        exec_sql(
            app,
            'UPDATE "UtubInviteLinks" SET "revokedAt" = now() WHERE id = %s',
            (invite_id,),
        )

    with app.app_context():
        actor = db.session.get(Users, user_ids[actor_index])
        invite = db.session.get(Utub_Invite_Links, invite_id)
        assert invite.token == COMMITTED_INVITE_TOKEN
        if mutation == "purge":
            exec_sql(app, 'DELETE FROM "UtubInviteLinks" WHERE id = %s', (invite_id,))
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
