from typing import Any

import pytest

from backend.invite_links.permissions import (
    can_create_invite_links,
    can_enable_invite_preview,
    creator_may_create,
    creators_from_raw_settings,
)
from backend.models.utub_members import Member_Role
from backend.models.utubs import Utubs
from backend.schemas.utub_settings import InviteLinkCreators

pytestmark = pytest.mark.unit

ALL_ROLES = (Member_Role.CREATOR, Member_Role.CO_CREATOR, Member_Role.MEMBER, None)

# (rule, role) -> may create
CREATE_TABLE: dict[tuple[InviteLinkCreators, Member_Role | None], bool] = {
    (InviteLinkCreators.OWNER_AND_CO_OWNERS, Member_Role.CREATOR): True,
    (InviteLinkCreators.OWNER_AND_CO_OWNERS, Member_Role.CO_CREATOR): True,
    (InviteLinkCreators.OWNER_AND_CO_OWNERS, Member_Role.MEMBER): False,
    (InviteLinkCreators.OWNER_AND_CO_OWNERS, None): False,
    (InviteLinkCreators.OWNER_ONLY, Member_Role.CREATOR): True,
    (InviteLinkCreators.OWNER_ONLY, Member_Role.CO_CREATOR): False,
    (InviteLinkCreators.OWNER_ONLY, Member_Role.MEMBER): False,
    (InviteLinkCreators.OWNER_ONLY, None): False,
    (InviteLinkCreators.NO_ONE, Member_Role.CREATOR): False,
    (InviteLinkCreators.NO_ONE, Member_Role.CO_CREATOR): False,
    (InviteLinkCreators.NO_ONE, Member_Role.MEMBER): False,
    (InviteLinkCreators.NO_ONE, None): False,
}

UNKNOWN_RAW: list[Any] = [
    {"members": {"invite_link_creators": "everyone"}},
    {"members": {"invite_link_creators": 3}},
    {"members": {"invite_link_creators": True}},
    {"members": {"invite_link_creators": None}},
    {"members": {"invite_link_creators": ["no_one"]}},
    {"members": None},
    {"members": "owner_only"},
    {"members": ["x"]},
    ["not", "a", "dict"],
]


def _utub(settings: Any) -> Utubs:
    utub = Utubs(name="utub", utub_creator=1, utub_description="")
    utub.settings = settings
    return utub


@pytest.mark.parametrize("settings", [None, {}, {"members": {}}, {"urls": {}}])
def test_absent_rule_resolves_to_default(settings):
    assert (
        creators_from_raw_settings(settings) == InviteLinkCreators.OWNER_AND_CO_OWNERS
    )


@pytest.mark.parametrize("value", list(InviteLinkCreators))
def test_valid_stored_rule_is_returned(value):
    raw = {"members": {"invite_link_creators": value.value}}
    assert creators_from_raw_settings(raw) == value


@pytest.mark.parametrize("raw", UNKNOWN_RAW)
def test_unknown_stored_rule_is_none(raw):
    assert creators_from_raw_settings(raw) is None


@pytest.mark.parametrize(("rule", "role"), list(CREATE_TABLE))
def test_creator_may_create_table(rule, role):
    assert creator_may_create(creators=rule, role=role) is CREATE_TABLE[(rule, role)]


@pytest.mark.parametrize("role", ALL_ROLES)
def test_creator_may_create_denies_unknown_rule(role):
    assert creator_may_create(creators=None, role=role) is False


@pytest.mark.parametrize(("rule", "role"), list(CREATE_TABLE))
def test_can_create_invite_links_table(rule, role):
    utub = _utub({"members": {"invite_link_creators": rule.value}})
    assert can_create_invite_links(utub=utub, role=role) is CREATE_TABLE[(rule, role)]


@pytest.mark.parametrize("role", ALL_ROLES)
def test_can_create_invite_links_defaults_without_stored_rule(role):
    expected = role in (Member_Role.CREATOR, Member_Role.CO_CREATOR)
    assert can_create_invite_links(utub=_utub(None), role=role) is expected


@pytest.mark.parametrize("raw", UNKNOWN_RAW)
@pytest.mark.parametrize("role", ALL_ROLES)
def test_can_create_invite_links_denies_every_role_on_unknown_raw(raw, role):
    assert can_create_invite_links(utub=_utub(raw), role=role) is False


@pytest.mark.parametrize(
    ("role", "setting", "expected"),
    [
        (Member_Role.CREATOR, None, True),
        (Member_Role.CREATOR, False, True),
        (Member_Role.CREATOR, True, True),
        (Member_Role.CO_CREATOR, None, False),
        (Member_Role.CO_CREATOR, False, False),
        (Member_Role.CO_CREATOR, True, True),
        (Member_Role.MEMBER, True, False),
        (Member_Role.MEMBER, None, False),
        (None, True, False),
    ],
)
def test_can_enable_invite_preview(role, setting, expected):
    raw = (
        None
        if setting is None
        else {"members": {"co_owners_can_enable_preview": setting}}
    )
    assert can_enable_invite_preview(utub=_utub(raw), role=role) is expected


@pytest.mark.parametrize(
    "raw",
    [
        {"members": {"co_owners_can_enable_preview": "yes"}},
        {"members": {"co_owners_can_enable_preview": 1}},
        {"members": {"co_owners_can_enable_preview": None}},
        {"members": None},
        {"members": "x"},
    ],
)
def test_co_owner_cannot_enable_preview_on_invalid_stored_value(raw):
    utub = _utub(raw)
    assert can_enable_invite_preview(utub=utub, role=Member_Role.CO_CREATOR) is False


def test_create_and_preview_rules_are_independent():
    utub = _utub(
        {
            "members": {
                "invite_link_creators": "no_one",
                "co_owners_can_enable_preview": True,
            }
        }
    )
    assert can_create_invite_links(utub=utub, role=Member_Role.CO_CREATOR) is False
    assert can_enable_invite_preview(utub=utub, role=Member_Role.CO_CREATOR) is True
