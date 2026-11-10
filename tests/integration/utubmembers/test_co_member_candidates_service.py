from __future__ import annotations

import pytest
from flask import Flask

from backend import db
from backend.members.services.co_member_search import get_co_member_candidates
from backend.models.users import Users
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utubs import Utubs
from tests.utils_for_test import statements_while, trash_utub

pytestmark = pytest.mark.members


def _make_user(username: str) -> Users:
    """Create an email-validated user with a unique email derived from username."""
    new_user = Users(
        username=username,
        email=f"{username.lower()}@email.com",
        plaintext_password="FakePassword1234",
    )
    new_user.email_validated = True
    db.session.add(new_user)
    db.session.commit()
    return new_user


def _make_utub(creator: Users, name: str) -> Utubs:
    """Create a UTub with `creator` as its CREATOR member."""
    new_utub = Utubs(name=name, utub_creator=creator.id, utub_description="")
    db.session.add(new_utub)
    db.session.commit()

    creator_membership = Utub_Members(member_role=Member_Role.CREATOR)
    creator_membership.utub_id = new_utub.id
    creator_membership.user_id = creator.id
    db.session.add(creator_membership)
    db.session.commit()
    return new_utub


def _add_member(utub: Utubs, user: Users) -> None:
    membership = Utub_Members()
    membership.utub_id = utub.id
    membership.user_id = user.id
    db.session.add(membership)
    db.session.commit()


def test_candidates_ignore_trashed_shared_utub(app: Flask) -> None:
    """A user who shares only a trashed UTub with the requester is not a candidate."""
    with app.app_context():
        requester = _make_user("requester")
        trashed_only = _make_user("trashedonly")

        target = _make_utub(requester, "Target")
        trashed_shared = _make_utub(requester, "TrashedShared")
        _add_member(trashed_shared, trashed_only)
        requester_id = requester.id
        target_id = target.id
        trashed_shared_id = trashed_shared.id

    trash_utub(app, trashed_shared_id, deleted_by=requester_id)

    with app.app_context():
        result = get_co_member_candidates(
            requester_id, Utubs.query.get(target_id), viewer_is_manager=True
        )

        assert result.members == []


def test_shared_count_excludes_trashed_utub(app: Flask) -> None:
    """A candidate sharing one live and one trashed UTub has shared_utub_count 1."""
    with app.app_context():
        requester = _make_user("requester")
        alice = _make_user("alice")

        target = _make_utub(requester, "Target")
        live_shared = _make_utub(requester, "LiveShared")
        trashed_shared = _make_utub(requester, "TrashedShared")
        _add_member(live_shared, alice)
        _add_member(trashed_shared, alice)
        requester_id = requester.id
        target_id = target.id
        trashed_shared_id = trashed_shared.id

    trash_utub(app, trashed_shared_id, deleted_by=requester_id)

    with app.app_context():
        result = get_co_member_candidates(
            requester_id, Utubs.query.get(target_id), viewer_is_manager=True
        )

        assert [member.username for member in result.members] == ["alice"]
        assert result.members[0].shared_utub_count == 1


def test_co_members_computed_with_shared_counts(app: Flask) -> None:
    """Co-members are users sharing >=1 of the requester's UTubs; self and the
    target UTub's existing members are excluded; shared_utub_count is the number
    of the requester's UTubs each candidate belongs to."""
    with app.app_context():
        requester = _make_user("requester")
        alice = _make_user("alice")
        bob = _make_user("bob")
        dave = _make_user("dave")
        charlie = _make_user("charlie")

        target = _make_utub(requester, "Target")
        other_one = _make_utub(requester, "OtherOne")
        other_two = _make_utub(requester, "OtherTwo")

        # OtherOne shares requester + alice + bob + charlie
        _add_member(other_one, alice)
        _add_member(other_one, bob)
        _add_member(other_one, charlie)
        # OtherTwo shares requester + alice + dave
        _add_member(other_two, alice)
        _add_member(other_two, dave)
        # charlie is ALSO an existing member of the target UTub -> excluded
        _add_member(target, charlie)

        result = get_co_member_candidates(requester.id, target, viewer_is_manager=True)

        usernames = [member.username for member in result.members]
        counts = {
            member.username: member.shared_utub_count for member in result.members
        }

        # alice, bob, dave are candidates; charlie (target member) + requester excluded
        assert usernames == ["alice", "bob", "dave"]
        assert counts == {"alice": 2, "bob": 1, "dave": 1}
        assert "charlie" not in counts
        assert "requester" not in counts


