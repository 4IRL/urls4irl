from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from flask import Flask
from playwright.sync_api import Page, Route, expect

from backend.cli.mock_constants import USERNAME_BASE
from backend.models.user_preferences import MemberSort
from backend.models.utub_members import Member_Role
from backend.utils.strings.user_strs import (
    MEMBER_ROLE_CHANGE_GRANT_POSITION,
    MEMBERS_LIST_SORT_JOINED_NOTE,
    MEMBERS_LIST_SORT_NOTICE_PREFIX,
    MEMBERS_LIST_SORT_OPTION_JOINED,
    MEMBERS_LIST_SORT_OPTION_NAME_AZ,
    MEMBERS_LIST_SORT_OPTION_ROLE,
)
from tests.functional.db_utils import (
    add_member_with_join_date,
    create_utubs_owned_by,
    get_member_sort_preference,
    get_utub_this_user_created,
    set_utub_list_preferences,
)
from tests.functional.home_ui.playwright_utils import (
    open_members_settings,
    sort_select,
)
from tests.functional.home_ui.test_utub_list_settings_ui import (
    _expect_failure_surfaced,
    close_settings_popover,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.members_ui.playwright_utils import (
    click_add_member_submit,
    close_add_member_combobox,
    open_add_member_combobox,
    open_member_row_role_action,
    stage_outsider_username,
    submit_confirm_modal,
)
from tests.functional.playwright_login_utils import (
    login_user_and_select_utub_by_utubid,
)
from tests.functional.playwright_utils import (
    select_utub_by_id,
    wait_until_hidden,
)

pytestmark = [pytest.mark.home_ui, pytest.mark.members_ui]

OWNER_ID = 1
OWNER_NAME = f"{USERNAME_BASE}{OWNER_ID}"
MEMBER_SORT_ROUTE = "**/users/preferences/members"

# value -> (option label, spoken label in the live-region notice)
SORT_UI: dict[MemberSort, tuple[str, str]] = {
    MemberSort.NAME_AZ: (MEMBERS_LIST_SORT_OPTION_NAME_AZ, "Name A to Z"),
    MemberSort.ROLE_THEN_NAME: (MEMBERS_LIST_SORT_OPTION_ROLE, "Role, then name"),
    MemberSort.RECENTLY_JOINED: (MEMBERS_LIST_SORT_OPTION_JOINED, "Recently joined"),
}

# (user number, role, days ago joined; None = dateless). Chosen so every sort
# yields a different order of the non-owner rows.
_SEEDED_MEMBERS: list[tuple[int, Member_Role, float | None]] = [
    (2, Member_Role.MEMBER, 3),
    (3, Member_Role.CO_CREATOR, 5),
    (4, Member_Role.MEMBER, None),
    (5, Member_Role.MEMBER, 1),
]
ORDER_BY_SORT: dict[MemberSort, list[int]] = {
    MemberSort.NAME_AZ: [2, 3, 4, 5],
    MemberSort.ROLE_THEN_NAME: [3, 2, 4, 5],
    MemberSort.RECENTLY_JOINED: [5, 2, 3, 4],
}


def username(number: int) -> str:
    """The mock username of user ``number``."""
    return f"{USERNAME_BASE}{number}"


def names(*, order: list[int]) -> list[str]:
    """Usernames for the given user numbers, in order."""
    return [username(number) for number in order]


def make_member_co_owner(*, page: Page, member_id: int) -> None:
    """Open the member's role action, confirm the modal and wait for it to close."""
    open_member_row_role_action(page=page, member_id=member_id)
    submit_confirm_modal(page=page)
    wait_until_hidden(page=page, css_selector=HPL.HOME_MODAL)


def seed_members(*, app: Flask, utub_id: int) -> None:
    """Add users 2-5 to the owner's UTub with the roles and join dates above."""
    now = datetime.now(timezone.utc)
    for number, role, days_ago in _SEEDED_MEMBERS:
        add_member_with_join_date(
            app,
            utub_id,
            number,
            member_role=role,
            joined_at=None if days_ago is None else now - timedelta(days=days_ago),
        )


def expect_deck_order(*, page: Page, order: list[int]) -> None:
    """Assert the non-owner rows are in ``order`` and the owner is in #UTubOwner."""
    expect(page.locator(HPL.MEMBERS_DECK_ROW_NAMES)).to_have_text(names(order=order))
    expect(page.locator(HPL.MEMBERS_DECK_OWNER_NAME)).to_have_text(OWNER_NAME)


def sort_notice(*, sort: MemberSort) -> str:
    """The live-region text announced after ``sort`` is saved."""
    return f"{MEMBERS_LIST_SORT_NOTICE_PREFIX}{SORT_UI[sort][1]}"


def pick_sort(*, page: Page, sort: MemberSort) -> None:
    """Pick ``sort`` and wait for the saved-notice, announced only after the
    debounced PATCH has been answered and applied."""
    sort_select(page=page).select_option(label=SORT_UI[sort][0])
    expect(page.locator(HPL.PANEL_SETTINGS_ANNOUNCEMENT)).to_contain_text(
        sort_notice(sort=sort)
    )


def fail_member_sort_saves(*, page: Page) -> None:
    """Answer every member-sort PATCH with a 400 until the page closes."""

    def fulfill_with_bad_request(route: Route) -> None:
        route.fulfill(
            status=400,
            content_type="application/json",
            body='{"status": "Failure", "message": "forced failure"}',
        )

    page.route(MEMBER_SORT_ROUTE, fulfill_with_bad_request)


def login_to_seeded_utub(*, app: Flask, page: Page, user_id: int = OWNER_ID) -> int:
    """Seed users 2-5 into the owner's UTub, log in as ``user_id``, return the UTub id."""
    utub_id = get_utub_this_user_created(app, OWNER_ID).id
    seed_members(app=app, utub_id=utub_id)
    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id, utub_id=utub_id
    )
    return utub_id


