from __future__ import annotations

import pytest
from flask import Flask
from playwright.sync_api import Page, expect

from tests.functional.db_utils import get_utub_this_user_created
from tests.functional.home_ui.test_panel_settings_ui import (
    _assert_no_gear_visible,
    _reveal_gears,
    gear_container_metrics,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_login_utils import (
    login_user_and_select_utub_by_utubid_mobile,
)
from tests.functional.playwright_utils import (
    click_on_navbar,
    wait_for_class_to_be_removed,
    wait_then_click_element,
)
from tests.functional.tags_ui.playwright_utils import (
    swipe_tag_sheet_closed,
    swipe_tag_sheet_open,
    wait_until_tag_sheet_collapsed,
    wait_until_tag_sheet_open,
)
from tests.functional.urls_ui.playwright_utils import enter_multi_select_mode

pytestmark = [pytest.mark.home_ui, pytest.mark.mobile_ui]

USER_ID_FOR_TEST = 1

_MIN_TOUCH_TARGET_PX = 44
_PHONE_WIDTHS = (320, 390)
_PHONE_HEIGHT_PX = 800

# The open/close/focus/inert/Escape/stacking contracts of the sheet are pinned in
# Vitest (frontend/home/panel-settings/__tests__/sheet.test.ts). No section is
# registered in the browser yet, so a gear tap opens nothing real: these tests
# assert only what the DOM-only gear reveal shows. The real-browser sheet flows
# are added once a section is registered.


def _select_owned_utub_on_phone(app: Flask, page: Page) -> int:
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )
    return utub.id


def _go_to_deck_via_navbar(page: Page, navbar_selector: str) -> None:
    click_on_navbar(page=page)
    wait_then_click_element(page=page, css_selector=navbar_selector)
    wait_for_class_to_be_removed(
        page=page, css_selector=HPL.NAVBAR_DROPDOWN, class_name="collapsing"
    )


def _open_tag_sheet(page: Page) -> None:
    swipe_tag_sheet_open(page=page)
    wait_until_tag_sheet_open(page=page)


def _unhide_gear(page: Page, gear_selector: str) -> None:
    """DOM-only reveal of one gear (two rAFs first, as `_reveal_gears` does, so a
    pending breakpoint re-apply of `hidden` cannot undo it)."""
    page.evaluate(
        """(gearSelector) => new Promise((resolve) => {
            requestAnimationFrame(() => requestAnimationFrame(() => {
                document.querySelector(gearSelector).classList.remove('hidden');
                resolve();
            }));
        })""",
        gear_selector,
    )
    assert (
        page.evaluate(
            "(gearSelector) => document.querySelector(gearSelector)"
            ".classList.contains('hidden')",
            gear_selector,
        )
        is False
    )


def _gear_state(page: Page, gear_selector: str) -> tuple[bool, str]:
    """(has the `hidden` class, computed display) read in a single evaluate."""
    state = page.evaluate(
        """(gearSelector) => {
            const gear = document.querySelector(gearSelector);
            return [gear.classList.contains('hidden'), getComputedStyle(gear).display];
        }""",
        gear_selector,
    )
    return state[0], state[1]


def _expect_touch_target(page: Page, gear_selector: str) -> None:
    expect(page.locator(gear_selector)).to_be_visible()
    box = page.locator(gear_selector).bounding_box()
    assert box is not None, gear_selector
    assert box["width"] >= _MIN_TOUCH_TARGET_PX, (gear_selector, box)
    assert box["height"] >= _MIN_TOUCH_TARGET_PX, (gear_selector, box)