def test_ordered_by_lower_username_case_insensitive(app: Flask) -> None:
    """Candidates are ordered case-insensitively by username."""
    with app.app_context():
        requester = _make_user("requester")
        charlie = _make_user("Charlie")
        alice = _make_user("alice")
        bob = _make_user("Bob")

        target = _make_utub(requester, "Target")
        shared = _make_utub(requester, "Shared")
        _add_member(shared, charlie)
        _add_member(shared, alice)
        _add_member(shared, bob)

        result = get_co_member_candidates(requester.id, target, viewer_is_manager=True)

        assert [member.username for member in result.members] == [
            "alice",
            "Bob",
            "Charlie",
        ]


def test_empty_when_no_co_members(app: Flask) -> None:
    """A requester whose other UTubs have no other members gets an empty list."""
    with app.app_context():
        requester = _make_user("requester")
        target = _make_utub(requester, "Target")
        # A second solo UTub with only the requester -> still no co-members
        _make_utub(requester, "Solo")

        result = get_co_member_candidates(requester.id, target, viewer_is_manager=True)

        assert result.members == []


def test_self_and_target_members_excluded(app: Flask) -> None:
    """A shared-UTub user already in the target UTub is excluded, and the
    requester never lists themselves."""
    with app.app_context():
        requester = _make_user("requester")
        already_member = _make_user("alreadymember")

        target = _make_utub(requester, "Target")
        shared = _make_utub(requester, "Shared")
        # already_member shares a UTub with the requester...
        _add_member(shared, already_member)
        # ...but is also already in the target UTub -> excluded
        _add_member(target, already_member)

        result = get_co_member_candidates(requester.id, target, viewer_is_manager=True)

        assert result.members == []


def _hide_list(utub: Utubs, hidden: bool = True) -> None:
    utub.settings = {"members": {"hide_member_list": hidden}}
    db.session.commit()


def _make_hidden_source(requester: Users, prefix: str) -> tuple[Users, Users]:
    """A hidden-list UTub owned by someone else where the requester is a plain member
    alongside one other plain member. Returns (owner, plain member)."""
    owner = _make_user(f"{prefix}owner")
    hidden_member = _make_user(f"{prefix}plain")
    source = _make_utub(owner, f"{prefix}Source")
    _add_member(source, requester)
    _add_member(source, hidden_member)
    _hide_list(source)
    return owner, hidden_member


def test_hidden_target_returns_empty_for_plain_member_only(app: Flask) -> None:
    """A hidden-list target yields no candidates for a plain member (or unknown
    role); a manager's result is unchanged."""
    with app.app_context():
        requester = _make_user("requester")
        other = _make_user("other")
        shared = _make_utub(requester, "Shared")
        _add_member(shared, other)
        target = _make_utub(_make_user("targetowner"), "Target")
        _add_member(target, requester)
        _hide_list(target)

        plain = get_co_member_candidates(requester.id, target, viewer_is_manager=False)
        unknown = get_co_member_candidates(requester.id, target, viewer_is_manager=None)
        manager = get_co_member_candidates(requester.id, target, viewer_is_manager=True)

        assert plain.members == []
        assert unknown.members == []
        assert [member.username for member in manager.members] == ["other"]


