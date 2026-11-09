from __future__ import annotations

from typing import Any

import pytest

from backend.members.member_visibility import (
    member_list_hidden_for,
    viewer_is_manager_from_role,
    visible_member_ids,
)
from backend.models.utub_members import Member_Role

pytestmark = pytest.mark.unit

_ROLE_EXPECTED: dict[Member_Role, bool] = {
    Member_Role.CREATOR: True,
    Member_Role.CO_CREATOR: True,
    Member_Role.MEMBER: False,
}

# (raw settings, hidden for a plain member)
_PLAIN_MEMBER_CASES: list[tuple[Any, bool]] = [
    (None, False),
    ({}, False),
    ({"members": {}}, False),
    ({"members": {"members_can_add": True}}, False),
    ({"members": {"hide_member_list": True}}, True),
    ({"members": {"hide_member_list": False}}, False),
    ({"members": {"hide_member_list": True, "members_can_add": "bad"}}, True),
    ("garbage", True),
    ([], True),
    ({"members": "garbage"}, True),
    ({"members": ["x"]}, True),
    ({"members": {"hide_member_list": 0}}, True),
    ({"members": {"hide_member_list": "false"}}, True),
    ({"members": {"hide_member_list": None}}, True),
]


@pytest.mark.parametrize("settings,expected", _PLAIN_MEMBER_CASES)
def test_plain_member_matrix(settings: Any, expected: bool):
    assert (
        member_list_hidden_for(settings=settings, viewer_is_manager=False) is expected
    )


@pytest.mark.parametrize("settings,_expected", _PLAIN_MEMBER_CASES)
def test_manager_is_never_hidden(settings: Any, _expected: bool):
    assert member_list_hidden_for(settings=settings, viewer_is_manager=True) is False


@pytest.mark.parametrize("settings,_expected", _PLAIN_MEMBER_CASES)
def test_unknown_role_is_always_hidden(settings: Any, _expected: bool):
    assert member_list_hidden_for(settings=settings, viewer_is_manager=None) is True


def test_role_converter_pinned_to_every_enum_member():
    assert set(_ROLE_EXPECTED) == set(Member_Role)
    for role in Member_Role:
        assert viewer_is_manager_from_role(role.value) is _ROLE_EXPECTED[role]


@pytest.mark.parametrize("role", [None, "", "admin", "Creator", "CREATOR"])
def test_role_converter_unknown_is_none(role: str | None):
    assert viewer_is_manager_from_role(role) is None


def test_visible_member_ids_none_when_not_hidden():
    assert (
        visible_member_ids(
            settings=None,
            viewer_is_manager=False,
            utub_creator_id=1,
            viewer_id=3,
            co_owner_ids=[2],
        )
        is None
    )


def test_visible_member_ids_manager_is_none_even_when_set():
    assert (
        visible_member_ids(
            settings={"members": {"hide_member_list": True}},
            viewer_is_manager=True,
            utub_creator_id=1,
            viewer_id=2,
            co_owner_ids=[2],
        )
        is None
    )


def test_visible_member_ids_unknown_role_is_filtered():
    assert visible_member_ids(
        settings=None,
        viewer_is_manager=None,
        utub_creator_id=1,
        viewer_id=1,
        co_owner_ids=[],
    ) == {1}


def test_visible_member_ids_when_hidden():
    assert visible_member_ids(
        settings={"members": {"hide_member_list": True}},
        viewer_is_manager=False,
        utub_creator_id=1,
        viewer_id=3,
        co_owner_ids=[2],
    ) == {1, 2, 3}