def test_no_gear_rendered_on_phone_without_a_section(
    page_mobile_portrait: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a phone viewport with an owned UTub selected
    WHEN no settings section is registered
    THEN no gear renders on the URL deck or the open Tag sheet
    """
    page = page_mobile_portrait
    _select_owned_utub_on_phone(provide_app, page)
    _assert_no_gear_visible(page)

    _open_tag_sheet(page)
    _assert_no_gear_visible(page)


def test_revealed_gears_are_touch_targets_on_phone(
    page_mobile_portrait: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN a phone viewport with an owned UTub selected
    WHEN the gears are un-hidden through the DOM, deck by deck
    THEN the URLs, UTubs, Members and (with the Tag sheet open) Tags gears are
        each visible and at least 44x44
    """
    page = page_mobile_portrait
    _select_owned_utub_on_phone(provide_app, page)
    # The UTub load is async and every store write re-runs the gear visibility
    # pass (re-adding `hidden`, as no section is registered): wait for the tag
    # filters, rendered from the loaded UTub, before revealing the gears.
    expect(page.locator(HPL.TAG_FILTERS).first).to_be_attached()
    _reveal_gears(page)

    _expect_touch_target(page, HPL.BUTTON_URL_SETTINGS_GEAR)

    _open_tag_sheet(page)
    _expect_touch_target(page, HPL.BUTTON_TAG_SETTINGS_GEAR)

    _go_to_deck_via_navbar(page, HPL.NAVBAR_MEMBER_DECK)
    _expect_touch_target(page, HPL.BUTTON_MEMBER_SETTINGS_GEAR)

    _go_to_deck_via_navbar(page, HPL.NAVBAR_UTUB_DECK)
    _expect_touch_target(page, HPL.BUTTON_UTUB_SETTINGS_GEAR)


def test_tags_gear_hides_in_multi_select_and_returns_on_exit(
    page_mobile_portrait: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN a phone viewport with the Tag sheet open and the Tags gear revealed
    WHEN URL multi-select is entered and then exited
    THEN the Tags gear is hidden during the mode and visible again after it
    """
    page = page_mobile_portrait
    _select_owned_utub_on_phone(provide_app, page)
    expect(page.locator(HPL.TAG_FILTERS).first).to_be_attached()
    _reveal_gears(page)
    _open_tag_sheet(page)
    expect(page.locator(HPL.BUTTON_TAG_SETTINGS_GEAR)).to_be_visible()

    # The open sheet covers the deck's toggle: close it, enter the mode, then
    # reopen the sheet on demand through the bulk tag-filter icon.
    swipe_tag_sheet_closed(page=page)
    wait_until_tag_sheet_collapsed(page=page)
    enter_multi_select_mode(page=page)
    wait_then_click_element(page=page, css_selector=HPL.BULK_TAG_FILTER_ICON)
    wait_until_tag_sheet_open(page=page)
    # No section is registered, so the gear's `hidden` class returns on re-render;
    # re-reveal it so only the mode's CSS rule can keep it hidden.
    _reveal_gears(page)
    # Class and computed display read in one evaluate: `hidden` absent plus
    # display:none proves the mode's CSS rule (not a re-added class) hides it.
    assert _gear_state(page, HPL.BUTTON_TAG_SETTINGS_GEAR) == (False, "none")

    swipe_tag_sheet_closed(page=page)
    wait_until_tag_sheet_collapsed(page=page)
    wait_then_click_element(page=page, css_selector=HPL.BULK_SELECT_EXIT)
    expect(page.locator(HPL.BULK_SELECT_EXIT)).to_be_hidden()
    _open_tag_sheet(page)
    _reveal_gears(page)
    has_hidden_class, display = _gear_state(page, HPL.BUTTON_TAG_SETTINGS_GEAR)
    assert has_hidden_class is False
    assert display != "none"
    expect(page.locator(HPL.BUTTON_TAG_SETTINGS_GEAR)).to_be_visible()


@pytest.mark.parametrize("viewport_width", _PHONE_WIDTHS)
def test_revealed_gears_fit_their_headers_on_small_phones(
    page_mobile_portrait: Page,
    create_test_tags,
    provide_app: Flask,
    viewport_width: int,
):
    """
    GIVEN a 320px or 390px phone viewport with an owned UTub selected
    WHEN each deck's gear is un-hidden through the DOM
    THEN the gear's button container neither overflows nor wraps and stays no
        taller than one 44px touch target
    """
    page = page_mobile_portrait
    page.set_viewport_size({"width": viewport_width, "height": _PHONE_HEIGHT_PX})
    _select_owned_utub_on_phone(provide_app, page)
    # The UTub load is async and every store write re-adds `hidden` to the gears
    # (no section is registered): wait for the loaded UTub's tag filters first.
    expect(page.locator(HPL.TAG_FILTERS).first).to_be_attached()

    def check_fit(gear_selector: str) -> None:
        _unhide_gear(page, gear_selector)
        expect(page.locator(gear_selector)).to_be_visible()
        metrics = gear_container_metrics(page, gear_selector)
        assert metrics["maxMarginBoxRight"] <= metrics["contentRight"] + 0.5, metrics
        # Wrap guard is the height bound, not distinctTops: on phones the deck
        # headers center a 30px filter button beside the 44px gear, so tops
        # legitimately differ without any wrapping.
        assert metrics["containerHeight"] <= _MIN_TOUCH_TARGET_PX + 0.5, metrics

    check_fit(HPL.BUTTON_URL_SETTINGS_GEAR)

    _open_tag_sheet(page)
    check_fit(HPL.BUTTON_TAG_SETTINGS_GEAR)

    _go_to_deck_via_navbar(page, HPL.NAVBAR_MEMBER_DECK)
    check_fit(HPL.BUTTON_MEMBER_SETTINGS_GEAR)

    _go_to_deck_via_navbar(page, HPL.NAVBAR_UTUB_DECK)
    check_fit(HPL.BUTTON_UTUB_SETTINGS_GEAR)
