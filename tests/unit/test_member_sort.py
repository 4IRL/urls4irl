import json
import os
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from backend.members.services.member_sort import sort_members
from backend.models.user_preferences import MemberSort
from backend.models.utub_members import Member_Role, Utub_Members

pytestmark = pytest.mark.unit

PARITY_FIXTURE_PATH = (
    Path(__file__).resolve().parents[1] / "fixtures" / "member_sort_parity.json"
)
REGEN_ENV_FLAG = "U4I_REGEN_MEMBER_SORT_PARITY"
REGEN_SENTINEL_PATH = PARITY_FIXTURE_PATH.with_name("REGEN_MEMBER_SORT_PARITY")


def _membership(row: dict[str, Any]) -> Utub_Members:
    """A transient membership stand-in carrying only what the sort reads."""
    joined_at = (
        None if row["joinedAt"] is None else datetime.fromisoformat(row["joinedAt"])
    )
    return SimpleNamespace(  # type: ignore[return-value]
        user_id=row["id"],
        member_role=Member_Role(row["role"]),
        joined_at=joined_at,
        to_user=SimpleNamespace(username=row["username"]),
    )


def _sorted_ids(case: dict[str, Any], member_sort: MemberSort) -> list[int]:
    memberships = [_membership(row) for row in case["members"]]
    return [member.user_id for member in sort_members(memberships, member_sort)]


def test_member_sort_matches_shared_parity_fixture():
    """
    GIVEN the checked-in parity fixture (the client replays it in a later step)
    WHEN every case is sorted under each of the three member sorts
    THEN the order equals the fixture's ``expected`` (the Python sort is the
        source of truth; ``U4I_REGEN_MEMBER_SORT_PARITY=1`` or the sentinel file
        rewrites ``expected``)
    """
    fixture = json.loads(PARITY_FIXTURE_PATH.read_text())
    regenerate = os.environ.get(REGEN_ENV_FLAG) == "1" or REGEN_SENTINEL_PATH.exists()
    produced: dict[str, dict[str, list[int]]] = {
        member_sort.value: {
            case["case"]: _sorted_ids(case, member_sort) for case in fixture["inputs"]
        }
        for member_sort in MemberSort
    }
    if regenerate:
        fixture["expected"] = produced
        PARITY_FIXTURE_PATH.write_text(json.dumps(fixture, indent=2) + "\n")
        pytest.skip("parity fixture regenerated; unset the flag/sentinel and rerun")
    assert produced == fixture["expected"]


def test_sub_millisecond_date_ties_break_by_id_literal():
    """
    GIVEN dates that differ only below 1 ms
    WHEN sorted by recently joined
    THEN they tie after truncation and fall to id order (a literal, so a
        regenerated fixture cannot bless a wrong tie rule)
    """
    fixture = json.loads(PARITY_FIXTURE_PATH.read_text())
    case = next(
        entry
        for entry in fixture["inputs"]
        if entry["case"] == "sub_millisecond_date_ties"
    )
    assert _sorted_ids(case, MemberSort.RECENTLY_JOINED) == [1, 4, 2, 3, 5]


@pytest.mark.parametrize("member_sort", list(MemberSort))
def test_owner_is_first_under_every_sort(member_sort: MemberSort):
    """
    GIVEN every fixture case
    WHEN sorted under any sort
    THEN the creator row is first
    """
    fixture = json.loads(PARITY_FIXTURE_PATH.read_text())
    for case in fixture["inputs"]:
        owner_id = next(
            row["id"] for row in case["members"] if row["role"] == "creator"
        )
        assert _sorted_ids(case, member_sort)[0] == owner_id, case["case"]


def test_recently_joined_puts_dateless_after_dated_by_name():
    """
    GIVEN dated and dateless members
    WHEN sorted by recently joined
    THEN dated members come newest first, then dateless members by name
    """
    fixture = json.loads(PARITY_FIXTURE_PATH.read_text())
    case = next(entry for entry in fixture["inputs"] if entry["case"] == "mixed_roles")
    assert _sorted_ids(case, MemberSort.RECENTLY_JOINED) == [1, 3, 2, 4, 5, 6]


def test_role_then_name_groups_cocreators_before_members():
    """
    GIVEN co-owners and members
    WHEN sorted by role then name
    THEN co-owners precede members, each group by case-folded name
    """
    fixture = json.loads(PARITY_FIXTURE_PATH.read_text())
    case = next(entry for entry in fixture["inputs"] if entry["case"] == "mixed_roles")
    assert _sorted_ids(case, MemberSort.ROLE_THEN_NAME) == [1, 5, 4, 2, 3, 6]


def test_casefold_difference_does_not_change_name_grouping():
    """
    GIVEN names differing only by case
    WHEN sorted by name
    THEN they are grouped together and ties break by id
    """
    fixture = json.loads(PARITY_FIXTURE_PATH.read_text())
    case = next(
        entry for entry in fixture["inputs"] if entry["case"] == "casefold_ties"
    )
    assert _sorted_ids(case, MemberSort.NAME_AZ) == [1, 3, 5, 2, 4]


def test_identical_names_tie_by_id():
    """
    GIVEN three members with an identical name
    WHEN sorted by name
    THEN they appear in id order
    """
    fixture = json.loads(PARITY_FIXTURE_PATH.read_text())
    case = next(
        entry
        for entry in fixture["inputs"]
        if entry["case"] == "identical_names_tie_by_id"
    )
    assert _sorted_ids(case, MemberSort.NAME_AZ) == [1, 4, 7, 9]


def test_sort_members_rejects_unknown_sort():
    """
    GIVEN an unknown sort value
    WHEN sorting members
    THEN a ValueError is raised
    """
    with pytest.raises(ValueError):
        sort_members([], "bogus")  # type: ignore[arg-type]
