"""Real two-connection race tests for owner/role mutations (issue #757).

The standard ``db_transaction`` harness runs every test on ONE connection inside
a SAVEPOINT, so a genuine lock race cannot happen there. These tests run on
``build_app`` with real commits and two request threads (each with its own
SQLAlchemy session/connection). A ``threading.Barrier(2)`` patched into the
route's pre-lock check (the owner check, or ``lock_and_reauthorize`` itself) makes both requests deterministically pass the
stale, unlocked authorization before either one mutates.
"""

from __future__ import annotations

import threading
from typing import Any, Callable, Generator, Tuple
from unittest import mock

import pytest
from flask import Flask, url_for
from flask_session.redis import RedisSessionInterface
from redis import Redis
from sqlalchemy import text

from backend import db
from backend.api_common.request_utils import is_current_utub_owner
from backend.models.users import Users
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utubs import Utubs
from backend.utils.all_routes import ROUTES
from backend.utils.strings import model_strs
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.model_strs import MODELS
from backend.utils.strings.user_strs import MEMBER_FAILURE
from backend.utils.strings.utub_strs import UTUB_FAILURE
from backend.utubs.guards import lock_and_reauthorize
from tests.conftest import AjaxFlaskLoginClient
from tests.integration.utils import flush_member_add_lookup_keys
from tests.models_for_test import valid_user_1, valid_user_2, valid_user_3
from tests.utils_for_test import get_csrf_token, set_member_role

pytestmark = pytest.mark.members

BARRIER_TIMEOUT_SECONDS = 5
THREAD_JOIN_TIMEOUT_SECONDS = 30
OWNER_USER_ID = 1

# Not a member of the seeded UTub: the add-member race test adds them.
_NON_MEMBER_USER: dict[str, str] = {
    model_strs.USERNAME: "RaceNonMember1234",
    model_strs.EMAIL: "RaceNonMember@email.com",
    model_strs.PASSWORD: "RaceNonMemberPassword1234",
}

ThreadResult = Tuple[int, Any]


@pytest.fixture(autouse=True)
def _flush_member_add_lookup_counter(
    build_app,
) -> Generator[None, None, None]:
    """Override the directory's autouse fixture by name so it does NOT depend on
    ``app`` (and therefore does not activate the SAVEPOINT ``db_transaction``).
    Still flushes the per-user ``member-add-lookup:*`` Redis counter before and
    after, since it survives DB teardown."""
    app, _ = build_app
    flush_member_add_lookup_keys(app)
    yield
    flush_member_add_lookup_keys(app)


@pytest.fixture
def committed_owner_utub(
    build_app,
) -> Generator[Tuple[Flask, int, list[int]], None, None]:
    """Commit 4 users and a UTub owned by user 1 (members 2 and 3; user 4 is a
    non-member) with real commits, then TRUNCATE on teardown so the shared
    session-scoped schema (and its indexes) is left intact and empty."""
    app, _ = build_app
    credentials = [
        valid_user_1,
        valid_user_2,
        valid_user_3,
        _NON_MEMBER_USER,
    ]
    with app.app_context():
        user_ids: list[int] = []
        for credential in credentials:
            new_user = Users(
                username=credential[model_strs.USERNAME],
                email=credential[model_strs.EMAIL].lower(),
                plaintext_password=credential[model_strs.PASSWORD],
            )
            new_user.email_validated = True
            db.session.add(new_user)
            db.session.commit()
            user_ids.append(new_user.id)

        new_utub = Utubs(
            name="Race UTub", utub_creator=user_ids[0], utub_description=""
        )
        db.session.add(new_utub)
        db.session.commit()
        utub_id: int = new_utub.id

        roles = (Member_Role.CREATOR, Member_Role.MEMBER, Member_Role.MEMBER)
        for member_user_id, role in zip(user_ids[:3], roles):
            membership = Utub_Members(member_role=role)
            membership.utub_id = utub_id
            membership.user_id = member_user_id
            db.session.add(membership)
        db.session.commit()

    yield app, utub_id, user_ids

    with app.app_context():
        # SET LOCAL ends at commit, so it does not leak onto the pooled
        # connection; a stuck request thread still holding a lock makes the
        # TRUNCATE fail loudly after 10s instead of hanging the worker.
        db.session.execute(text("SET LOCAL lock_timeout = '10s'"))
        db.session.execute(
            text(
                'TRUNCATE TABLE "Users", "Utubs", "UtubMembers" RESTART IDENTITY CASCADE'
            )
        )
        db.session.commit()
    if isinstance(app.session_interface, RedisSessionInterface):
        client: Redis = app.session_interface.client
        client.flushdb()


