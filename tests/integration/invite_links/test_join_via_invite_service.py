"""Tests for ``join_via_invite`` (logic only; locking is proven in the purged and
concurrency modules that use real commits)."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from backend import db
from backend.invite_links.constants import (
    INVITE_LINK_DEFAULT_TTL,
    InviteJoinOutcome,
)
from backend.invite_links.data_models import InviteJoinResult
from backend.invite_links.services.join_via_invite import join_via_invite
from backend.members.constants import MemberAddSource
from backend.metrics.events import EventName
from backend.models.users import Users
from backend.models.utub_invite_acceptances import Utub_Invite_Acceptances
from backend.models.utub_invite_links import Utub_Invite_Links
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utubs import Utubs
from backend.utils.datetime_utils import utc_now
from tests.integration.system.metrics_helpers import (
    count_counter_keys,
    find_counter_keys,
    parse_dims,
)
from tests.utils_for_test import lock_utub, trash_utub

pytestmark = pytest.mark.invite_links

TOKEN: str = "J" * 22
CREATOR_ID: int = 1
JOINER_ID: int = 2
OTHER_JOINER_ID: int = 3
UTUB_ID: int = 1

SERVICE_MODULE: str = "backend.invite_links.services.join_via_invite"


def _make_invite(
    *,
    max_uses: int | None = None,
    use_count: int = 0,
    revoked: bool = False,
    expired: bool = False,
    created_by: int | None = CREATOR_ID,
) -> int:
    invite = Utub_Invite_Links(
        utub_id=UTUB_ID,
        token=TOKEN,
        created_by=created_by,
        expires_at=(
            utc_now() - timedelta(seconds=1)
            if expired
            else utc_now() + INVITE_LINK_DEFAULT_TTL
        ),
        max_uses=max_uses,
    )
    invite.use_count = use_count
    if revoked:
        invite.revoked_at = utc_now()
    db.session.add(invite)
    db.session.commit()
    return invite.id


def _add_member(user_id: int, role: Member_Role) -> None:
    membership = Utub_Members(member_role=role)
    membership.utub_id = UTUB_ID
    membership.user_id = user_id
    db.session.add(membership)
    db.session.commit()


def _join(user_id: int, invite_id: int) -> InviteJoinResult:
    actor = db.session.get(Users, user_id)
    invite = db.session.get(Utub_Invite_Links, invite_id)
    return join_via_invite(actor, invite)


def _assert_nothing_written(user_id: int, invite_id: int, use_count: int = 0) -> None:
    db.session.expire_all()
    assert db.session.get(Utub_Members, (UTUB_ID, user_id)) is None
    assert db.session.get(Utub_Invite_Links, invite_id).use_count == use_count
    assert Utub_Invite_Acceptances.query.count() == 0


def test_join_happy_path(app: Flask, every_user_makes_a_unique_utub) -> None:
    """
    GIVEN a live link and a validated non-member
    WHEN the non-member joins
    THEN a MEMBER row, one acceptance, use_count +1 and a newer last_updated exist
    """
    with app.app_context():
        invite_id = _make_invite()
        before = db.session.get(Utubs, UTUB_ID).last_updated
        result = _join(JOINER_ID, invite_id)
        assert result == InviteJoinResult(InviteJoinOutcome.JOINED, UTUB_ID)

        db.session.expire_all()
        membership = db.session.get(Utub_Members, (UTUB_ID, JOINER_ID))
        assert membership is not None
        assert membership.member_role == Member_Role.MEMBER
        assert db.session.get(Utub_Invite_Links, invite_id).use_count == 1
        acceptances = Utub_Invite_Acceptances.query.all()
        assert len(acceptances) == 1
        assert acceptances[0].invite_id == invite_id
        assert acceptances[0].utub_id == UTUB_ID
        assert acceptances[0].user_id == JOINER_ID
        assert acceptances[0].accepted_at is not None
        assert db.session.get(Utubs, UTUB_ID).last_updated > before


def test_two_joiners_share_invite_and_unlimited_keeps_counting(
    app: Flask, every_user_makes_a_unique_utub
) -> None:
    """
    GIVEN an unlimited live link
    WHEN two different users join
    THEN two acceptance rows share the invite id and use_count is 2
    """
    with app.app_context():
        invite_id = _make_invite()
        assert _join(JOINER_ID, invite_id).outcome is InviteJoinOutcome.JOINED
        assert _join(OTHER_JOINER_ID, invite_id).outcome is InviteJoinOutcome.JOINED
        db.session.expire_all()
        acceptances = Utub_Invite_Acceptances.query.all()
        assert len(acceptances) == 2
        assert {row.invite_id for row in acceptances} == {invite_id}
        assert {row.user_id for row in acceptances} == {JOINER_ID, OTHER_JOINER_ID}
        assert db.session.get(Utub_Invite_Links, invite_id).use_count == 2


@pytest.mark.parametrize(
    "case",
    [
        "revoked",
        "expired",
        "used_up",
        "null_creator",
        "creator_not_member",
        "creator_demoted",
        "trashed",
        "locked",
    ],
)
def test_every_dead_condition_denies_non_member(
    app: Flask, every_user_makes_a_unique_utub, case: str
) -> None:
    """
    GIVEN a link failing exactly one validity condition
    WHEN a non-member joins
    THEN DEAD with no UTub id and nothing written
    """
    with app.app_context():
        kwargs: dict = {}
        used = 0
        if case == "revoked":
            kwargs["revoked"] = True
        elif case == "expired":
            kwargs["expired"] = True
        elif case == "used_up":
            kwargs.update(max_uses=1, use_count=1)
            used = 1
        elif case == "null_creator":
            kwargs["created_by"] = None
        invite_id = _make_invite(**kwargs)

    if case == "trashed":
        trash_utub(app, UTUB_ID, CREATOR_ID)
    elif case == "locked":
        lock_utub(app, UTUB_ID)

    with app.app_context():
        if case == "creator_not_member":
            db.session.delete(db.session.get(Utub_Members, (UTUB_ID, CREATOR_ID)))
            db.session.commit()
        elif case == "creator_demoted":
            db.session.get(
                Utub_Members, (UTUB_ID, CREATOR_ID)
            ).member_role = Member_Role.MEMBER
            db.session.commit()

        result = _join(JOINER_ID, invite_id)
        assert result == InviteJoinResult(InviteJoinOutcome.DEAD, None)
        _assert_nothing_written(JOINER_ID, invite_id, use_count=used)


@pytest.mark.parametrize(
    "gate, expected",
    [
        ("unvalidated", InviteJoinOutcome.ACTOR_UNVALIDATED),
        ("suspended", InviteJoinOutcome.ACTOR_SUSPENDED),
        ("both", InviteJoinOutcome.ACTOR_UNVALIDATED),
    ],
)
@pytest.mark.parametrize("already_member", [False, True])
def test_actor_gate_wins_and_changes_nothing(
    app: Flask,
    every_user_makes_a_unique_utub,
    gate: str,
    expected: InviteJoinOutcome,
    already_member: bool,
) -> None:
    """
    GIVEN a live link and an unvalidated and/or suspended actor (member or not)
    WHEN the actor joins
    THEN the actor outcome is returned (unvalidated first), ahead of ALREADY_MEMBER,
        with utub_id None and nothing written
    """
    with app.app_context():
        invite_id = _make_invite()
        if already_member:
            _add_member(JOINER_ID, Member_Role.MEMBER)
        actor = db.session.get(Users, JOINER_ID)
        if gate in ("unvalidated", "both"):
            actor.email_validated = False
        if gate in ("suspended", "both"):
            actor.is_suspended = True
        db.session.commit()

        result = _join(JOINER_ID, invite_id)
        assert result == InviteJoinResult(expected, None)

        db.session.expire_all()
        assert Utub_Invite_Acceptances.query.count() == 0
        assert db.session.get(Utub_Invite_Links, invite_id).use_count == 0
        member_row = db.session.get(Utub_Members, (UTUB_ID, JOINER_ID))
        assert (member_row is not None) is already_member


@pytest.mark.parametrize(
    "role, user_id",
    [
        (Member_Role.CREATOR, CREATOR_ID),
        (Member_Role.CO_CREATOR, JOINER_ID),
        (Member_Role.MEMBER, JOINER_ID),
    ],
)
@pytest.mark.parametrize("scenario", ["live", "revoked", "locked"])
def test_existing_member_gets_already_member(
    app: Flask,
    every_user_makes_a_unique_utub,
    role: Member_Role,
    user_id: int,
    scenario: str,
) -> None:
    """
    GIVEN a validated, non-suspended member of a live UTub
    WHEN they use a live link, a dead link or a locked UTub's link
    THEN ALREADY_MEMBER with the UTub id, no consumed use, no acceptance
    """
    with app.app_context():
        invite_id = _make_invite(revoked=scenario == "revoked")
        if user_id != CREATOR_ID:
            _add_member(user_id, role)
    if scenario == "locked":
        lock_utub(app, UTUB_ID)

    with app.app_context():
        result = _join(user_id, invite_id)
        assert result == InviteJoinResult(InviteJoinOutcome.ALREADY_MEMBER, UTUB_ID)
        db.session.expire_all()
        assert db.session.get(Utub_Invite_Links, invite_id).use_count == 0
        assert Utub_Invite_Acceptances.query.count() == 0
        assert db.session.get(Utub_Members, (UTUB_ID, user_id)).member_role == role


def test_member_of_trashed_utub_gets_dead(
    app: Flask, every_user_makes_a_unique_utub
) -> None:
    """
    GIVEN a member of a trashed UTub
    WHEN they use its live link
    THEN DEAD with no UTub id
    """
    with app.app_context():
        invite_id = _make_invite()
        _add_member(JOINER_ID, Member_Role.MEMBER)
    trash_utub(app, UTUB_ID, CREATOR_ID)
    with app.app_context():
        assert _join(JOINER_ID, invite_id) == InviteJoinResult(
            InviteJoinOutcome.DEAD, None
        )


def test_missing_utub_row_gets_dead_and_releases_locks(
    app: Flask, every_user_makes_a_unique_utub
) -> None:
    """
    GIVEN an invite whose ``utub_id`` points at no Utubs row
    WHEN a validated non-member joins
    THEN DEAD with no UTub id and nothing written
    """
    stale_utub_id = 99999
    with app.app_context():
        assert db.session.get(Utubs, stale_utub_id) is None
        stale_invite = Utub_Invite_Links(
            utub_id=stale_utub_id,
            token=TOKEN,
            created_by=CREATOR_ID,
            expires_at=utc_now() + INVITE_LINK_DEFAULT_TTL,
        )
        stale_invite.id = 12345
        actor = db.session.get(Users, JOINER_ID)

        result = join_via_invite(actor, stale_invite)

        assert result == InviteJoinResult(InviteJoinOutcome.DEAD, None)
        assert db.session.get(Utub_Members, (stale_utub_id, JOINER_ID)) is None
        assert Utub_Invite_Acceptances.query.count() == 0


def test_join_records_member_added_metric_once(
    metrics_enabled_app,
    provide_metrics_redis,
    every_user_makes_a_unique_utub,
) -> None:
    """
    GIVEN metrics enabled
    WHEN a join succeeds and then a denied join and an already-member join happen
    THEN exactly one MEMBER_ADDED counter with source invite_link exists
    """
    app = metrics_enabled_app
    with app.app_context():
        invite_id = _make_invite()
        assert count_counter_keys(provide_metrics_redis, EventName.MEMBER_ADDED) == 0

        assert _join(JOINER_ID, invite_id).outcome is InviteJoinOutcome.JOINED
        keys = find_counter_keys(provide_metrics_redis, EventName.MEMBER_ADDED)
        assert len(keys) == 1
        assert parse_dims(keys[0])["source"] == MemberAddSource.INVITE_LINK.value
        assert int(provide_metrics_redis.get(keys[0])) == 1

        assert _join(JOINER_ID, invite_id).outcome is InviteJoinOutcome.ALREADY_MEMBER
        invite = db.session.get(Utub_Invite_Links, invite_id)
        invite.revoked_at = utc_now()
        db.session.commit()
        assert _join(OTHER_JOINER_ID, invite_id).outcome is InviteJoinOutcome.DEAD
        assert int(provide_metrics_redis.get(keys[0])) == 1
        assert count_counter_keys(provide_metrics_redis, EventName.MEMBER_ADDED) == 1


def test_join_logs_omit_token_and_run_after_commit(
    app: Flask, every_user_makes_a_unique_utub
) -> None:
    """
    GIVEN a live link
    WHEN a join succeeds
    THEN the logged lines never contain the token, and commit precedes the log
        and the metric call
    """
    with app.app_context():
        invite_id = _make_invite()
        actor = db.session.get(Users, JOINER_ID)
        invite = db.session.get(Utub_Invite_Links, invite_id)

        parent = MagicMock()
        real_commit = db.session.commit

        def recorded_commit() -> None:
            parent.commit()
            real_commit()

        with (
            patch.object(db.session, "commit", side_effect=recorded_commit),
            patch(f"{SERVICE_MODULE}.safe_add_many_logs", parent.logs),
            patch(f"{SERVICE_MODULE}.record_event", parent.metric),
        ):
            result = join_via_invite(actor, invite)

        assert result.outcome is InviteJoinOutcome.JOINED
        names = [call[0] for call in parent.mock_calls]
        assert names == ["commit", "logs", "metric"]
        logged_lines = parent.logs.call_args.args[0]
        assert all(TOKEN not in line for line in logged_lines)
        assert f"UTub.id={UTUB_ID}" in logged_lines
