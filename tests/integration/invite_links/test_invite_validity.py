"""Tests for the invite link validity evaluator and the invite row lock."""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from flask import Flask

from backend import db
from backend.invite_links.constants import INVITE_LINK_DEFAULT_TTL, InviteState
from backend.invite_links.guards import (
    lock_current_invite_for_update,
    lock_invite_for_update,
)
from backend.invite_links.validity import evaluate_invite, is_invite_live
from backend.models.utub_invite_links import Utub_Invite_Links
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utubs import Utubs
from backend.utils.datetime_utils import utc_now
from tests.utils_for_test import add_invite_link, lock_utub, trash_utub

pytestmark = pytest.mark.invite_links

TOKEN: str = "T" * 22
CREATOR_ID: int = 1
UTUB_ID: int = 1
OTHER_UTUB_ID: int = 2
OTHER_CREATOR_ID: int = 2


def _make_invite(
    *,
    created_by: int | None = CREATOR_ID,
    expires_at: datetime | None = None,
    max_uses: int | None = None,
    use_count: int = 0,
    revoked: bool = False,
) -> Utub_Invite_Links:
    invite = Utub_Invite_Links(
        utub_id=UTUB_ID,
        token=TOKEN,
        created_by=created_by,
        expires_at=expires_at or utc_now() + INVITE_LINK_DEFAULT_TTL,
        max_uses=max_uses,
    )
    invite.use_count = use_count
    if revoked:
        invite.revoked_at = utc_now()
    db.session.add(invite)
    db.session.commit()
    return invite


def _set_creator_role(role: Member_Role) -> None:
    membership = db.session.get(Utub_Members, (UTUB_ID, CREATOR_ID))
    assert membership is not None
    membership.member_role = role
    db.session.commit()


def _remove_creator_membership() -> None:
    membership = db.session.get(Utub_Members, (UTUB_ID, CREATOR_ID))
    assert membership is not None
    db.session.delete(membership)
    db.session.commit()


def _past() -> datetime:
    return utc_now() - timedelta(seconds=1)


@pytest.mark.parametrize(
    "case, expected",
    [
        ("revoked", InviteState.REVOKED),
        ("expired", InviteState.EXPIRED),
        ("used_up", InviteState.USED_UP),
        ("null_creator", InviteState.CREATOR_NOT_MANAGER),
        ("creator_not_member", InviteState.CREATOR_NOT_MANAGER),
        ("creator_demoted", InviteState.CREATOR_NOT_MANAGER),
        ("trashed", InviteState.UTUB_TRASHED),
        ("locked", InviteState.UTUB_LOCKED),
    ],
)
def test_each_condition_alone_denies(
    app: Flask, every_user_makes_a_unique_utub, case: str, expected: InviteState
) -> None:
    """
    GIVEN a link where exactly one DD-3 condition fails
    WHEN it is evaluated
    THEN the exact state for that condition is returned and it is not live
    """
    with app.app_context():
        kwargs: dict = {}
        if case == "revoked":
            kwargs["revoked"] = True
        elif case == "expired":
            kwargs["expires_at"] = _past()
        elif case == "used_up":
            kwargs.update(max_uses=2, use_count=2)
        elif case == "null_creator":
            kwargs["created_by"] = None
        invite = _make_invite(**kwargs)
        invite_id = invite.id

    if case == "trashed":
        trash_utub(app, UTUB_ID, CREATOR_ID)
    elif case == "locked":
        lock_utub(app, UTUB_ID)

    with app.app_context():
        if case == "creator_not_member":
            _remove_creator_membership()
        elif case == "creator_demoted":
            _set_creator_role(Member_Role.MEMBER)
        invite = db.session.get(Utub_Invite_Links, invite_id)
        state = evaluate_invite(invite)
        assert state is expected
        assert not is_invite_live(state)


@pytest.mark.parametrize("role", [Member_Role.CREATOR, Member_Role.CO_CREATOR])
def test_manager_creator_is_live(
    app: Flask, every_user_makes_a_unique_utub, role: Member_Role
) -> None:
    """
    GIVEN a fresh link whose creator is a CREATOR or CO_CREATOR
    WHEN it is evaluated
    THEN it is LIVE
    """
    with app.app_context():
        _set_creator_role(role)
        assert evaluate_invite(_make_invite()) is InviteState.LIVE


def test_unlimited_uses_is_live(app: Flask, every_user_makes_a_unique_utub) -> None:
    """
    GIVEN a link with max_uses NULL and a high use_count
    WHEN it is evaluated
    THEN it is LIVE
    """
    with app.app_context():
        assert evaluate_invite(_make_invite(use_count=10_000)) is InviteState.LIVE


def test_last_remaining_use_is_live(app: Flask, every_user_makes_a_unique_utub) -> None:
    """
    GIVEN a link with use_count == max_uses - 1
    WHEN it is evaluated
    THEN it is LIVE
    """
    with app.app_context():
        invite = _make_invite(max_uses=5, use_count=4)
        assert evaluate_invite(invite) is InviteState.LIVE


def test_expiry_exactly_now_is_expired(
    app: Flask, every_user_makes_a_unique_utub
) -> None:
    """
    GIVEN a link whose expires_at equals the (patched) current time
    WHEN it is evaluated
    THEN it is EXPIRED
    """
    with app.app_context():
        now = utc_now()
        invite = _make_invite(expires_at=now)
        with patch("backend.invite_links.validity.utc_now", return_value=now):
            assert evaluate_invite(invite) is InviteState.EXPIRED


