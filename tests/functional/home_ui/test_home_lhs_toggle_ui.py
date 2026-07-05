from __future__ import annotations

import re

import pytest
from flask import Flask
from playwright.sync_api import Page, expect

from backend.models.utubs import Utubs
from tests.functional.db_utils import (
    create_test_cross_utub_searchable_data,
    get_utub_this_user_created,
    get_utub_this_user_did_not_create,
)
from tests.functional.home_ui.playwright_utils import (
    assert_lhs_panels_hidden,
    assert_lhs_panels_visible,
    toggle_lhs_panels,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.members_ui.playwright_utils import leave_utub_as_member
from tests.functional.playwright_assert_utils import assert_visible_css_selector
from tests.functional.playwright_login_utils import (
    login_user_and_select_utub_by_name,
    login_user_and_select_utub_by_utubid,
    login_user_and_select_utub_by_utubid_mobile,
)
from tests.functional.playwright_utils import (
    login_user_to_home_page,
    wait_then_get_element,
    wait_until_hidden,
    wait_until_in_focus,
)
from tests.functional.search_ui.playwright_utils import open_cross_search_via_trigger
from tests.functional.utubs_ui.playwright_utils import delete_utub_as_creator

pytestmark = pytest.mark.home_ui

_USER_ID_FOR_TEST = 1
_MAIN_PANEL_COLLAPSED_CLASS = "lhs-collapsed"

# Viewport widths straddling the 992px desktop/mobile (TABLET_WIDTH) breakpoint
# that governs `isMobile()` and the matchMedia handler reconciling LHS state.
_DESKTOP_VIEWPORT_WIDTH_PX = 1920
_DESKTOP_VIEWPORT_HEIGHT_PX = 1080
_MOBILE_VIEWPORT_WIDTH_PX = 420
_MOBILE_VIEWPORT_HEIGHT_PX = 900


def _login_and_select_first_utub(provide_app: Flask, page: Page) -> None:
    with provide_app.app_context():
        utub = Utubs.query.first()
        utub_id = utub.id
    login_user_and_select_utub_by_utubid(
        app=provide_app, page=page, user_id=_USER_ID_FOR_TEST, utub_id=utub_id
    )


def test_seam_toggle_hides_and_restores_lhs(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN a logged-in user on the desktop home page with a UTub selected
    WHEN the user clicks the seam chevron toggle, then clicks it again
    THEN the first click collapses the LHS (URL deck reclaims width) and the
        second click restores it; the seam button itself stays visible/clickable
        while collapsed (it is a sibling of #leftPanel, not a child).
    """
    _login_and_select_first_utub(provide_app, page)

    # Before-state: the LHS is visible (no collapsed class yet).
    assert_lhs_panels_visible(page=page)

    toggle_lhs_panels(page=page, via="seam")
    # assert_lhs_panels_hidden confirms the LHS animated to width:0/hidden,
    # which means the center panel has reclaimed the 350px gutter.
    assert_lhs_panels_hidden(page=page)
    # The seam button is a sibling of #leftPanel (not a child), so the
    # collapsed-state `visibility: hidden` rule does not hide it — the user
    # can still click it to expand.
    expect(page.locator(HPL.LHS_TOGGLE_SEAM_BTN).first).to_be_visible()

    toggle_lhs_panels(page=page, via="seam")
    assert_lhs_panels_visible(page=page)


def test_url_header_toggle_hides_and_restores_lhs(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN a logged-in user on the desktop home page with a UTub selected
    WHEN the user clicks the mirror toggle in the URL deck header twice
    THEN the LHS collapses and then restores (the second affordance routes
        through the same shared resolver).
    """
    _login_and_select_first_utub(provide_app, page)

    assert_lhs_panels_visible(page=page)

    toggle_lhs_panels(page=page, via="url_header")
    assert_lhs_panels_hidden(page=page)

    toggle_lhs_panels(page=page, via="url_header")
    assert_lhs_panels_visible(page=page)


def test_seam_toggle_keyboard_activation_collapses_and_keeps_focus(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN a logged-in user on the desktop home page with a UTub selected
    WHEN the user focuses the seam toggle button and presses Enter, then Space
    THEN the native <button> activates on both keys (Enter collapses, Space
        re-expands) and focus remains on the toggle throughout (it stays a
        focusable sibling of the collapsed panel).
    """
    _login_and_select_first_utub(provide_app, page)

    assert_lhs_panels_visible(page=page)

    seam_button = wait_then_get_element(page=page, css_selector=HPL.LHS_TOGGLE_SEAM_BTN)
    seam_button.focus()
    wait_until_in_focus(page=page, css_selector=HPL.LHS_TOGGLE_SEAM_BTN)

    # Enter activates the native button -> collapse.
    seam_button.press("Enter")
    assert_lhs_panels_hidden(page=page)
    wait_until_in_focus(page=page, css_selector=HPL.LHS_TOGGLE_SEAM_BTN)

    # Space also activates a native <button> -> re-expand; focus is retained.
    seam_button.press(" ")
    assert_lhs_panels_visible(page=page)
    wait_until_in_focus(page=page, css_selector=HPL.LHS_TOGGLE_SEAM_BTN)


def test_url_header_toggle_hidden_on_initial_load_with_no_utub(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN a logged-in user on the desktop home page with no UTub selected
    WHEN the page initializes
    THEN the URL-header LHS minify toggle is hidden (it is only meaningful once
        a UTub is open).
    """
    login_user_to_home_page(app=provide_app, page=page, user_id=_USER_ID_FOR_TEST)

    wait_then_get_element(page=page, css_selector=HPL.URL_DECK)
    expect(page.locator(HPL.LHS_TOGGLE_HEADER_BTN)).to_be_hidden()


def test_url_header_toggle_visible_when_utub_selected(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN a logged-in user on the desktop home page with no UTub selected
        (header toggle hidden)
    WHEN the user selects a UTub
    THEN the URL-header LHS minify toggle becomes visible.
    """
    login_user_to_home_page(app=provide_app, page=page, user_id=_USER_ID_FOR_TEST)
    expect(page.locator(HPL.LHS_TOGGLE_HEADER_BTN)).to_be_hidden()

    _login_and_select_first_utub(provide_app, page)

    expect(page.locator(HPL.LHS_TOGGLE_HEADER_BTN)).to_be_visible()


def test_url_header_toggle_hidden_after_leaving_utub(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a member has a UTub selected (header toggle visible)
    WHEN they leave the UTub, after which no UTub is selected (others remain)
    THEN the URL-header LHS minify toggle is hidden again.
    """
    utub_user_member_of = get_utub_this_user_did_not_create(
        provide_app, _USER_ID_FOR_TEST
    )
    login_user_and_select_utub_by_name(
        app=provide_app,
        page=page,
        user_id=_USER_ID_FOR_TEST,
        utub_name=utub_user_member_of.name,
    )

    expect(page.locator(HPL.LHS_TOGGLE_HEADER_BTN)).to_be_visible()

    leave_utub_as_member(page=page, utub_to_leave=utub_user_member_of)

    expect(page.locator(HPL.LHS_TOGGLE_HEADER_BTN)).to_be_hidden()


def test_url_header_toggle_hidden_after_deleting_utub(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN an owner has a UTub selected (header toggle visible)
    WHEN they delete the UTub, after which no UTub is selected (others remain)
    THEN the URL-header LHS minify toggle is hidden again.
    """
    utub_user_created = get_utub_this_user_created(provide_app, _USER_ID_FOR_TEST)
    login_user_and_select_utub_by_name(
        app=provide_app,
        page=page,
        user_id=_USER_ID_FOR_TEST,
        utub_name=utub_user_created.name,
    )

    expect(page.locator(HPL.LHS_TOGGLE_HEADER_BTN)).to_be_visible()

    delete_utub_as_creator(page=page, utub_to_delete=utub_user_created)

    expect(page.locator(HPL.LHS_TOGGLE_HEADER_BTN)).to_be_hidden()


@pytest.mark.mobile_ui
def test_lhs_toggle_not_visible_on_mobile(
    page_mobile_portrait: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN a logged-in user on a mobile-portrait viewport (below 992px)
    WHEN the home page is loaded
    THEN neither LHS toggle affordance is visible — the mobile single-screen
        nav governs panels there.
    """
    page = page_mobile_portrait
    with provide_app.app_context():
        utub = Utubs.query.first()
        utub_id = utub.id

    login_user_and_select_utub_by_utubid_mobile(
        app=provide_app, page=page, user_id=_USER_ID_FOR_TEST, utub_id=utub_id
    )

    expect(page.locator(HPL.LHS_TOGGLE_SEAM_BTN)).to_be_hidden()
    expect(page.locator(HPL.LHS_TOGGLE_HEADER_BTN)).to_be_hidden()


def _enter_cross_search_then_exit_via_escape(page: Page) -> None:
    """Open cross-UTub search via the navbar trigger, then close it with Escape.

    The trigger and the Escape close both route through the same
    `setSearchModeActive(...)` writer the LHS resolver composes with the manual
    collapse intent, so this exercises the real entry/exit path the resolver
    must survive.
    """
    open_cross_search_via_trigger(page=page)
    assert_visible_css_selector(page=page, css_selector=HPL.CROSS_SEARCH_MODE)

    # Escape is delivered to the focused search input (the trigger focuses it on
    # open); waiting for focus first guarantees the keystroke lands.
    wait_until_in_focus(page=page, css_selector=HPL.CROSS_SEARCH_INPUT)
    page.locator(HPL.CROSS_SEARCH_INPUT).press("Escape")
    wait_until_hidden(page=page, css_selector=HPL.CROSS_SEARCH_MODE)


def test_cross_search_round_trip_preserves_manual_lhs_collapse(
    page: Page, create_test_users, provide_app: Flask
):
    """
    GIVEN a desktop user who has manually collapsed the LHS via the seam toggle
    WHEN they enter cross-UTub search mode and then exit it
    THEN the LHS stays collapsed afterward — search exit does not clobber the
        retained manual-collapse intent (resolver OR of userCollapsedLHS and
        searchModeActive).
    """
    seeded = create_test_cross_utub_searchable_data(provide_app, _USER_ID_FOR_TEST)
    login_user_and_select_utub_by_utubid(
        app=provide_app,
        page=page,
        user_id=_USER_ID_FOR_TEST,
        utub_id=seeded[0]["utub_id"],
    )

    # Manually collapse the LHS, then prove it is collapsed before search opens.
    assert_lhs_panels_visible(page=page)
    toggle_lhs_panels(page=page, via="seam")
    assert_lhs_panels_hidden(page=page)

    _enter_cross_search_then_exit_via_escape(page)

    # The manual collapse survives the search round-trip.
    assert_lhs_panels_hidden(page=page)


def test_cross_search_round_trip_restores_uncollapsed_lhs(
    page: Page, create_test_users, provide_app: Flask
):
    """
    GIVEN a desktop user who has NOT collapsed the LHS
    WHEN they enter cross-UTub search mode (which hides the LHS) and then exit
    THEN the LHS is restored to visible — search exit releases its own hide
        intent without leaving the panel stuck collapsed.
    """
    seeded = create_test_cross_utub_searchable_data(provide_app, _USER_ID_FOR_TEST)
    login_user_and_select_utub_by_utubid(
        app=provide_app,
        page=page,
        user_id=_USER_ID_FOR_TEST,
        utub_id=seeded[0]["utub_id"],
    )

    # Before-state: LHS visible and no manual collapse recorded.
    assert_lhs_panels_visible(page=page)

    _enter_cross_search_then_exit_via_escape(page)

    # Search exit restores the LHS rather than stranding it collapsed.
    assert_lhs_panels_visible(page=page)


def test_viewport_crossing_drops_then_reapplies_lhs_collapse(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN a desktop user who has manually collapsed the LHS
    WHEN the viewport shrinks below the 992px breakpoint and then grows back
    THEN the `lhs-collapsed` desktop class is dropped on mobile (the mobile
        single-screen nav governs panels there) and re-applied on the return to
        desktop (the retained manual intent is re-asserted by the matchMedia
        reconciler).
    """
    _login_and_select_first_utub(provide_app, page)

    # Collapse on desktop and confirm the collapsed state class is present.
    assert_lhs_panels_visible(page=page)
    toggle_lhs_panels(page=page, via="seam")
    assert_lhs_panels_hidden(page=page)

    # Cross below the breakpoint -> mobile: the desktop collapse class is dropped.
    page.set_viewport_size(
        {"width": _MOBILE_VIEWPORT_WIDTH_PX, "height": _MOBILE_VIEWPORT_HEIGHT_PX}
    )
    expect(page.locator(HPL.MAIN_PANEL)).not_to_have_class(
        re.compile(rf"(^|\s){re.escape(_MAIN_PANEL_COLLAPSED_CLASS)}(\s|$)")
    )

    # Cross back above the breakpoint -> desktop: the retained intent re-applies.
    page.set_viewport_size(
        {"width": _DESKTOP_VIEWPORT_WIDTH_PX, "height": _DESKTOP_VIEWPORT_HEIGHT_PX}
    )
    expect(page.locator(HPL.MAIN_PANEL)).to_have_class(
        re.compile(rf"(^|\s){re.escape(_MAIN_PANEL_COLLAPSED_CLASS)}(\s|$)")
    )