def _run_concurrently(
    callables: dict[str, Callable[[], ThreadResult]],
) -> dict[str, ThreadResult]:
    """Run each callable on its own daemon thread; return results by label."""
    results: dict[str, ThreadResult] = {}
    thread_errors: list[BaseException] = []
    results_lock = threading.Lock()

    def _worker(label: str, target: Callable[[], ThreadResult]) -> None:
        try:
            result = target()
            with results_lock:
                results[label] = result
        except BaseException as thread_error:
            with results_lock:
                thread_errors.append(thread_error)

    threads = [
        threading.Thread(target=_worker, args=(label, target), daemon=True)
        for label, target in callables.items()
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=THREAD_JOIN_TIMEOUT_SECONDS)

    stuck = [thread for thread in threads if thread.is_alive()]
    assert stuck == [], "request threads still running after join timeout"
    assert thread_errors == []
    return results


def _request_as_owner(
    app: Flask,
    user_id: int,
    method: str,
    url: str,
    json_body: dict[str, Any],
) -> ThreadResult:
    """Log in as ``user_id`` on a fresh client and send one mutating request."""
    app.test_client_class = AjaxFlaskLoginClient
    with app.app_context():
        user = Users.query.get(user_id)
    with app.test_client(user=user) as client:
        home_response = client.get("/home")
        csrf_token = get_csrf_token(home_response.get_data(), meta_tag=True)
        response = getattr(client, method)(
            url, json=json_body, headers={"X-CSRFToken": csrf_token}
        )
        return response.status_code, response.get_json()


def _barriered_owner_check() -> Callable[[Any], bool]:
    """Wrap the real ``is_current_utub_owner`` so both requests rendezvous after
    passing the unlocked pre-check and before either mutates."""
    barrier = threading.Barrier(2)

    def _wrapper(current_utub: Utubs) -> bool:
        result = is_current_utub_owner(current_utub)
        try:
            barrier.wait(timeout=BARRIER_TIMEOUT_SECONDS)
        except threading.BrokenBarrierError:
            pass
        return result

    return _wrapper


def _creator_state(app: Flask, utub_id: int) -> Tuple[list[int], int]:
    """(user ids holding CREATOR, Utubs.utub_creator) read in a fresh context."""
    with app.app_context():
        creator_ids = [
            membership.user_id
            for membership in Utub_Members.query.filter(
                Utub_Members.utub_id == utub_id,
                Utub_Members.member_role == Member_Role.CREATOR,
            ).all()
        ]
        utub_creator: int = Utubs.query.get(utub_id).utub_creator
    return creator_ids, utub_creator


def _role_of(app: Flask, utub_id: int, user_id: int) -> Member_Role:
    with app.app_context():
        membership: Utub_Members = Utub_Members.query.get((utub_id, user_id))
        return membership.member_role


def test_concurrent_double_transfer_exactly_one_succeeds(
    committed_owner_utub: Tuple[Flask, int, list[int]],
) -> None:
    """
    GIVEN a UTub owned by user 1 with plain members 2 and 3
    WHEN user 1 double-fires PATCH /owner (to 2 and to 3) and both requests pass
        the unlocked owner pre-check before either mutates
    THEN exactly one transfer succeeds (200) and the other is rejected (403),
        leaving a single CREATOR row that matches Utubs.utub_creator
    """
    app, utub_id, user_ids = committed_owner_utub
    with app.test_request_context():
        transfer_url = url_for(ROUTES.MEMBERS.TRANSFER_UTUB_OWNERSHIP, utub_id=utub_id)

    with mock.patch(
        "backend.api_common.auth_decorators.is_current_utub_owner",
        _barriered_owner_check(),
    ):
        results = _run_concurrently(
            {
                "to_second": lambda: _request_as_owner(
                    app,
                    OWNER_USER_ID,
                    "patch",
                    transfer_url,
                    {"new_owner_id": user_ids[1]},
                ),
                "to_third": lambda: _request_as_owner(
                    app,
                    OWNER_USER_ID,
                    "patch",
                    transfer_url,
                    {"new_owner_id": user_ids[2]},
                ),
            }
        )

    statuses = sorted(status for status, _ in results.values())
    assert statuses == [200, 403]
    winner_body = next(body for status, body in results.values() if status == 200)
    loser_body = next(body for status, body in results.values() if status == 403)
    assert loser_body[STD_JSON.MESSAGE] == UTUB_FAILURE.NOT_AUTHORIZED

    winner_id = winner_body[MODELS.NEW_OWNER][MODELS.ID]
    loser_target = ({user_ids[1], user_ids[2]} - {winner_id}).pop()
    creator_ids, utub_creator = _creator_state(app, utub_id)
    assert creator_ids == [winner_id]
    assert utub_creator == winner_id
    assert _role_of(app, utub_id, OWNER_USER_ID) == Member_Role.CO_CREATOR
    assert _role_of(app, utub_id, loser_target) == Member_Role.MEMBER