def test_only_live_state_is_live() -> None:
    """
    GIVEN every InviteState member
    WHEN is_invite_live is called
    THEN only LIVE is True (a future member denies automatically)
    """
    for state in InviteState:
        assert is_invite_live(state) is (state is InviteState.LIVE)


def test_unrecognised_creator_role_denies(
    app: Flask, every_user_makes_a_unique_utub
) -> None:
    """
    GIVEN a creator membership whose role is an unrecognised sentinel
    WHEN the link is evaluated
    THEN evaluate_invite itself returns CREATOR_NOT_MANAGER
    """
    with app.app_context():
        invite = _make_invite()
        stand_in = SimpleNamespace(member_role="not-a-member-role")
        with patch(
            "backend.invite_links.validity.get_fresh_membership",
            return_value=stand_in,
        ):
            assert evaluate_invite(invite) is InviteState.CREATOR_NOT_MANAGER


@pytest.mark.parametrize(
    "setup, expected",
    [
        (("revoked", "expired", "locked"), InviteState.REVOKED),
        (("expired", "locked"), InviteState.EXPIRED),
        (("trashed", "locked"), InviteState.UTUB_TRASHED),
        (("demoted", "trashed"), InviteState.CREATOR_NOT_MANAGER),
        (("used_up", "locked"), InviteState.USED_UP),
        (("used_up", "demoted"), InviteState.USED_UP),
        (("expired", "used_up"), InviteState.EXPIRED),
    ],
)
def test_precedence(
    app: Flask,
    every_user_makes_a_unique_utub,
    setup: tuple[str, ...],
    expected: InviteState,
) -> None:
    """
    GIVEN a link failing several conditions at once
    WHEN it is evaluated
    THEN the earliest condition in the contract order is reported
    """
    with app.app_context():
        kwargs: dict = {}
        if "revoked" in setup:
            kwargs["revoked"] = True
        if "expired" in setup:
            kwargs["expires_at"] = _past()
        if "used_up" in setup:
            kwargs.update(max_uses=1, use_count=1)
        invite_id = _make_invite(**kwargs).id
        if "demoted" in setup:
            _set_creator_role(Member_Role.MEMBER)

    if "trashed" in setup:
        trash_utub(app, UTUB_ID, CREATOR_ID)
    if "locked" in setup:
        lock_utub(app, UTUB_ID)

    with app.app_context():
        invite = db.session.get(Utub_Invite_Links, invite_id)
        assert evaluate_invite(invite) is expected


def test_evaluate_writes_nothing(app: Flask, every_user_makes_a_unique_utub) -> None:
    """
    GIVEN a live link
    WHEN it is evaluated
    THEN the session has no pending changes afterwards
    """
    with app.app_context():
        invite = _make_invite()
        evaluate_invite(invite)
        assert not db.session.dirty
        assert not db.session.new
        assert not db.session.deleted
        assert db.session.get(Utubs, UTUB_ID) is not None


def test_lock_current_invite_ignores_revoked_and_other_utubs(
    app: Flask, every_user_makes_a_unique_utub
) -> None:
    """
    GIVEN a revoked and an unrevoked link in UTub 1 and an unrevoked link in UTub 2
    WHEN lock_current_invite_for_update runs for each UTub, and for one with no links
    THEN UTub 1 gets only its unrevoked row, UTub 2 gets its own, and None otherwise
    """
    revoked_id = add_invite_link(app, UTUB_ID, CREATOR_ID, revoked=True)
    live_id = add_invite_link(app, UTUB_ID, CREATOR_ID)
    other_id = add_invite_link(app, OTHER_UTUB_ID, OTHER_CREATOR_ID)

    with app.app_context():
        locked = lock_current_invite_for_update(utub_id=UTUB_ID)
        assert locked is not None
        assert locked.id == live_id
        assert locked.id != revoked_id
        db.session.rollback()

        other = lock_current_invite_for_update(utub_id=OTHER_UTUB_ID)
        assert other is not None
        assert other.id == other_id
        db.session.rollback()

        assert lock_current_invite_for_update(utub_id=OTHER_UTUB_ID + 100) is None
        db.session.rollback()


def test_lock_current_invite_none_when_only_revoked(
    app: Flask, every_user_makes_a_unique_utub
) -> None:
    """
    GIVEN a UTub whose only link is revoked
    WHEN lock_current_invite_for_update runs
    THEN it returns None
    """
    add_invite_link(app, UTUB_ID, CREATOR_ID, revoked=True)
    with app.app_context():
        assert lock_current_invite_for_update(utub_id=UTUB_ID) is None
        db.session.rollback()


def test_lock_invite_returns_row_and_none_for_missing(
    app: Flask, every_user_makes_a_unique_utub
) -> None:
    """
    GIVEN an existing invite id and a missing one
    WHEN lock_invite_for_update is called
    THEN the row is returned for the first and None for the second
    """
    with app.app_context():
        invite_id = _make_invite().id
        locked = lock_invite_for_update(invite_id=invite_id)
        assert locked is not None
        assert locked.id == invite_id
        db.session.rollback()
        assert lock_invite_for_update(invite_id=invite_id + 9999) is None
        db.session.rollback()
