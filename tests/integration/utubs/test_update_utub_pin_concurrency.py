"""Real two-connection proofs for ``PATCH /utubs/<id>/pin``.

Runs on ``build_app`` (real commits, one connection per request thread), not the
SAVEPOINT harness, so locks are genuine. Proves that:

- two concurrent pins of different UTubs by one user cannot both pass the cap
  (the per-user advisory lock is taken before the count), and
- a pin racing an erasure of the same user queues on the membership row and then
  answers 404, with no deadlock (the advisory lock never conflicts with
  ``erase_user_core``).
"""

from __future__ import annotations

import threading
import time
from unittest import mock

import pytest
from flask import Flask, url_for

from backend import db
from backend.admin.account_data_service import erase_user_core
from backend.models.users import Users
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utubs import Utubs
from backend.utils.all_routes import ROUTES
from backend.utils.datetime_utils import utc_now
from backend.utubs.constants import MAX_PINNED_UTUBS
from backend.utubs.services.update_utub_pin import count_live_pinned_utubs
from tests.integration.invite_links.concurrency_helpers import (
    assert_no_server_error,
    join_all,
    prepare_request,
    run_concurrently,
    spawn,
    wait_until_blocked,
)
from tests.integration.short_links.test_mint_short_link_concurrency import (
    ThreadResult,
)
from tests.integration.utubmembers.test_owner_mutation_concurrency import (
    OWNER_USER_ID,
    committed_owner_utub,  # noqa: F401  (fixture reused as a base seed)
)

pytestmark = pytest.mark.utubs

COUNT_PATH = "backend.utubs.services.update_utub_pin.count_live_pinned_utubs"
HOLD_SECONDS = 0.5
SeedType = tuple[Flask, int, list[int]]


def _slow_count(user_id: int) -> int:
    """Hold the freshly read count for a moment before the commit, so an
    unserialized second pin would read the same stale count and also commit."""
    count = count_live_pinned_utubs(user_id)
    time.sleep(HOLD_SECONDS)
    return count


def _add_pinned_utubs(
    app: Flask, user_id: int, count: int, *, pinned: bool
) -> list[int]:
    """Commit ``count`` extra UTubs created by the user, optionally pinned."""
    utub_ids: list[int] = []
    with app.app_context():
        for index in range(count):
            new_utub = Utubs(
                name=f"Race Pin {index}", utub_creator=user_id, utub_description=""
            )
            db.session.add(new_utub)
            db.session.commit()
            membership = Utub_Members(member_role=Member_Role.CREATOR)
            membership.utub_id = new_utub.id
            membership.user_id = user_id
            if pinned:
                membership.pinned_at = utc_now()
            db.session.add(membership)
            db.session.commit()
            utub_ids.append(new_utub.id)
    return utub_ids


def _pin_url(app: Flask, utub_id: int) -> str:
    with app.test_request_context():
        return url_for(ROUTES.UTUBS.UPDATE_UTUB_PIN, utub_id=utub_id)


def _total_pins(app: Flask, user_id: int) -> int:
    with app.app_context():
        return Utub_Members.query.filter(
            Utub_Members.user_id == user_id, Utub_Members.pinned_at.is_not(None)
        ).count()


def test_concurrent_pins_of_different_utubs_respect_the_cap(
    committed_owner_utub: SeedType,  # noqa: F811
) -> None:
    """
    GIVEN a user with 4 pins and a count slowed down before the commit
    WHEN two concurrent requests pin two different unpinned UTubs
    THEN exactly one gets 200, the other 409, and the DB holds 5 pins (the
        per-user advisory lock serializes the count-then-write)
    """
    app, base_utub_id, _ = committed_owner_utub
    _add_pinned_utubs(app, OWNER_USER_ID, MAX_PINNED_UTUBS - 1, pinned=True)
    other_utub_id = _add_pinned_utubs(app, OWNER_USER_ID, 1, pinned=False)[0]
    first_url = _pin_url(app, base_utub_id)
    second_url = _pin_url(app, other_utub_id)

    with mock.patch(COUNT_PATH, _slow_count):
        results = run_concurrently(
            {
                "first": lambda: _send(app, first_url),
                "second": lambda: _send(app, second_url),
            }
        )

    assert sorted(status for status, _ in results.values()) == [200, 409]
    assert _total_pins(app, OWNER_USER_ID) == MAX_PINNED_UTUBS


def _send(app: Flask, url: str) -> ThreadResult:
    return prepare_request(app, OWNER_USER_ID, "patch", url, {"pinned": True})()


def test_pin_racing_an_erasure_of_the_same_user_gets_404_without_deadlock(
    committed_owner_utub: SeedType,  # noqa: F811
) -> None:
    """
    GIVEN a user with 4+ live UTubs and an erasure of that user holding its
        locks before commit
    WHEN the user's pin request starts and queues behind the erasure
    THEN the erasure commits cleanly, the pin answers 404 (membership gone),
        no pin rows remain and nothing is a 5xx or a deadlock
    """
    app, base_utub_id, _ = committed_owner_utub
    _add_pinned_utubs(app, OWNER_USER_ID, MAX_PINNED_UTUBS - 1, pinned=True)
    send_pin = prepare_request(
        app, OWNER_USER_ID, "patch", _pin_url(app, base_utub_id), {"pinned": True}
    )

    erasure_locked = threading.Event()
    release_erasure = threading.Event()

    erase_errors: list[BaseException] = []

    def _erase() -> str:
        try:
            with app.app_context():
                target = Users.query.get(OWNER_USER_ID)
                erase_user_core(target_user=target)
                erasure_locked.set()
                release_erasure.wait(timeout=30)
                db.session.commit()
        except BaseException as error:
            erase_errors.append(error)
            raise
        finally:
            erasure_locked.set()
        return "committed"

    erasure_thread, erasure_box = spawn(_erase)
    try:
        assert erasure_locked.wait(timeout=30), "erasure never took its locks"
        assert not erase_errors, f"erase_user_core raised: {erase_errors!r}"
        pin_thread, pin_box = spawn(send_pin)
        wait_until_blocked(app, [pin_thread], 1)
    finally:
        release_erasure.set()
    join_all(app, [erasure_thread, pin_thread])

    assert erasure_box == ["committed"]
    pin_status, pin_body = pin_box[0]
    assert_no_server_error((pin_status, pin_body))
    assert pin_status == 404
    assert _total_pins(app, OWNER_USER_ID) == 0
