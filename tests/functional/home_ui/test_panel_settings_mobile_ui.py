from __future__ import annotations

import re
from typing import Tuple

import pytest
from flask import Flask
from flask.testing import FlaskCliRunner
from playwright.sync_api import Page, expect

from backend.models.utub_members import Member_Role
from backend.utils.strings.utub_strs import (
    PANEL_SETTINGS_MANAGERS_ONLY,
    PANEL_SETTINGS_SAVED,
)
from tests.functional.db_utils import (
    add_mock_urls,
    get_url_in_utub,
    get_utub_this_user_created,
    get_utub_this_user_did_not_create,
    set_member_role_in_utub,
    set_utub_settings,
)
from tests.functional.home_ui.test_panel_settings_ui import (
    _GEARS_WITHOUT_SECTION,
    _assert_only_utubs_gear_visible,
    _reveal_gears,
    gear_container_metrics,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_assert_utils import (
    assert_no_utub_selected,
    assert_panel_visibility_mobile,
)
from tests.functional.playwright_login_utils import (
    login_user_and_select_utub_by_utubid_mobile,
)
from tests.functional.playwright_utils import (
    Decks,
    click_on_navbar,
    dispatch_pointer_drag,
    get_selected_url,
    login_user_to_home_page,
    wait_for_class_to_be_removed,
    wait_for_css_transitions_to_finish,
    wait_then_click_element,
    wait_until_visible_css_selector,
)
from tests.functional.tags_ui.playwright_utils import (
    swipe_tag_sheet_closed,
    swipe_tag_sheet_open,
    wait_until_tag_sheet_collapsed,
    wait_until_tag_sheet_open,
)
from tests.functional.urls_ui.playwright_utils import (
    enter_multi_select_mode,
    expect_selected_scheme,
    wait_for_update_input_highlight,
)

pytestmark = [pytest.mark.home_ui, pytest.mark.mobile_ui]

USER_ID_FOR_TEST = 1

_MIN_TOUCH_TARGET_PX = 44
_MIN_PICKER_TOGGLE_HEIGHT_PX = 46
_PHONE_WIDTHS = (320, 390)
_PHONE_HEIGHT_PX = 800
_PHONE_PORTRAIT_VIEWPORT = {"width": 420, "height": 900}
_DESKTOP_VIEWPORT = {"width": 1100, "height": 900}
_SHEET_DRAG_DISMISS_PX = 500

_HIDE_ON_HTTPS = {"urls": {"default_url_scheme": "https", "hide_scheme_selector": True}}
_STORED_FTP_URL = "ftp://files.example.com/a"
_SHEET_OPEN_CLASS_RE = re.compile(r"(^|\s)panelSettingsSheet--open(\s|$)")

# The open/close/focus/inert/Escape/stacking contracts of the sheet are pinned in
# Vitest (frontend/home/panel-settings/__tests__/sheet.test.ts and
# sheet-history.test.ts). The gear tests below use the DOM-only reveal for the
# decks with no section; the URLs deck has the real "New URLs" section, so the
# sheet acceptance and mobile flows at the end of this module run in a real
# browser. The sheet stacked over the Tag sheet is not reachable here (the Tag
# sheet makes #mainPanel inert and the Tags gear has no section until phase 7).

# Markers on the live DOM nodes: a UTub rebuild replaces the URL cards and so
# drops every expando, which is how an unwanted rebuild is detected.
_MARK_UTUB_DOM_JS = """() => {
    document.querySelector('#listURLs').__u4iSurvivor = true;
    const rows = document.querySelectorAll('.urlRow');
    rows.forEach((row) => { row.__u4iSurvivor = true; });
    return rows.length;
}"""
_UTUB_DOM_SURVIVED_JS = """() => {
    const list = document.querySelector('#listURLs');
    const rows = Array.from(document.querySelectorAll('.urlRow'));
    return (
        list !== null &&
        list.__u4iSurvivor === true &&
        rows.length > 0 &&
        rows.every((row) => row.__u4iSurvivor === true)
    );
}"""


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


def test_urls_and_utubs_gears_rendered_on_phone(
    page_mobile_portrait: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a phone viewport with an owned UTub selected
    WHEN only the UTubs and URLs panels have a registered settings section
    THEN the URLs gear renders on the URL deck, the UTubs gear (registered, but in
        the #leftPanel that selecting a UTub hides on a phone) renders once the
        UTubs deck is reopened from the navbar, and the Members and Tags gears
        (the Tags one on the open Tag sheet) stay hidden
    """
    page = page_mobile_portrait
    _select_owned_utub_on_phone(provide_app, page)
    # Wait for the async UTub load: the UTUB_SELECTED handler hides #leftPanel.
    expect(page.locator(HPL.LEFT_PANEL)).to_be_hidden()
    expect(page.locator(HPL.BUTTON_URL_SETTINGS_GEAR)).to_be_visible()
    expect(page.locator(HPL.BUTTON_UTUB_SETTINGS_GEAR)).not_to_have_class(
        re.compile(r"\bhidden\b")
    )
    expect(page.locator(HPL.BUTTON_UTUB_SETTINGS_GEAR)).to_be_hidden()

    _open_tag_sheet(page)
    for gear_selector in _GEARS_WITHOUT_SECTION:
        expect(page.locator(gear_selector)).to_be_hidden()

    # Reopening the UTubs deck from the navbar shows #leftPanel, and its gear.
    _go_to_deck_via_navbar(page, HPL.NAVBAR_UTUB_DECK)
    expect(page.locator(HPL.BUTTON_UTUB_SETTINGS_GEAR)).to_be_visible()


def test_only_utubs_gear_rendered_on_phone_without_a_selected_utub(
    page_mobile_portrait: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a phone viewport on the home page with no UTub selected
    WHEN the page loads
    THEN only the UTubs gear renders; the URLs, Members and Tags gears do not
    """
    page = page_mobile_portrait
    login_user_to_home_page(app=provide_app, page=page, user_id=USER_ID_FOR_TEST)
    _assert_only_utubs_gear_visible(page)


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
    # pass (re-adding `hidden` to gears with no section): wait for the tag
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
    # that have no section (and re-runs the visibility pass for the rest): wait
    # for the loaded UTub's tag filters first.
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


# ---------------------------------------------------------------------------
# Real-browser sheet acceptance and mobile flows (URLs "New URLs" section)
# ---------------------------------------------------------------------------


def go_back(page: Page) -> None:
    page.go_back()


def go_forward(page: Page) -> None:
    page.go_forward()


def reload(page: Page) -> None:
    page.reload()


def read_history_state(page: Page) -> dict | None:
    return page.evaluate("() => history.state")


def _wait_sheet_history_entry(page: Page, *, keyed: bool) -> None:
    """Wait until the current history entry does (or does not) carry the sheet key."""
    page.wait_for_function(
        "(keyed) => ((history.state && history.state.panelSettingsSheetOpen) "
        "=== true) === keyed",
        arg=keyed,
    )


def _mark_utub_dom(page: Page) -> None:
    assert page.evaluate(_MARK_UTUB_DOM_JS) > 0


def _utub_dom_survived(page: Page) -> bool:
    # A rebuild runs after an async fetch: let in-flight requests land first.
    page.wait_for_load_state("networkidle")
    return page.evaluate(_UTUB_DOM_SURVIVED_JS)


def _login_and_select_owned_utub_on_phone(app: Flask, page: Page) -> int:
    utub_id = _select_owned_utub_on_phone(app, page)
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)
    return utub_id


def _open_urls_sheet(page: Page) -> None:
    gear = page.locator(HPL.BUTTON_URL_SETTINGS_GEAR)
    expect(gear).to_be_visible()
    gear.tap()
    expect(page.locator(HPL.PANEL_SETTINGS_SHEET)).to_have_class(_SHEET_OPEN_CLASS_RE)
    expect(page.locator(HPL.URLS_SETTINGS_DEFAULT_SCHEME)).to_be_visible()
    # bounding_box() returns the transformed rect, which is fractional (e.g.
    # 43.9999px) while the slide-in transition is still running.
    wait_for_css_transitions_to_finish(locator=page.locator(HPL.PANEL_SETTINGS_SHEET))
    _wait_sheet_history_entry(page, keyed=True)


def _expect_sheet_closed(page: Page) -> None:
    expect(page.locator(HPL.PANEL_SETTINGS_SHEET)).to_be_hidden()
    expect(page.locator(HPL.PANEL_SETTINGS_SHEET_BACKDROP)).to_be_hidden()


def _close_sheet_via_close_button(page: Page) -> None:
    page.locator(HPL.PANEL_SETTINGS_SHEET_CLOSE).tap()


def _close_sheet_via_backdrop(page: Page) -> None:
    # The sheet is bottom-anchored: the top-left corner of the backdrop is clear.
    page.locator(HPL.PANEL_SETTINGS_SHEET_BACKDROP).tap(position={"x": 8, "y": 8})


def _close_sheet_via_drag(page: Page) -> None:
    header = page.locator(HPL.PANEL_SETTINGS_SHEET_HEADER)
    box = header.bounding_box()
    assert box is not None
    start_y = box["y"] + box["height"] / 2
    dispatch_pointer_drag(
        page=page,
        css_selector=HPL.PANEL_SETTINGS_SHEET_HEADER,
        start_y=start_y,
        end_y=start_y + _SHEET_DRAG_DISMISS_PX,
    )


def _pick_default_scheme_in_sheet(page: Page, scheme: str) -> None:
    page.locator(HPL.URLS_SETTINGS_DEFAULT_SCHEME).tap()
    listbox = page.locator(HPL.URLS_SETTINGS_SHEET_SCHEME_LISTBOX)
    expect(listbox).to_be_visible()
    page.locator(HPL.URLS_SETTINGS_SHEET_SCHEME_FILTER).fill(scheme)
    option = page.locator(
        f"{HPL.PANEL_SETTINGS_SHEET} "
        + HPL.SCHEME_OPTION_BY_SCHEME_FORMAT.format(scheme=scheme)
    )
    expect(option).to_be_visible()
    option.tap()
    expect(listbox).to_be_hidden()


def _box(page: Page, selector: str) -> dict:
    box = page.locator(selector).bounding_box()
    assert box is not None, selector
    return box


def test_back_closes_sheet_and_leaves_utub_intact(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN the URLs settings sheet open on a phone over a selected UTub
    WHEN browser Back is pressed
    THEN the sheet closes, its history key is gone, the UTub's DOM is not rebuilt
        and the sheet can be opened again
    """
    page = page_mobile_portrait
    _login_and_select_owned_utub_on_phone(provide_app, page)
    _mark_utub_dom(page)

    _open_urls_sheet(page)
    assert read_history_state(page)["panelSettingsSheetOpen"] is True

    go_back(page)

    _expect_sheet_closed(page)
    _wait_sheet_history_entry(page, keyed=False)
    assert _utub_dom_survived(page)
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)

    _open_urls_sheet(page)


def test_second_back_after_sheet_back_lands_on_utub_list(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN the sheet opened over a selected UTub and closed by Back
    WHEN Back is pressed again
    THEN the phone lands on the UTub list with no UTub selected and the sheet
        stays closed (the sheet cannot open with no UTub: no gear is reachable
        there, so this is the real-browser form of "Back with no UTub")
    """
    page = page_mobile_portrait
    _login_and_select_owned_utub_on_phone(provide_app, page)
    _open_urls_sheet(page)

    go_back(page)
    _expect_sheet_closed(page)
    go_back(page)

    assert_no_utub_selected(page=page)
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.UTUBS)
    _expect_sheet_closed(page)
    _wait_sheet_history_entry(page, keyed=False)


@pytest.mark.parametrize(
    "close_sheet",
    [_close_sheet_via_close_button, _close_sheet_via_backdrop, _close_sheet_via_drag],
    ids=["close_button", "backdrop", "drag_to_dismiss"],
)
def test_user_close_removes_its_history_entry(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask, close_sheet
):
    """
    GIVEN the URLs settings sheet open on a phone
    WHEN it is closed by the close button, the backdrop or a drag-to-dismiss
    THEN its history entry is consumed, so the next Back leaves the UTub for the
        UTub list and does not reopen the sheet
    """
    page = page_mobile_portrait
    _login_and_select_owned_utub_on_phone(provide_app, page)
    _open_urls_sheet(page)

    close_sheet(page)

    _expect_sheet_closed(page)
    _wait_sheet_history_entry(page, keyed=False)
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)

    go_back(page)

    assert_no_utub_selected(page=page)
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.UTUBS)
    _expect_sheet_closed(page)


