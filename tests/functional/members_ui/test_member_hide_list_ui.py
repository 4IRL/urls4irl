from __future__ import annotations

import re
from typing import Callable

import pytest
from flask import Flask
from playwright.sync_api import Locator, Page, Request, Response, expect

from backend.utils.strings.url_strs import HIDDEN_MEMBER_LABEL, URL_ADDED_BY
from backend.utils.strings.user_strs import (
    MEMBER_ADD_EXACT_USERNAME_HINT,
    MEMBER_CANNOT_BE_ADDED,
)
from tests.functional.db_utils import set_utub_list_preferences
from tests.functional.home_ui.test_panel_settings_mobile_ui import (
    _go_to_deck_via_navbar,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.members_ui.playwright_utils import (
    click_add_member_submit,
    close_add_member_combobox,
    get_staged_chip,
    is_settings_patch,
    member_row,
    open_add_member_combobox,
    open_members_gear,
    stage_outsider_username,
)
from tests.functional.playwright_assert_utils import assert_no_page_errors
from tests.functional.playwright_login_utils import (
    login_user_and_select_utub_by_utubid,
    login_user_and_select_utub_by_utubid_mobile,
)
from tests.functional.playwright_utils import (
    collect_page_errors,
    get_url_row_by_id,
    refocus_window,
    wait_until_visible_css_selector,
)
from tests.utils_for_test import (
    HideListSeed,
    seed_hide_list_utub,
    set_members_settings,
)

pytestmark = pytest.mark.members_ui

# Longer than UTUB_REFRESH_MIN_INTERVAL_MS (30_000) so the next refocus is due.
REFRESH_INTERVAL_PASSED_MS = 31_000
UNKNOWN_USERNAME = "hide_nobody_here"

_MEMBER_ADD_POST_URL_RE = re.compile(r"/utubs/\d+/members$")
_UTUB_SETTINGS_URL_RE = re.compile(r"/utubs/\d+/settings$")
_ADDED_BY_A_MEMBER_RE = re.compile(rf"{URL_ADDED_BY} {HIDDEN_MEMBER_LABEL}\b")


@pytest.fixture
def seed_hidden_utub(runner, provide_app: Flask) -> Callable[..., HideListSeed]:
    """Factory seeding the shared 5-user hide-list UTub in the UI app's database
    (``runner`` clears the database after the test).

    ``hide_member_list`` is the stored value; ``members_can_add`` additionally
    turns on plain-member adding.
    """

    def _seed(
        *, hide_member_list: bool | None, members_can_add: bool = False
    ) -> HideListSeed:
        seed = seed_hide_list_utub(provide_app, hide_member_list)
        if members_can_add:
            stored = {"members_can_add": True}
            if hide_member_list is not None:
                stored["hide_member_list"] = hide_member_list
            set_members_settings(provide_app, seed.utub_id, stored)
        return seed

    return _seed


def _visible_member_ids(*, page: Page, expected_count: int) -> set[int]:
    """The member ids of the deck rows, read once the row count has settled."""
    rows = page.locator(f"{HPL.MEMBER_DECK} {HPL.BADGES_MEMBERS}")
    expect(rows).to_have_count(expected_count)
    return {
        int(member_id)
        for member_id in rows.evaluate_all(
            "elements => elements.map(element => element.getAttribute('memberid'))"
        )
    }


def _utub_row_numbers(*, page: Page, utub_id: int) -> Locator:
    return page.locator(
        f"{HPL.SELECTORS_UTUB}[utubid='{utub_id}'] {HPL.UTUB_ROW_COUNT_NUMBERS}"
    )


def _expanded_adder_badge(*, page: Page, utub_url_id: int) -> Locator:
    """Select the URL row (expanding it) and return its stacked attribution badge."""
    row = get_url_row_by_id(page=page, utub_url_id=utub_url_id)
    row.click()
    expect(row).to_have_attribute("urlselected", "true")
    return row.locator(HPL.URL_DATE_ADDED_BADGE_STACKED)


def _is_settings_patch_request(request: Request) -> bool:
    return (
        request.method == "PATCH"
        and _UTUB_SETTINGS_URL_RE.search(request.url) is not None
    )


def _is_utub_refresh(*, utub_id: int) -> Callable[[Response], bool]:
    refresh_suffix = f"/utubs/{utub_id}/refresh"
    return lambda response: response.url.endswith(refresh_suffix)


def _is_member_add_post(response: Response) -> bool:
    return (
        response.request.method == "POST"
        and _MEMBER_ADD_POST_URL_RE.search(response.url) is not None
    )


def test_owner_toggles_hide_switch_and_it_persists_across_reload(
    page: Page, seed_hidden_utub, provide_app: Flask
):
    """
    GIVEN a UTub owner with the member list visible
    WHEN they turn on "Hide member list from members" and reload
    THEN the PATCH succeeds and the switch is still on afterwards
    """
    app = provide_app
    page_errors = collect_page_errors(page=page)
    seed = seed_hidden_utub(hide_member_list=None)
    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=seed.owner_id, utub_id=seed.utub_id
    )

    open_members_gear(page=page)
    switch = page.locator(HPL.MEMBERS_PERMISSIONS_HIDE_LIST_SWITCH)
    expect(switch).to_have_attribute("aria-checked", "false")
    with page.expect_response(is_settings_patch) as response_info:
        switch.click()
    assert response_info.value.status == 200
    expect(switch).to_have_attribute("aria-checked", "true")

    page.reload()
    wait_until_visible_css_selector(
        page=page, css_selector=HPL.BUTTON_MEMBER_SETTINGS_GEAR
    )
    open_members_gear(page=page)
    expect(page.locator(HPL.MEMBERS_PERMISSIONS_HIDE_LIST_SWITCH)).to_have_attribute(
        "aria-checked", "true"
    )
    assert_no_page_errors(page_errors=page_errors)


