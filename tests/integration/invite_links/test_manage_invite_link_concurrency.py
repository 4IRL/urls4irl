"""Real-Postgres concurrency proofs for the invite link manage routes.

Depends on ``build_app`` only (via ``committed_manage_utub``): every request commits for
real. Two managers (the creator and a co-owner) send their requests from threads that
queue behind a ``Utubs`` row lock held on a second raw connection; ``pg_stat_activity``
confirms the exact number of queued backends before the lock is released. The UTub lock
is the serialiser, so the one-active-link index must never be the thing that decides.
Every case asserts no 500/599 and compares counts, never which thread won.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Callable

import pytest
from flask import Flask, url_for

from backend import db
from backend.invite_links.constants import INVITE_LINK_DEFAULT_TTL, InviteLinkErrorCodes
from backend.invite_links.token_generator import generate_invite_token
from backend.models.utub_invite_links import Utub_Invite_Links
from backend.utils.all_routes import ROUTES
from backend.utils.datetime_utils import utc_now
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.model_strs import MODELS
from tests.integration.invite_links.concurrency_helpers import (
    LOCK_UTUB_SQL,
    ThreadResult,
    assert_no_server_error,
    held_lock,
    invite_rows,
    join_all,
    prepare_request,
    spawn,
    wait_until_blocked,
)

pytestmark = pytest.mark.invite_links

CREATOR_INDEX: int = 0
CO_OWNER_INDEX: int = 1
CREATED: int = 201
OK: int = 200
NOT_FOUND: int = 404
CONFLICT: int = 409
SETTINGS_BODY: dict[str, int] = {"expires_in_days": 7}


def _route_url(app: Flask, route: str, utub_id: int) -> str:
    with app.test_request_context():
        return url_for(route, utub_id=utub_id)


def _seed_invite(app: Flask, utub_id: int, creator_id: int, *, dead: bool) -> int:
    """Commit one unrevoked row; ``dead`` makes it expired (still unrevoked)."""
    expires_at = (
        utc_now() - timedelta(minutes=1)
        if dead
        else utc_now() + INVITE_LINK_DEFAULT_TTL
    )
    with app.app_context():
        invite = Utub_Invite_Links(
            utub_id=utub_id,
            token=generate_invite_token(),
            created_by=creator_id,
            expires_at=expires_at,
            max_uses=None,
        )
        db.session.add(invite)
        db.session.commit()
        return invite.id


def _race_two_managers(
    app: Flask,
    utub_id: int,
    user_ids: list[int],
    method: str,
    route: str,
    body: dict[str, int] | None,
) -> list[ThreadResult]:
    """Queue the same request from the creator and the co-owner behind a held ``Utubs``
    lock, release it and return both results."""
    url = _route_url(app, route, utub_id)
    senders: list[Callable[[], ThreadResult]] = [
        prepare_request(app, user_ids[index], method, url, body)
        for index in (CREATOR_INDEX, CO_OWNER_INDEX)
    ]
    with held_lock(app, LOCK_UTUB_SQL, utub_id):
        spawned = [spawn(sender) for sender in senders]
        threads = [thread for thread, _ in spawned]
        wait_until_blocked(app, threads, expected=len(threads))
    join_all(app, threads)
    results: list[ThreadResult] = [box[0] for _, box in spawned]
    assert_no_server_error(*results)
    return results


def _error_code(result: ThreadResult) -> int | None:
    return (result[1] or {}).get(STD_JSON.ERROR_CODE)


def _token_of(result: ThreadResult) -> str:
    return result[1][MODELS.INVITE_LINK]["token"]


def _assert_one_created_one_conflict(results: list[ThreadResult]) -> None:
    assert sorted(status for status, _ in results) == [CREATED, CONFLICT], results
    conflict = next(result for result in results if result[0] == CONFLICT)
    assert _error_code(conflict) == InviteLinkErrorCodes.LIVE_LINK_EXISTS, conflict


def test_create_vs_create_one_wins(committed_manage_utub) -> None:
    """
    GIVEN a UTub with no invite row and two managers' creates queued behind the Utubs lock
    WHEN the lock is released
    THEN exactly one is 201, the other 409 LIVE_LINK_EXISTS, with one unrevoked row
    """
    app, utub_id, user_ids = committed_manage_utub

    results = _race_two_managers(
        app,
        utub_id,
        user_ids,
        "post",
        ROUTES.INVITE_LINKS.CREATE_INVITE_LINK,
        SETTINGS_BODY,
    )

    _assert_one_created_one_conflict(results)
    rows = invite_rows(app, utub_id)
    assert [revoked for _, _, revoked in rows] == [False], rows
    created = next(result for result in results if result[0] == CREATED)
    assert rows[0][1] == _token_of(created)


def test_create_vs_create_over_dead_row_revokes_it_once(committed_manage_utub) -> None:
    """
    GIVEN a dead-unrevoked row and two managers' creates queued behind the Utubs lock
    WHEN the lock is released
    THEN exactly one is 201, the other 409 LIVE_LINK_EXISTS; the dead row is revoked and
         exactly one new unrevoked row exists
    """
    app, utub_id, user_ids = committed_manage_utub
    dead_id = _seed_invite(app, utub_id, user_ids[CREATOR_INDEX], dead=True)

    results = _race_two_managers(
        app,
        utub_id,
        user_ids,
        "post",
        ROUTES.INVITE_LINKS.CREATE_INVITE_LINK,
        SETTINGS_BODY,
    )

    _assert_one_created_one_conflict(results)
    rows = invite_rows(app, utub_id)
    assert len(rows) == 2, rows
    assert [(row_id, revoked) for row_id, _, revoked in rows if row_id == dead_id] == [
        (dead_id, True)
    ]
    live = [row for row in rows if not row[2]]
    assert len(live) == 1 and live[0][0] != dead_id, rows
    created = next(result for result in results if result[0] == CREATED)
    assert live[0][1] == _token_of(created)


def test_replace_vs_replace_both_succeed_in_turn(committed_manage_utub) -> None:
    """
    GIVEN a live row and two managers' replaces queued behind the Utubs lock
    WHEN the lock is released
    THEN both are 201 with distinct tokens; three rows exist, the original is revoked
         and exactly one unrevoked row remains, holding one of the returned tokens
    """
    app, utub_id, user_ids = committed_manage_utub
    original_id = _seed_invite(app, utub_id, user_ids[CREATOR_INDEX], dead=False)

    results = _race_two_managers(
        app,
        utub_id,
        user_ids,
        "post",
        ROUTES.INVITE_LINKS.REPLACE_INVITE_LINK,
        SETTINGS_BODY,
    )

    assert [status for status, _ in results] == [CREATED, CREATED], results
    tokens = {_token_of(result) for result in results}
    assert len(tokens) == 2, results
    rows = invite_rows(app, utub_id)
    assert len(rows) == 3, rows
    assert [revoked for row_id, _, revoked in rows if row_id == original_id] == [True]
    live = [row for row in rows if not row[2]]
    assert len(live) == 1, rows
    assert live[0][1] in tokens


def test_revoke_vs_revoke_one_wins(committed_manage_utub) -> None:
    """
    GIVEN a live row and two managers' revokes queued behind the Utubs lock
    WHEN the lock is released
    THEN one is 200 and the other 404 INVITE_LINK_NOT_FOUND; the row is revoked
    """
    app, utub_id, user_ids = committed_manage_utub
    _seed_invite(app, utub_id, user_ids[CREATOR_INDEX], dead=False)

    results = _race_two_managers(
        app,
        utub_id,
        user_ids,
        "delete",
        ROUTES.INVITE_LINKS.REVOKE_INVITE_LINK,
        None,
    )

    assert sorted(status for status, _ in results) == [OK, NOT_FOUND], results
    missing = next(result for result in results if result[0] == NOT_FOUND)
    assert _error_code(missing) == InviteLinkErrorCodes.INVITE_LINK_NOT_FOUND, missing
    assert [revoked for _, _, revoked in invite_rows(app, utub_id)] == [True]