@pytest.mark.parametrize(
    "sort",
    [MemberSort.ROLE_THEN_NAME, MemberSort.RECENTLY_JOINED],
)
def test_each_sort_reorders_the_deck_and_persists_across_reload(
    page: Page, create_test_utubs, provide_app: Flask, sort: MemberSort
):
    """
    GIVEN a UTub whose members differ in name, role and join date
    WHEN the owner picks a sort in the Members gear
    THEN the deck reorders at once with the owner still in #UTubOwner, and the
        choice and order survive a reload
    """
    app = provide_app
    login_to_seeded_utub(app=app, page=page)
    expect_deck_order(page=page, order=ORDER_BY_SORT[MemberSort.NAME_AZ])

    open_members_settings(page=page)
    expect(sort_select(page=page)).to_have_value(MemberSort.NAME_AZ.value)
    pick_sort(page=page, sort=sort)
    expect_deck_order(page=page, order=ORDER_BY_SORT[sort])

    page.reload()
    expect_deck_order(page=page, order=ORDER_BY_SORT[sort])
    open_members_settings(page=page)
    expect(sort_select(page=page)).to_have_value(sort.value)


def test_choice_applies_in_a_second_utub(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a sort picked in one UTub
    WHEN the user selects a second UTub they own
    THEN that UTub's members are in the same sort order
    """
    app = provide_app
    second_utub_id = create_utubs_owned_by(app, OWNER_ID, ["Second members UTub"])[
        "Second members UTub"
    ]
    seed_members(app=app, utub_id=second_utub_id)
    login_to_seeded_utub(app=app, page=page)

    open_members_settings(page=page)
    pick_sort(page=page, sort=MemberSort.RECENTLY_JOINED)
    close_settings_popover(page=page)

    select_utub_by_id(page=page, utub_id=second_utub_id)
    expect_deck_order(page=page, order=ORDER_BY_SORT[MemberSort.RECENTLY_JOINED])


def test_dateless_member_sorts_last_and_gear_shows_the_note_for_that_sort(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a member who joined before join dates were recorded (user 4)
    WHEN the owner picks Recently joined
    THEN the dateless member is last, and the pre-date-members note shows for that
        sort only
    """
    app = provide_app
    login_to_seeded_utub(app=app, page=page)

    open_members_settings(page=page)
    expect(page.locator(HPL.MEMBERS_SETTINGS_SORT_NOTE)).to_have_count(0)

    pick_sort(page=page, sort=MemberSort.RECENTLY_JOINED)
    expect(page.locator(HPL.MEMBERS_DECK_ROW_NAMES).last).to_have_text(username(4))
    expect(page.locator(HPL.MEMBERS_SETTINGS_SORT_NOTE)).to_have_text(
        MEMBERS_LIST_SORT_JOINED_NOTE
    )

    pick_sort(page=page, sort=MemberSort.NAME_AZ)
    expect(page.locator(HPL.MEMBERS_SETTINGS_SORT_NOTE)).to_have_count(0)


def test_plain_member_can_change_the_sort_without_changing_anyone_elses(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a plain member (user 2) viewing the owner's UTub
    WHEN they pick Role then name
    THEN their deck reorders and only their stored sort changes
    """
    app = provide_app
    login_to_seeded_utub(app=app, page=page, user_id=2)

    open_members_settings(page=page)
    pick_sort(page=page, sort=MemberSort.ROLE_THEN_NAME)
    expect_deck_order(page=page, order=ORDER_BY_SORT[MemberSort.ROLE_THEN_NAME])

    assert get_member_sort_preference(app, 2) == MemberSort.ROLE_THEN_NAME
    assert get_member_sort_preference(app, OWNER_ID) == MemberSort.NAME_AZ


@pytest.mark.parametrize(
    "sort, expects_position_clause",
    [(MemberSort.ROLE_THEN_NAME, True), (MemberSort.NAME_AZ, False)],
    ids=["role_then_name", "name_az"],
)
def test_granting_co_owner_lands_in_the_right_place_and_announces_the_group(
    page: Page,
    create_test_utubs,
    provide_app: Flask,
    sort: MemberSort,
    expects_position_clause: bool,
):
    """
    GIVEN the owner's sort is Role then name or Name A-Z
    WHEN they make user 5 a co-owner
    THEN under Role then name the row moves up into the co-owner group and the
        live region names that group; under Name A-Z the row stays put with no
        group clause
    """
    app = provide_app
    set_utub_list_preferences(app, OWNER_ID, member_sort=sort)
    login_to_seeded_utub(app=app, page=page)
    expect_deck_order(page=page, order=ORDER_BY_SORT[sort])

    make_member_co_owner(page=page, member_id=5)

    expected_order = [3, 5, 2, 4] if expects_position_clause else [2, 3, 4, 5]
    expect_deck_order(page=page, order=expected_order)
    announcement = page.locator(HPL.MEMBER_ROW_ACTION_ANNOUNCEMENT)
    if expects_position_clause:
        expect(announcement).to_contain_text(MEMBER_ROLE_CHANGE_GRANT_POSITION)
    else:
        # Wait for the announcement first, or the negative check passes vacuously.
        expect(announcement).not_to_be_empty()
        expect(announcement).not_to_contain_text(MEMBER_ROLE_CHANGE_GRANT_POSITION)


_MEMBER_SCROLLER_JS = """() => {
    let scroller = document.querySelector('#listMembers').parentElement;
    while (scroller) {
        const overflowY = getComputedStyle(scroller).overflowY;
        if (overflowY === 'auto' || overflowY === 'scroll') break;
        scroller = scroller.parentElement;
    }
    return scroller;
}"""

_ROW_IN_SCROLLER_JS = """(memberID) => {
    const row = document.querySelector(`#listMembers > .member[memberid="${memberID}"]`);
    let scroller = row.parentElement;
    while (scroller) {
        const overflowY = getComputedStyle(scroller).overflowY;
        if (overflowY === 'auto' || overflowY === 'scroll') break;
        scroller = scroller.parentElement;
    }
    const bounds = scroller.getBoundingClientRect();
    const rect = row.getBoundingClientRect();
    return rect.top >= bounds.top - 1 && rect.bottom <= bounds.bottom + 1;
}"""

_SHORT_VIEWPORT: dict[str, int] = {"width": 1280, "height": 420}


def test_role_change_keeps_the_moved_row_visible_in_a_scrolled_deck(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN Role then name on a short viewport where the member list scrolls, scrolled
        to the bottom
    WHEN the owner makes the last member (user 5) a co-owner, moving it to the top
    THEN the moved row is scrolled back into view and the group is announced
    """
    app = provide_app
    set_utub_list_preferences(app, OWNER_ID, member_sort=MemberSort.ROLE_THEN_NAME)
    page.set_viewport_size(_SHORT_VIEWPORT)
    login_to_seeded_utub(app=app, page=page)
    expect_deck_order(page=page, order=ORDER_BY_SORT[MemberSort.ROLE_THEN_NAME])

    scroller = page.evaluate_handle(_MEMBER_SCROLLER_JS).as_element()
    assert scroller is not None, "Test premise violated: no scrolling ancestor"
    assert scroller.evaluate("(el) => el.scrollHeight > el.clientHeight"), (
        "Test premise violated: the member list must scroll"
    )
    scroller.evaluate("(el) => { el.scrollTop = el.scrollHeight; }")
    assert page.evaluate(_ROW_IN_SCROLLER_JS, 5)

    make_member_co_owner(page=page, member_id=5)

    expect_deck_order(page=page, order=[3, 5, 2, 4])
    expect(page.locator(HPL.MEMBER_ROW_ACTION_ANNOUNCEMENT)).to_contain_text(
        MEMBER_ROLE_CHANGE_GRANT_POSITION
    )
    page.wait_for_function(_ROW_IN_SCROLLER_JS, arg=5)


def test_adding_a_member_under_recently_joined_lands_first(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN the owner's sort is Recently joined
    WHEN they add user 4, who has never been a member
    THEN the new member is first in #listMembers
    """
    app = provide_app
    set_utub_list_preferences(app, OWNER_ID, member_sort=MemberSort.RECENTLY_JOINED)
    utub_id = get_utub_this_user_created(app, OWNER_ID).id
    now = datetime.now(timezone.utc)
    add_member_with_join_date(app, utub_id, 2, joined_at=now - timedelta(days=3))
    add_member_with_join_date(app, utub_id, 3, joined_at=None)
    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=OWNER_ID, utub_id=utub_id
    )
    expect_deck_order(page=page, order=[2, 3])

    open_add_member_combobox(page=page)
    stage_outsider_username(page=page, username=username(4))
    click_add_member_submit(page=page)
    expect(page.locator(HPL.MEMBER_COMBOBOX_STAGED_CHIP_FAILED)).to_have_count(0)
    close_add_member_combobox(page=page)

    expect_deck_order(page=page, order=[4, 2, 3])


def test_a_failed_save_shows_the_error_and_leaves_the_deck_unchanged(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN the member-sort endpoint answers 400
    WHEN the owner picks Recently joined
    THEN the failure is announced, the select returns to the saved sort, the deck
        order is unchanged, and a reload still shows the saved sort
    """
    app = provide_app
    login_to_seeded_utub(app=app, page=page)
    open_members_settings(page=page)
    fail_member_sort_saves(page=page)
    select = sort_select(page=page)

    with page.expect_response(MEMBER_SORT_ROUTE):
        select.select_option(label=SORT_UI[MemberSort.RECENTLY_JOINED][0])

    _expect_failure_surfaced(page=page)
    expect(select).to_have_value(MemberSort.NAME_AZ.value)
    expect_deck_order(page=page, order=ORDER_BY_SORT[MemberSort.NAME_AZ])

    page.reload()
    expect_deck_order(page=page, order=ORDER_BY_SORT[MemberSort.NAME_AZ])
    open_members_settings(page=page)
    expect(sort_select(page=page)).to_have_value(MemberSort.NAME_AZ.value)