def test_forced_close_then_back_behaves_like_a_base_entry_back(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN the URLs settings sheet open on a phone
    WHEN the viewport crosses the desktop breakpoint (a forced close) and returns
    THEN the history key is stripped in place, and the next Back is plain
        base-entry handling: the sheet stays closed and the UTub stays selected
    """
    page = page_mobile_portrait
    _login_and_select_owned_utub_on_phone(provide_app, page)
    _open_urls_sheet(page)

    page.set_viewport_size(_DESKTOP_VIEWPORT)
    _expect_sheet_closed(page)
    _wait_sheet_history_entry(page, keyed=False)
    page.set_viewport_size(_PHONE_PORTRAIT_VIEWPORT)

    go_back(page)

    _expect_sheet_closed(page)
    _wait_sheet_history_entry(page, keyed=False)
    expect(page.locator(HPL.URL_DECK)).to_be_visible()
    expect(page.locator(HPL.BUTTON_URL_SETTINGS_GEAR)).to_be_visible()


def test_forward_onto_keyed_entry_does_not_reopen_sheet(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN the URLs settings sheet opened and closed by its close button, leaving
        the keyed entry ahead in the history
    WHEN browser Forward lands on that keyed entry
    THEN the sheet does not reopen
    """
    page = page_mobile_portrait
    _login_and_select_owned_utub_on_phone(provide_app, page)
    _open_urls_sheet(page)
    _close_sheet_via_close_button(page)
    _expect_sheet_closed(page)
    _wait_sheet_history_entry(page, keyed=False)

    go_forward(page)

    _wait_sheet_history_entry(page, keyed=True)
    _expect_sheet_closed(page)
    expect(page.locator(HPL.URL_DECK)).to_be_visible()


def test_reload_with_sheet_open_never_reopens_it(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN the URLs settings sheet open on a phone
    WHEN the page is reloaded
    THEN the UTub and URL deck are restored and the sheet stays closed
    """
    page = page_mobile_portrait
    _login_and_select_owned_utub_on_phone(provide_app, page)
    _open_urls_sheet(page)

    reload(page)

    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)
    expect(page.locator(HPL.BUTTON_URL_SETTINGS_GEAR)).to_be_visible()
    _expect_sheet_closed(page)


def test_default_change_in_sheet_starts_create_panel_on_it_with_touch_targets(
    page_mobile_portrait: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN the URLs settings sheet on a touch phone
    WHEN the default scheme is changed to ssh
    THEN the picker toggle is >= 46px tall, every open option and the hide switch
        are >= 44px, "Saved" is announced and a new create panel starts on ssh
    """
    page = page_mobile_portrait
    _login_and_select_owned_utub_on_phone(provide_app, page)
    _open_urls_sheet(page)

    toggle_box = _box(page, HPL.URLS_SETTINGS_DEFAULT_SCHEME)
    assert toggle_box["height"] >= _MIN_PICKER_TOGGLE_HEIGHT_PX, toggle_box
    switch_box = _box(page, HPL.URLS_SETTINGS_HIDE_SWITCH)
    assert switch_box["width"] >= _MIN_TOUCH_TARGET_PX, switch_box
    assert switch_box["height"] >= _MIN_TOUCH_TARGET_PX, switch_box

    page.locator(HPL.URLS_SETTINGS_DEFAULT_SCHEME).tap()
    expect(page.locator(HPL.URLS_SETTINGS_SHEET_SCHEME_LISTBOX)).to_be_visible()
    options = page.locator(HPL.URLS_SETTINGS_SHEET_SCHEME_OPTION_VISIBLE)
    option_count = options.count()
    assert option_count > 0
    for index in range(option_count):
        option_box = options.nth(index).bounding_box()
        assert option_box is not None
        assert option_box["height"] >= _MIN_TOUCH_TARGET_PX, (index, option_box)
    # Close the open list (Escape closes only the list), then pick through it.
    page.keyboard.press("Escape")
    expect(page.locator(HPL.URLS_SETTINGS_SHEET_SCHEME_LISTBOX)).to_be_hidden()
    expect(page.locator(HPL.PANEL_SETTINGS_SHEET)).to_have_class(_SHEET_OPEN_CLASS_RE)

    _pick_default_scheme_in_sheet(page, "ssh")
    expect(page.locator(HPL.PANEL_SETTINGS_ANNOUNCEMENT)).to_contain_text(
        PANEL_SETTINGS_SAVED
    )

    _close_sheet_via_close_button(page)
    _expect_sheet_closed(page)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_CORNER_URL_CREATE)
    expect(page.locator(HPL.WRAP_URL_CREATE)).to_be_visible()
    expect_selected_scheme(
        page=page, toggle_locator=HPL.SCHEME_TOGGLE_CREATE, scheme="ssh"
    )


def test_hidden_selector_mobile_edit_panel_shows_helper_and_keeps_stored_scheme(
    page_mobile_portrait: Page,
    create_test_utubs,
    runner: Tuple[Flask, FlaskCliRunner],
    provide_app: Flask,
):
    """
    GIVEN a UTub that hides the scheme selector and a stored ftp:// URL
    WHEN the consolidated mobile edit panel opens
    THEN the helper line shows, the stored scheme is kept, the selector toggle is
        hidden, the URL input keeps its left border and top-left radius, and Tab
        and Shift+Tab never land on the hidden toggle
    """
    app = provide_app
    _, cli_runner = runner
    add_mock_urls(cli_runner, [_STORED_FTP_URL])
    utub_id = get_utub_this_user_created(app, USER_ID_FOR_TEST).id
    set_utub_settings(app, utub_id, _HIDE_ON_HTTPS)
    page = page_mobile_portrait
    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub_id
    )
    wait_then_click_element(
        page=page,
        css_selector=f"{HPL.ROWS_URLS}[utuburlid='{get_url_in_utub(app, utub_id).id}']",
    )
    get_selected_url(page=page)
    wait_then_click_element(
        page=page,
        css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_STRING_UPDATE}",
    )
    wait_until_visible_css_selector(
        page=page, css_selector=HPL.INPUT_URL_STRING_UPDATE_SELECTED
    )
    wait_for_update_input_highlight(
        page=page, input_css_selector=HPL.INPUT_URL_STRING_UPDATE_SELECTED
    )

    expect(page.locator(HPL.SCHEME_TOGGLE_UPDATE)).to_be_hidden()
    helper = page.locator(HPL.SCHEME_HELPER_UPDATE)
    expect(helper).to_be_visible()
    expect(helper).to_contain_text("ftp://")
    expect(page.locator(HPL.INPUT_URL_STRING_UPDATE_SELECTED)).to_have_value(
        "files.example.com/a"
    )

    styles = page.evaluate(
        """(inputSelector) => {
            const style = getComputedStyle(document.querySelector(inputSelector));
            return {
                borderLeftWidth: parseFloat(style.borderLeftWidth),
                borderTopLeftRadius: parseFloat(style.borderTopLeftRadius),
            };
        }""",
        HPL.INPUT_URL_STRING_UPDATE_SELECTED,
    )
    assert styles["borderLeftWidth"] > 0, styles
    assert styles["borderTopLeftRadius"] > 0, styles

    url_input = page.locator(HPL.INPUT_URL_STRING_UPDATE_SELECTED)
    for key in ("Shift+Tab", "Tab"):
        url_input.focus()
        page.keyboard.press(key)
        assert not page.evaluate(
            "document.activeElement !== null && "
            "document.activeElement.classList.contains('urlSchemeToggle')"
        ), key