def test_concurrent_transfer_and_demote_new_owner_keeps_one_creator(
    committed_owner_utub: Tuple[Flask, int, list[int]],
) -> None:
    """
    GIVEN user 2 is a CO_CREATOR and user 1 owns the UTub
    WHEN user 1 transfers ownership to user 2 while concurrently demoting user 2
        to MEMBER, both passing the unlocked owner pre-check
    THEN the transfer succeeds, the role change is 200 or 403, and the UTub ends
        with exactly one CREATOR row: user 2, matching Utubs.utub_creator

    The winner is scheduler-dependent, so only outcome-independent facts are
    asserted (never "exactly one 200").
    """
    app, utub_id, user_ids = committed_owner_utub
    set_member_role(app, utub_id, user_ids[1], Member_Role.CO_CREATOR)
    with app.test_request_context():
        transfer_url = url_for(ROUTES.MEMBERS.TRANSFER_UTUB_OWNERSHIP, utub_id=utub_id)
        demote_url = url_for(
            ROUTES.MEMBERS.MODIFY_MEMBER_ROLE, utub_id=utub_id, user_id=user_ids[1]
        )

    with mock.patch(
        "backend.api_common.auth_decorators.is_current_utub_owner",
        _barriered_owner_check(),
    ):
        results = _run_concurrently(
            {
                "transfer": lambda: _request_as_owner(
                    app,
                    OWNER_USER_ID,
                    "patch",
                    transfer_url,
                    {"new_owner_id": user_ids[1]},
                ),
                "demote": lambda: _request_as_owner(
                    app,
                    OWNER_USER_ID,
                    "patch",
                    demote_url,
                    {"member_role": "member"},
                ),
            }
        )

    transfer_status, _ = results["transfer"]
    demote_status, demote_body = results["demote"]
    assert transfer_status == 200
    assert demote_status in {200, 403}
    if demote_status == 403:
        assert demote_body[STD_JSON.MESSAGE] == UTUB_FAILURE.NOT_AUTHORIZED

    creator_ids, utub_creator = _creator_state(app, utub_id)
    assert creator_ids == [user_ids[1]]
    assert utub_creator == user_ids[1]


def _barriered_lock_and_reauthorize() -> Callable[..., Any]:
    """Wrap the real ``lock_and_reauthorize`` so both requests rendezvous BEFORE
    taking the row lock, i.e. after passing the stale route guard."""
    barrier = threading.Barrier(2)

    def _wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            barrier.wait(timeout=BARRIER_TIMEOUT_SECONDS)
        except threading.BrokenBarrierError:
            pass
        return lock_and_reauthorize(*args, **kwargs)

    return _wrapper


def test_concurrent_double_remove_member_one_success_one_404(
    committed_owner_utub: Tuple[Flask, int, list[int]],
) -> None:
    """
    GIVEN a UTub owned by user 1 with plain member 3
    WHEN user 1 double-fires DELETE of member 3 and both requests pass the stale
        membership guard before either takes the UTub row lock
    THEN exactly one removal succeeds (200) and the other gets 404
        MEMBER_NOT_IN_UTUB, with no unhandled exception in either request
        thread, member 3 gone and user 1 still the single CREATOR
    """
    app, utub_id, user_ids = committed_owner_utub
    with app.test_request_context():
        remove_url = url_for(
            ROUTES.MEMBERS.REMOVE_MEMBER, utub_id=utub_id, user_id=user_ids[2]
        )

    with mock.patch(
        "backend.members.services.delete_members.lock_and_reauthorize",
        _barriered_lock_and_reauthorize(),
    ):
        results = _run_concurrently(
            {
                "first": lambda: _request_as_owner(
                    app, OWNER_USER_ID, "delete", remove_url, {}
                ),
                "second": lambda: _request_as_owner(
                    app, OWNER_USER_ID, "delete", remove_url, {}
                ),
            }
        )

    statuses = sorted(status for status, _ in results.values())
    assert statuses == [200, 404]
    loser_body = next(body for status, body in results.values() if status == 404)
    assert loser_body[STD_JSON.MESSAGE] == MEMBER_FAILURE.MEMBER_NOT_IN_UTUB

    with app.app_context():
        assert Utub_Members.query.get((utub_id, user_ids[2])) is None
    creator_ids, utub_creator = _creator_state(app, utub_id)
    assert creator_ids == [user_ids[0]]
    assert utub_creator == user_ids[0]
