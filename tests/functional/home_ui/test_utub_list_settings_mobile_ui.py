from __future__ import annotations

import re

import pytest
from flask import Flask
from playwright.sync_api import Page, expect

from backend.utils.strings.utub_strs import UTUB_LIST_SETTINGS_ROW_COUNTS_SHOWN_NOTICE
from tests.functional.db_utils import (
    count_live_urls_and_members,
    create_utubs_owned_by,
    get_utub_id_by_name,
    set_utub_list_preferences,
)
from tests.functional.home_ui.test_panel_settings_mobile_ui import (
    _MIN_TOUCH_TARGET_PX,
    _SHEET_OPEN_CLASS_RE,
    _close_sheet_via_close_button,
    _expect_sheet_closed,
    _go_to_deck_via_navbar,
)
from tests.functional.home_ui.test_utub_list_settings_ui import (
    DECK_NAMES,
    ORDER_BY_SORT,
    SORT_UI,
    USER_ID_FOR_TEST,
    counts_switch,
    expect_deck_order,
    expect_row_counts,
    mock_names,
    seed_sortable_mock_utubs,
    sort_notice,
    sort_select,
    totals_switch,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_login_utils import (
    login_user_and_select_utub_by_utubid_mobile,
)
from tests.functional.playwright_utils import (
    login_user_to_home_page,
    wait_for_css_transitions_to_finish,
)

pytestmark = [pytest.mark.home_ui, pytest.mark.mobile_ui]

SHEET = HPL.PANEL_SETTINGS_SHEET
_PHONE_WIDTHS = (320, 390)
_PHONE_HEIGHT_PX = 800
_LONG_UTUB_NAME = (
    "W" * 30
)  # the widest glyph, so the 30-character cap overflows a phone row

_THREE_DIGIT_URL_COUNT = "999"
_THREE_DIGIT_MEMBER_COUNT = "100"

_ROW_FIT_JS = """(utubName) => {
    const row = Array.from(
        document.querySelectorAll('#listUTubs > .UTubSelector')
    ).find((candidate) => candidate.querySelector('.UTubName').textContent === utubName);
    const rowRect = row.getBoundingClientRect();
    const name = row.querySelector('.UTubName');
    const counts = row.querySelector('.UTubRowCounts');
    const countRects = Array.from(counts.querySelectorAll('.UTubRowCount')).map(
        (count) => count.getBoundingClientRect()
    );
    const role = row.querySelector('.memberRole').getBoundingClientRect();
    const countsRect = counts.getBoundingClientRect();
    return {
        rowHeight: rowRect.height,
        rowRight: rowRect.right,
        nameRight: name.getBoundingClientRect().right,
        nameTruncated: name.scrollWidth > name.clientWidth,
        countsLeft: countsRect.left,
        countsRight: countsRect.right,
        countsClipped: counts.scrollWidth > counts.clientWidth,
        countTops: countRects.map((rect) => Math.round(rect.top)),
        countHeights: countRects.map((rect) => Math.round(rect.height)),
        roleLeft: role.left,
        roleRight: role.right,
    };
}"""

_SET_COUNT_NUMBERS_JS = """([utubName, urlCount, memberCount]) => {
    const row = Array.from(
        document.querySelectorAll('#listUTubs > .UTubSelector')
    ).find((candidate) => candidate.querySelector('.UTubName').textContent === utubName);
    const numbers = row.querySelectorAll('.UTubRowCountNum');
    numbers[0].textContent = urlCount;
    numbers[1].textContent = memberCount;
}"""


def _open_utubs_sheet(*, page: Page) -> None:
    gear = page.locator(HPL.BUTTON_UTUB_SETTINGS_GEAR)
    expect(gear).to_be_visible()
    gear.tap()
    expect(page.locator(SHEET)).to_have_class(_SHEET_OPEN_CLASS_RE)
    expect(sort_select(page=page, surface=SHEET)).to_be_visible()
    # The sheet slides in: sizes read mid-transition are fractional.
    wait_for_css_transitions_to_finish(locator=page.locator(SHEET))


def _expect_touch_target(*, locator) -> None:
    box = locator.bounding_box()
    assert box is not None
    assert box["height"] >= _MIN_TOUCH_TARGET_PX, box


def test_sheet_holds_the_same_controls_as_touch_targets_and_deck_reorders_on_close(
    page_mobile_portrait: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a phone viewport on the UTubs list
    WHEN the user opens the UTubs gear and picks name A-Z
    THEN the bottom sheet holds the sort select and both switches (all 44px tall
        targets), and the deck is in name order once the sheet closes
    """
    app = provide_app
    page = page_mobile_portrait
    seed_sortable_mock_utubs(app)
    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)
    expect_deck_order(
        page=page, names=mock_names(order=ORDER_BY_SORT["recent_activity"])
    )

    _open_utubs_sheet(page=page)
    select = sort_select(page=page, surface=SHEET)
    counts = counts_switch(page=page, surface=SHEET)
    totals = totals_switch(page=page, surface=SHEET)
    for control in (select, counts, totals):
        _expect_touch_target(locator=control)
    expect(counts).to_have_attribute("aria-checked", "false")
    expect(totals).to_have_attribute("aria-checked", "true")

    select.select_option(label=SORT_UI["name_az"][0])
    expect(page.locator(HPL.PANEL_SETTINGS_ANNOUNCEMENT)).to_contain_text(
        sort_notice(sort="name_az")
    )
    _close_sheet_via_close_button(page)
    _expect_sheet_closed(page)

    expect_deck_order(page=page, names=mock_names(order=ORDER_BY_SORT["name_az"]))
    page.reload()
    expect_deck_order(page=page, names=mock_names(order=ORDER_BY_SORT["name_az"]))


def test_gear_is_reachable_after_selecting_a_utub_by_reopening_the_deck(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a phone user who selected a UTub (which hides the UTubs panel)
    WHEN they reopen the UTubs deck from the navbar and turn row counts on in the sheet
    THEN the selected UTub's row shows its real counts
    """
    app = provide_app
    page = page_mobile_portrait
    utub_id = get_utub_id_by_name(app, "MockUTub_1")
    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub_id
    )
    expect(page.locator(HPL.LEFT_PANEL)).to_be_hidden()
    _go_to_deck_via_navbar(page, HPL.NAVBAR_UTUB_DECK)

    _open_utubs_sheet(page=page)
    counts_switch(page=page, surface=SHEET).tap()
    expect(page.locator(HPL.PANEL_SETTINGS_ANNOUNCEMENT)).to_contain_text(
        UTUB_LIST_SETTINGS_ROW_COUNTS_SHOWN_NOTICE
    )
    _close_sheet_via_close_button(page)
    _expect_sheet_closed(page)

    urls, members = count_live_urls_and_members(app, utub_id)
    expect_row_counts(page=page, utub_id=utub_id, urls=urls, members=members)
    expect(page.locator(HPL.UTUB_DECK)).to_have_class(re.compile(r"showUTubRowCounts"))


@pytest.mark.parametrize("viewport_width", _PHONE_WIDTHS)
def test_three_digit_counts_do_not_wrap_and_the_name_truncates_first(
    page_mobile_portrait: Page,
    create_test_utubmembers,
    provide_app: Flask,
    viewport_width: int,
):
    """
    GIVEN counts on and a UTub with a long name, at a 320px or 390px phone width
    WHEN the row's numbers are three digits (written into the DOM: a real 100-member
        UTub would need 100 users)
    THEN the row keeps its height, the counts stay on one line unclipped beside the
        role icon, and it is the name that truncates
    """
    app = provide_app
    page = page_mobile_portrait
    page.set_viewport_size({"width": viewport_width, "height": _PHONE_HEIGHT_PX})
    create_utubs_owned_by(app, USER_ID_FOR_TEST, [_LONG_UTUB_NAME])
    set_utub_list_preferences(app, USER_ID_FOR_TEST, show_row_counts=True)
    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)
    expect(page.locator(DECK_NAMES).filter(has_text=_LONG_UTUB_NAME)).to_be_visible()
    before = page.evaluate(_ROW_FIT_JS, _LONG_UTUB_NAME)
    assert before["nameTruncated"], "Test premise violated: the name must overflow"

    page.evaluate(
        _SET_COUNT_NUMBERS_JS,
        [_LONG_UTUB_NAME, _THREE_DIGIT_URL_COUNT, _THREE_DIGIT_MEMBER_COUNT],
    )
    after = page.evaluate(_ROW_FIT_JS, _LONG_UTUB_NAME)

    assert after["rowHeight"] == before["rowHeight"], (before, after)
    assert len(set(after["countTops"])) == 1, after
    assert len(set(after["countHeights"])) == 1, after
    assert not after["countsClipped"], after
    assert after["nameTruncated"], after
    assert after["nameRight"] <= after["countsLeft"] + 1, after
    assert after["countsRight"] <= after["roleLeft"] + 1, after
    assert after["roleRight"] <= after["rowRight"] + 1, after