def test_plain_member_sees_read_only_sheet_on_phone(
    page_mobile_portrait: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a plain member of a UTub on a phone
    WHEN they open the URLs settings sheet
    THEN both controls are aria-disabled yet focusable and the managers-only
        read-only note shows
    """
    app = provide_app
    utub_id = get_utub_this_user_did_not_create(app, USER_ID_FOR_TEST).id
    set_member_role_in_utub(app, USER_ID_FOR_TEST, utub_id, Member_Role.MEMBER)
    page = page_mobile_portrait
    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub_id
    )
    _open_urls_sheet(page)

    scheme_toggle = page.locator(HPL.URLS_SETTINGS_DEFAULT_SCHEME)
    hide_switch = page.locator(HPL.URLS_SETTINGS_HIDE_SWITCH)
    expect(scheme_toggle).to_have_attribute("aria-disabled", "true")
    expect(hide_switch).to_have_attribute("aria-disabled", "true")
    scheme_toggle.focus()
    expect(scheme_toggle).to_be_focused()
    hide_switch.focus()
    expect(hide_switch).to_be_focused()
    expect(page.locator(HPL.URLS_SETTINGS_SHEET_READ_ONLY_NOTE)).to_contain_text(
        PANEL_SETTINGS_MANAGERS_ONLY
    )


# ---------------------------------------------------------------------------
# Swipe up to expand (grabber / header drag between the default and expanded
# detents)
# ---------------------------------------------------------------------------

_SHEET_EXPANDED_CLASS_RE = re.compile(r"(^|\s)panelSettingsSheet--expanded(\s|$)")
# Slow steps keep the per-step velocity under the 0.5px/ms fling threshold, so
# only the distance decides the detent.
_SLOW_STEP_DELAY_MS = 150
_SWIPE_UP_PX = 300
_EXPANDED_MIN_VIEWPORT_FRACTION = 0.9


def _sheet_height(page: Page) -> float:
    return _box(page, HPL.PANEL_SETTINGS_SHEET)["height"]


def _drag_sheet_header(
    page: Page, *, dy: float, step_delay_ms: int = _SLOW_STEP_DELAY_MS
) -> None:
    """Touch-drag the sheet header by dy px (negative = up) from its centre."""
    header = _box(page, HPL.PANEL_SETTINGS_SHEET_HEADER)
    start_y = header["y"] + header["height"] / 2
    dispatch_pointer_drag(
        page=page,
        css_selector=HPL.PANEL_SETTINGS_SHEET_HEADER,
        start_y=start_y,
        end_y=start_y + dy,
        step_delay_ms=step_delay_ms,
    )


def _wait_sheet_settled(page: Page) -> None:
    """Wait until the settle transition ended and the inline pose was dropped."""
    page.wait_for_function(
        "(selector) => { const el = document.querySelector(selector);"
        " return el !== null && el.style.height === '' && el.style.maxHeight === ''"
        " && !el.classList.contains('panelSettingsSheet--dragging'); }",
        arg=HPL.PANEL_SETTINGS_SHEET,
    )
    wait_for_css_transitions_to_finish(locator=page.locator(HPL.PANEL_SETTINGS_SHEET))


def _expand_sheet_by_swipe(page: Page) -> None:
    _drag_sheet_header(page, dy=-_SWIPE_UP_PX)
    expect(page.locator(HPL.PANEL_SETTINGS_SHEET)).to_have_class(
        _SHEET_EXPANDED_CLASS_RE
    )
    _wait_sheet_settled(page)


def test_swipe_up_expands_sheet_without_extra_content(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN the URLs settings sheet open at its content-sized default height
    WHEN the grabber/header is swiped up
    THEN the sheet expands to a fixed tall height (about 95% of the viewport),
        taller than before, stays open and its body is a scroll container
    """
    page = page_mobile_portrait
    _login_and_select_owned_utub_on_phone(provide_app, page)
    _open_urls_sheet(page)
    default_height = _sheet_height(page)

    _expand_sheet_by_swipe(page)

    expanded_height = _sheet_height(page)
    viewport_height = _PHONE_PORTRAIT_VIEWPORT["height"]
    assert expanded_height > default_height, (default_height, expanded_height)
    assert expanded_height >= viewport_height * _EXPANDED_MIN_VIEWPORT_FRACTION, (
        expanded_height
    )
    assert page.evaluate(
        "(selector) => getComputedStyle(document.querySelector(selector)).overflowY",
        HPL.PANEL_SETTINGS_SHEET_BODY,
    ) in ("auto", "scroll")
    expect(page.locator(HPL.PANEL_SETTINGS_SHEET)).to_have_class(_SHEET_OPEN_CLASS_RE)


def test_short_swipe_up_keeps_default_height(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN the URLs settings sheet open at its default height
    WHEN the header is swiped up only a few pixels, slowly
    THEN the sheet snaps back to the default height and stays open
    """
    page = page_mobile_portrait
    _login_and_select_owned_utub_on_phone(provide_app, page)
    _open_urls_sheet(page)
    default_height = _sheet_height(page)

    _drag_sheet_header(page, dy=-20)
    _wait_sheet_settled(page)

    expect(page.locator(HPL.PANEL_SETTINGS_SHEET)).not_to_have_class(
        _SHEET_EXPANDED_CLASS_RE
    )
    assert _sheet_height(page) == pytest.approx(default_height, abs=1)


def test_swipe_down_from_expanded_returns_to_default_not_dismissed(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN the URLs settings sheet expanded by a swipe up
    WHEN the header is swiped down by a medium distance (less than the way back
        to the default height plus the dismiss threshold)
    THEN the sheet returns to its default height and is still open
    """
    page = page_mobile_portrait
    _login_and_select_owned_utub_on_phone(provide_app, page)
    _open_urls_sheet(page)
    default_height = _sheet_height(page)
    _expand_sheet_by_swipe(page)
    travel = _sheet_height(page) - default_height

    _drag_sheet_header(page, dy=travel * 0.6)
    _wait_sheet_settled(page)

    expect(page.locator(HPL.PANEL_SETTINGS_SHEET)).to_have_class(_SHEET_OPEN_CLASS_RE)
    expect(page.locator(HPL.PANEL_SETTINGS_SHEET)).not_to_have_class(
        _SHEET_EXPANDED_CLASS_RE
    )
    assert _sheet_height(page) == pytest.approx(default_height, abs=1)
    _wait_sheet_history_entry(page, keyed=True)


def test_swipe_down_far_from_expanded_dismisses(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN the URLs settings sheet expanded by a swipe up
    WHEN the header is dragged well past the default height
    THEN the sheet is dismissed like any other user close
    """
    page = page_mobile_portrait
    _login_and_select_owned_utub_on_phone(provide_app, page)
    _open_urls_sheet(page)
    _expand_sheet_by_swipe(page)

    # The whole expanded height: back to default, then the full default height on.
    _drag_sheet_header(page, dy=_sheet_height(page), step_delay_ms=0)

    _expect_sheet_closed(page)
    _wait_sheet_history_entry(page, keyed=False)


def test_swipe_down_from_default_dismisses(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN the URLs settings sheet open at its default height
    WHEN the header is swiped down past the threshold
    THEN the sheet is dismissed
    """
    page = page_mobile_portrait
    _login_and_select_owned_utub_on_phone(provide_app, page)
    _open_urls_sheet(page)

    _drag_sheet_header(page, dy=_SHEET_DRAG_DISMISS_PX, step_delay_ms=0)

    _expect_sheet_closed(page)
    _wait_sheet_history_entry(page, keyed=False)


def test_reopened_sheet_starts_at_default_height(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN the URLs settings sheet expanded and then closed with its close button
    WHEN it is opened again
    THEN it starts at the default height, not expanded
    """
    page = page_mobile_portrait
    _login_and_select_owned_utub_on_phone(provide_app, page)
    _open_urls_sheet(page)
    default_height = _sheet_height(page)
    _expand_sheet_by_swipe(page)

    _close_sheet_via_close_button(page)
    _expect_sheet_closed(page)
    _wait_sheet_history_entry(page, keyed=False)
    _open_urls_sheet(page)

    expect(page.locator(HPL.PANEL_SETTINGS_SHEET)).not_to_have_class(
        _SHEET_EXPANDED_CLASS_RE
    )
    assert _sheet_height(page) == pytest.approx(default_height, abs=1)
