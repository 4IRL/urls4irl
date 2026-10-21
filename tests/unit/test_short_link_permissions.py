from collections.abc import Set as AbstractSet

import pytest

from backend.urls.permissions import can_revoke_short_link

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "adder_id, minter_id, user_id, is_manager, member_ids, expected",
    [
        pytest.param(1, 3, 1, False, {1, 2, 3}, True, id="adder"),
        pytest.param(1, 3, 2, True, {1, 2, 3}, True, id="manager"),
        pytest.param(1, 3, 3, False, {1, 2, 3}, True, id="minter_plain_member"),
        pytest.param(1, 3, 2, False, {1, 2, 3}, False, id="neither_plain_member"),
        pytest.param(1, 3, 2, False, {2, 3}, True, id="orphaned_url_any_member"),
        pytest.param(1, None, 2, False, {1, 2}, False, id="minter_none_plain_member"),
        pytest.param(1, None, 2, False, {2}, True, id="minter_none_orphaned_url"),
        pytest.param(1, None, 1, False, {1, 2}, True, id="minter_none_adder"),
        pytest.param(1, None, 2, True, {1, 2}, True, id="minter_none_manager"),
        pytest.param(1, 3, 3, False, {1, 2}, False, id="minter_no_longer_member"),
        pytest.param(1, 3, 4, False, {1, 2, 3}, False, id="not_a_member"),
        pytest.param(1, 4, 4, True, {1, 2, 3}, False, id="manager_flag_not_member"),
        pytest.param(1, 3, 3, False, set(), False, id="empty_member_ids"),
        pytest.param(1, 3, 3, False, frozenset(), False, id="empty_frozenset"),
    ],
)
def test_can_revoke_short_link(
    adder_id: int,
    minter_id: int | None,
    user_id: int,
    is_manager: bool,
    member_ids: AbstractSet[int],
    expected: bool,
) -> None:
    """
    GIVEN a URL adder, a link minter (possibly None), a viewer, a manager flag and the
        UTub's current member ids
    WHEN can_revoke_short_link is evaluated
    THEN the adder, managers, any member of an orphaned URL, and the minter (while
        still a member) may revoke; everyone else fails closed
    """
    assert (
        can_revoke_short_link(
            adder_id=adder_id,
            minter_id=minter_id,
            user_id=user_id,
            is_manager=is_manager,
            member_ids=member_ids,
        )
        is expected
    )