def test_co_owner_sees_hide_switch_disabled(
    page: Page, seed_hidden_utub, provide_app: Flask
):
    """
    GIVEN a co-owner of a UTub whose owner turned the setting on
    WHEN they open the Members gear
    THEN the hide switch is on, aria-disabled and a click changes nothing
    """
    app = provide_app
    page_errors = collect_page_errors(page=page)
    seed = seed_hidden_utub(hide_member_list=True)
    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=seed.co_owner_id, utub_id=seed.utub_id
    )

    open_members_gear(page=page)
    switch = page.locator(HPL.MEMBERS_PERMISSIONS_HIDE_LIST_SWITCH)
    expect(switch).to_be_visible()
    expect(switch).to_have_attribute("aria-disabled", "true")
    expect(switch).to_have_attribute("aria-checked", "true")
    patch_requests: list[Request] = []
    page.on(
        "request",
        lambda request: (
            patch_requests.append(request)
            if _is_settings_patch_request(request)
            else None
        ),
    )
    # force: Playwright treats aria-disabled as "not enabled" and would wait.
    switch.click(force=True)

    # A reload round-trip proves the stored value did not change and, since the
    # click has been handled by then, that no PATCH was sent.
    page.reload()
    wait_until_visible_css_selector(
        page=page, css_selector=HPL.BUTTON_MEMBER_SETTINGS_GEAR
    )
    open_members_gear(page=page)
    expect(page.locator(HPL.MEMBERS_PERMISSIONS_HIDE_LIST_SWITCH)).to_have_attribute(
        "aria-checked", "true"
    )
    assert patch_requests == []
    assert_no_page_errors(page_errors=page_errors)


def test_plain_member_in_hidden_utub_sees_only_owner_co_owner_and_self(
    page: Page, seed_hidden_utub, provide_app: Flask
):
    """
    GIVEN a plain member of a UTub with the member list hidden and row counts on
    WHEN they open it
    THEN the deck lists exactly the owner, the co-owner and themself with no "(N)",
        a hidden member's URL reads "Added by a member" and the UTub row counts
        show URLs only
    """
    app = provide_app
    page_errors = collect_page_errors(page=page)
    seed = seed_hidden_utub(hide_member_list=True)
    set_utub_list_preferences(app, seed.member_a_id, show_row_counts=True)
    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=seed.member_a_id, utub_id=seed.utub_id
    )

    assert _visible_member_ids(page=page, expected_count=3) == {
        seed.owner_id,
        seed.co_owner_id,
        seed.member_a_id,
    }
    expect(page.locator(HPL.MEMBER_DECK_COUNT)).to_have_text("")
    expect(_utub_row_numbers(page=page, utub_id=seed.utub_id)).to_have_text(
        [str(len(seed.utub_url_ids))]
    )
    badge = _expanded_adder_badge(
        page=page, utub_url_id=seed.utub_url_ids[seed.member_b_id]
    )
    expect(badge).to_contain_text(_ADDED_BY_A_MEMBER_RE)
    assert_no_page_errors(page_errors=page_errors)


