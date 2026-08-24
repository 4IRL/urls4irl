from __future__ import annotations

import pytest
from flask import Flask

from backend import db
from backend.members.services.co_member_search import get_co_member_candidates
from backend.models.users import Users
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utubs import Utubs

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

        result = get_co_member_candidates(requester.id, target)

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

        result = get_co_member_candidates(requester.id, target)

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

        result = get_co_member_candidates(requester.id, target)

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

        result = get_co_member_candidates(requester.id, target)

        assert result.members == []
