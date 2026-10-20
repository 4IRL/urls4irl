from collections.abc import Set as AbstractSet

import pytest

from backend.urls.permissions import can_act_as_url_adder

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "adder_id, user_id, is_manager, member_ids, expected",
    [
        pytest.param(1, 1, False, {1, 2}, True, id="adder_on_own_url"),
        pytest.param(1, 2, True, {1, 2}, True, id="manager_on_anyones_url"),
        pytest.param(1, 2, False, {1, 2}, False, id="plain_member_current_adder"),
        pytest.param(1, 2, False, {2, 3}, True, id="plain_member_orphaned_url"),
        pytest.param(1, 4, False, {2, 3}, False, id="viewer_not_member_orphan"),
        pytest.param(1, 4, True, {2, 3}, False, id="manager_flag_but_not_member"),
        pytest.param(1, 1, False, set(), False, id="empty_member_ids"),
        pytest.param(1, 2, False, frozenset(), False, id="empty_frozenset"),
    ],
)
def test_can_act_as_url_adder(
    adder_id: int,
    user_id: int,
    is_manager: bool,
    member_ids: AbstractSet[int],
    expected: bool,
) -> None:
    """
    GIVEN an adder, a viewer, a manager flag and the UTub's current member ids
    WHEN can_act_as_url_adder is evaluated
    THEN it allows the adder, managers and (for orphaned URLs) any member, and fails
        closed for non-members and empty member sets
    """
    assert (
        can_act_as_url_adder(
            adder_id=adder_id,
            user_id=user_id,
            is_manager=is_manager,
            member_ids=member_ids,
        )
        is expected
    )