@pytest.mark.mobile_ui
def test_plain_member_in_hidden_utub_sees_only_visible_people_on_a_phone(
    page_mobile_portrait: Page, seed_hidden_utub, provide_app: Flask
):
    """
    GIVEN a phone-width plain member of a UTub with the member list hidden
    WHEN they open it
    THEN the Members deck lists exactly the owner, the co-owner and themself with
        no "(N)", a hidden member's URL reads "Added by a member" and the UTub row
        counts show URLs only
    """
    app = provide_app
    page = page_mobile_portrait
    page_errors = collect_page_errors(page=page)
    seed = seed_hidden_utub(hide_member_list=True)
    set_utub_list_preferences(app, seed.member_a_id, show_row_counts=True)
    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=seed.member_a_id, utub_id=seed.utub_id
    )

    expect(_utub_row_numbers(page=page, utub_id=seed.utub_id)).to_have_text(
        [str(len(seed.utub_url_ids))]
    )
    badge = _expanded_adder_badge(
        page=page, utub_url_id=seed.utub_url_ids[seed.member_b_id]
    )
    expect(badge).to_contain_text(_ADDED_BY_A_MEMBER_RE)

    _go_to_deck_via_navbar(page, HPL.NAVBAR_MEMBER_DECK)
    assert _visible_member_ids(page=page, expected_count=3) == {
        seed.owner_id,
        seed.co_owner_id,
        seed.member_a_id,
    }
    expect(page.locator(HPL.MEMBER_DECK_COUNT)).to_have_text("")
    assert_no_page_errors(page_errors=page_errors)


def test_plain_member_adding_gets_no_suggestions_and_one_unified_error(
    page: Page, seed_hidden_utub, provide_app: Flask
):
    """
    GIVEN a plain member allowed to add members in a UTub with the list hidden
    WHEN they open the add box, then submit a hidden member's name and an unknown name
    THEN no suggestion rows show, the neutral hint shows and both failed chips carry
        the identical tooltip, MEMBER_CANNOT_BE_ADDED
    """
    app = provide_app
    page_errors = collect_page_errors(page=page)
    seed = seed_hidden_utub(hide_member_list=True, members_can_add=True)
    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=seed.member_a_id, utub_id=seed.utub_id
    )
    wait_until_visible_css_selector(page=page, css_selector=HPL.MEMBER_ROW_ROLE_ICON)

    open_add_member_combobox(page=page)
    expect(page.locator(HPL.MEMBER_COMBOBOX_LISTBOX_HINT)).to_have_text(
        MEMBER_ADD_EXACT_USERNAME_HINT
    )
    expect(page.locator(HPL.MEMBER_COMBOBOX_OPTION)).to_have_count(0)

    existing_hidden_name = seed.usernames[seed.member_b_id]
    stage_outsider_username(page=page, username=existing_hidden_name)
    stage_outsider_username(page=page, username=UNKNOWN_USERNAME)
    click_add_member_submit(page=page)

    existing_chip = get_staged_chip(page=page, username=existing_hidden_name)
    unknown_chip = get_staged_chip(page=page, username=UNKNOWN_USERNAME)
    expect(existing_chip).to_have_attribute("title", MEMBER_CANNOT_BE_ADDED)
    expect(unknown_chip).to_have_attribute("title", MEMBER_CANNOT_BE_ADDED)
    assert existing_chip.get_attribute("title") == unknown_chip.get_attribute("title")
    assert_no_page_errors(page_errors=page_errors)