def test_hidden_source_contributes_only_owner_and_co_owner(app: Flask) -> None:
    """Someone shared only via a hidden-list source appears only as its owner or
    co-owner, and shared_utub_count excludes the hidden source for hidden people."""
    with app.app_context():
        requester = _make_user("requester")
        target = _make_utub(requester, "Target")
        owner, hidden_member = _make_hidden_source(requester, "y")
        co_owner = _make_user("ycoowner")
        source = Utubs.query.filter(Utubs.utub_creator == owner.id).one()
        co_membership = Utub_Members(member_role=Member_Role.CO_CREATOR)
        co_membership.utub_id = source.id
        co_membership.user_id = co_owner.id
        db.session.add(co_membership)
        visible = _make_utub(requester, "Visible")
        _add_member(visible, owner)
        db.session.commit()

        result = get_co_member_candidates(requester.id, target, viewer_is_manager=True)

        counts = {
            member.username: member.shared_utub_count for member in result.members
        }
        assert counts == {"yowner": 2, "ycoowner": 1}
        assert hidden_member.username not in counts


def test_candidates_statement_count_independent_of_hidden_sources(app: Flask) -> None:
    """The per-source filter must not issue per-source queries (no N+1)."""
    with app.app_context():
        requester = _make_user("requester")
        target = _make_utub(requester, "Target")
        _make_hidden_source(requester, "one")
        target_id = target.id
        requester_id = requester.id

        results: list[list[str]] = []

        def run() -> None:
            result = get_co_member_candidates(
                requester_id, Utubs.query.get(target_id), viewer_is_manager=True
            )
            results.append([member.username for member in result.members])

        db.session.expire_all()
        run()
        db.session.expire_all()
        one_source = len(statements_while(run))

        for index in range(3):
            _make_hidden_source(requester, f"many{index}")
        db.session.expire_all()
        run()
        db.session.expire_all()
        several_sources = len(statements_while(run))

        assert one_source == several_sources
        # The filter ran: only each source's owner is suggested, never its plain member.
        assert results[-1] == sorted(
            ["oneowner", "many0owner", "many1owner", "many2owner"], key=str.lower
        )


def test_candidate_in_hidden_and_visible_source_counts_only_visible(
    app: Flask,
) -> None:
    with app.app_context():
        requester = _make_user("requester")
        target = _make_utub(requester, "Target")
        _owner, hidden_member = _make_hidden_source(requester, "y")
        visible = _make_utub(requester, "Visible")
        _add_member(visible, hidden_member)

        result = get_co_member_candidates(requester.id, target, viewer_is_manager=True)

        counts = {
            member.username: member.shared_utub_count for member in result.members
        }
        assert counts["yplain"] == 1


def test_requester_managing_hidden_source_sees_its_members(app: Flask) -> None:
    with app.app_context():
        requester = _make_user("requester")
        target = _make_utub(requester, "Target")
        member = _make_user("plainpal")
        owned = _make_utub(requester, "Owned")
        _add_member(owned, member)
        _hide_list(owned)

        result = get_co_member_candidates(requester.id, target, viewer_is_manager=True)

        assert [member.username for member in result.members] == ["plainpal"]


@pytest.mark.parametrize(
    "settings,expect_visible",
    [
        ({"members": "x"}, False),
        ({"members": {"hide_member_list": "yes"}}, False),
        ({"members": {"hide_member_list": False}}, True),
        (None, True),
    ],
)
def test_source_settings_fail_closed(
    app: Flask, settings: object, expect_visible: bool
) -> None:
    with app.app_context():
        requester = _make_user("requester")
        target = _make_utub(requester, "Target")
        owner = _make_user("srcowner")
        plain = _make_user("srcplain")
        source = _make_utub(owner, "Source")
        _add_member(source, requester)
        _add_member(source, plain)
        source.settings = settings
        db.session.commit()

        result = get_co_member_candidates(requester.id, target, viewer_is_manager=True)

        names = {member.username for member in result.members}
        assert ("srcplain" in names) is expect_visible
        assert "srcowner" in names
