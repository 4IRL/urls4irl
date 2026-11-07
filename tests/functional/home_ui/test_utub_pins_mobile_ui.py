from __future__ import annotations

import pytest
from flask import Flask
from playwright.sync_api import Page, expect

from tests.functional.home_ui.test_panel_settings_mobile_ui import (
    _close_sheet_via_close_button,
    _expect_sheet_closed,
)
from tests.functional.home_ui.test_utub_list_settings_mobile_ui import (
    SHEET,
    _expect_touch_target,
    _open_utubs_sheet,
)
from tests.functional.home_ui.test_utub_list_settings_ui import (
    ORDER_BY_SORT,
    USER_ID_FOR_TEST,
    expect_deck_order,
    mock_names,
    seed_sortable_mock_utubs,
)
from tests.functional.home_ui.test_utub_pins_ui import (
    DECK_PIN_ICONS,
    counter_text,
    expect_divider,
    expect_pin_failure_surfaced,
    expect_pinned_rows,
    fail_all_pin_writes,
    mock_ids,
    picker_input,
    pin_from_picker,
    pin_mocks_in_db,
    pinned_notice,
    pins_body,
    remove_button,
    unpinned_notice,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_utils import login_user_to_home_page

pytestmark = [pytest.mark.home_ui, pytest.mark.mobile_ui]


def test_pin_and_unpin_in_the_bottom_sheet_reorder_the_deck(
    page_mobile_portrait: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a phone user with no pins
    WHEN they pin MockUTub_3 from the sheet's picker and then unpin it
    THEN the sheet does not autofocus the picker on open, the deck shows the icon
        and rule after the sheet closes, and the unpin restores the sorted order
    """
    app = provide_app
    page = page_mobile_portrait
    seed_sortable_mock_utubs(app)
    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)
    expect_deck_order(
        page=page, names=mock_names(order=ORDER_BY_SORT["recent_activity"])
    )

    _open_utubs_sheet(page=page)
    expect(picker_input(page=page, surface=SHEET)).to_be_visible()
    expect(picker_input(page=page, surface=SHEET)).not_to_be_focused()

    pin_from_picker(
        page=page,
        text="MockUTub_3",
        option_name="MockUTub_3",
        use_enter=False,
        tap=True,
        surface=SHEET,
    )
    expect(page.locator(HPL.PANEL_SETTINGS_ANNOUNCEMENT)).to_contain_text(
        pinned_notice(name="MockUTub_3", count=1)
    )
    body = pins_body(page=page, surface=SHEET)
    expect(body.locator(".utubPinsCounter")).to_have_text(counter_text(count=1))
    _close_sheet_via_close_button(page)
    _expect_sheet_closed(page)
    expect_deck_order(page=page, names=mock_names(order=[3, 5, 4, 2, 1]))
    expect_pinned_rows(page=page, names=["MockUTub_3"])
    expect_divider(page=page, visible=True)

    _open_utubs_sheet(page=page)
    three = mock_ids(app=app, numbers=[3])[0]
    remove_button(page=page, utub_id=three, surface=SHEET).tap()
    expect(page.locator(HPL.PANEL_SETTINGS_ANNOUNCEMENT)).to_contain_text(
        unpinned_notice(name="MockUTub_3", count=0)
    )
    _close_sheet_via_close_button(page)
    _expect_sheet_closed(page)
    expect_deck_order(
        page=page, names=mock_names(order=ORDER_BY_SORT["recent_activity"])
    )
    expect(page.locator(DECK_PIN_ICONS)).to_have_count(0)
    expect_divider(page=page, visible=False)


def test_pin_controls_in_the_sheet_are_touch_targets(
    page_mobile_portrait: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a phone user with one pin
    WHEN the sheet is open and a character is typed in the picker
    THEN the unpin X, the picker input and a picker option row are all 44px tall
        touch targets
    """
    app = provide_app
    page = page_mobile_portrait
    seed_sortable_mock_utubs(app)
    pin_mocks_in_db(app=app, numbers=[3])
    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)

    _open_utubs_sheet(page=page)
    three = mock_ids(app=app, numbers=[3])[0]
    _expect_touch_target(locator=remove_button(page=page, utub_id=three, surface=SHEET))
    input_locator = picker_input(page=page, surface=SHEET)
    _expect_touch_target(locator=input_locator)

    input_locator.fill("M")
    option = pins_body(page=page, surface=SHEET).locator(".utubPinsOption").first
    expect(option).to_be_visible()
    _expect_touch_target(locator=option)


def test_a_failed_pin_in_the_sheet_leaves_the_deck_unchanged(
    page_mobile_portrait: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN the pin endpoint answers 500
    WHEN a phone user pins MockUTub_3 from the sheet
    THEN the failure is announced with the reverted line and the deck is unchanged
        once the sheet closes
    """
    app = provide_app
    page = page_mobile_portrait
    seed_sortable_mock_utubs(app)
    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)
    _open_utubs_sheet(page=page)
    fail_all_pin_writes(page=page)

    pin_from_picker(
        page=page,
        text="MockUTub_3",
        option_name="MockUTub_3",
        use_enter=False,
        tap=True,
        surface=SHEET,
    )

    expect_pin_failure_surfaced(page=page, surface=SHEET)
    _close_sheet_via_close_button(page)
    _expect_sheet_closed(page)
    expect_deck_order(
        page=page, names=mock_names(order=ORDER_BY_SORT["recent_activity"])
    )
    expect(page.locator(DECK_PIN_ICONS)).to_have_count(0)