def test_successful_add_does_not_appear_in_plain_members_list(
    page: Page, seed_hidden_utub, provide_app: Flask
):
    """
    GIVEN a plain member allowed to add members in a UTub with the list hidden
    WHEN they successfully add an existing user who is not yet a member
    THEN the add returns 200 and the member's list still shows only the owner, the
        co-owner and themself
    """
    app = provide_app
    page_errors = collect_page_errors(page=page)
    seed = seed_hidden_utub(hide_member_list=True, members_can_add=True)
    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=seed.member_a_id, utub_id=seed.utub_id
    )
    wait_until_visible_css_selector(page=page, css_selector=HPL.MEMBER_ROW_ROLE_ICON)

    open_add_member_combobox(page=page)
    stage_outsider_username(page=page, username=seed.usernames[seed.former_member_id])
    with page.expect_response(_is_member_add_post) as response_info:
        click_add_member_submit(page=page)
    assert response_info.value.status == 200

    # The batch-settle pass (any append, then the summary) runs after the response
    # event; the summary text is its last write, so wait for it before asserting.
    expect(page.locator(HPL.MEMBER_COMBOBOX_MESSAGE)).not_to_be_empty()
    close_add_member_combobox(page=page)
    assert _visible_member_ids(page=page, expected_count=3) == {
        seed.owner_id,
        seed.co_owner_id,
        seed.member_a_id,
    }
    # Hidden-list viewers get no "(N)" subheader.
    expect(page.locator(HPL.MEMBER_DECK_COUNT)).not_to_contain_text("(")
    expect(page.locator(HPL.MEMBER_DECK_COUNT)).to_have_text("")
    assert_no_page_errors(page_errors=page_errors)


def test_live_flip_of_the_setting_hides_and_restores_the_list_for_a_loaded_member(
    page: Page, seed_hidden_utub, provide_app: Flask
):
    """
    GIVEN a plain member session loaded with the list visible, a hidden-to-be
        member's URL expanded and focus on that member's row
    WHEN the owner turns the setting on and the member's tab refreshes
    THEN the hidden rows, "(N)" and the member clause of the row count go, the open
        card reads "Added by a member" and focus stays inside the Members deck;
        and turning it back off restores the rows, count and names
    """
    app = provide_app
    page_errors = collect_page_errors(page=page)
    seed = seed_hidden_utub(hide_member_list=False)
    set_utub_list_preferences(app, seed.member_a_id, show_row_counts=True)
    page.clock.install()
    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=seed.member_a_id, utub_id=seed.utub_id
    )

    url_count = str(len(seed.utub_url_ids))
    member_count = len(seed.current_member_ids)
    assert _visible_member_ids(page=page, expected_count=member_count) == (
        seed.current_member_ids
    )
    expect(page.locator(HPL.MEMBER_DECK_COUNT)).to_have_text(f"({member_count})")
    expect(_utub_row_numbers(page=page, utub_id=seed.utub_id)).to_have_text(
        [url_count, str(member_count)]
    )
    hidden_name = seed.usernames[seed.member_b_id]
    badge = _expanded_adder_badge(
        page=page, utub_url_id=seed.utub_url_ids[seed.member_b_id]
    )
    expect(badge).to_contain_text(f"{URL_ADDED_BY} {hidden_name}")

    # Plain-member rows are not focusable, so give the row-to-be-hidden focus.
    hidden_row = member_row(page=page, member_id=seed.member_b_id)
    hidden_row.evaluate(
        "element => { element.setAttribute('tabindex', '-1'); element.focus(); }"
    )
    expect(hidden_row).to_be_focused()

    set_members_settings(app, seed.utub_id, {"hide_member_list": True})
    page.clock.fast_forward(REFRESH_INTERVAL_PASSED_MS)
    with page.expect_response(_is_utub_refresh(utub_id=seed.utub_id)):
        refocus_window(page=page)

    assert _visible_member_ids(page=page, expected_count=3) == {
        seed.owner_id,
        seed.co_owner_id,
        seed.member_a_id,
    }
    expect(page.locator(HPL.MEMBER_DECK_COUNT)).to_have_text("")
    expect(_utub_row_numbers(page=page, utub_id=seed.utub_id)).to_have_text([url_count])
    expect(badge).to_contain_text(_ADDED_BY_A_MEMBER_RE)
    expect(page.locator(f"{HPL.MEMBER_DECK} :focus")).to_have_count(1)

    set_members_settings(app, seed.utub_id, {"hide_member_list": False})
    page.clock.fast_forward(REFRESH_INTERVAL_PASSED_MS)
    with page.expect_response(_is_utub_refresh(utub_id=seed.utub_id)):
        refocus_window(page=page)

    assert _visible_member_ids(page=page, expected_count=member_count) == (
        seed.current_member_ids
    )
    expect(page.locator(HPL.MEMBER_DECK_COUNT)).to_have_text(f"({member_count})")
    expect(_utub_row_numbers(page=page, utub_id=seed.utub_id)).to_have_text(
        [url_count, str(member_count)]
    )
    expect(badge).to_contain_text(f"{URL_ADDED_BY} {hidden_name}")
    assert_no_page_errors(page_errors=page_errors)
