import pytest
from flask import Flask
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.ui import WebDriverWait

from backend.models.utubs import Utubs
from tests.functional.assert_utils import assert_visible_css_selector
from tests.functional.db_utils import (
    create_test_cross_utub_searchable_data,
    get_utub_this_user_created,
    get_utub_this_user_did_not_create,
)
from tests.functional.home_ui.selenium_utils import (
    assert_lhs_panels_hidden,
    assert_lhs_panels_visible,
    toggle_lhs_panels,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.login_utils import (
    login_user_and_select_utub_by_name,
    login_user_and_select_utub_by_utubid,
    login_user_and_select_utub_by_utubid_mobile,
    login_user_to_home_page,
)
from tests.functional.members_ui.selenium_utils import leave_utub_as_member
from tests.functional.search_ui.selenium_utils import open_cross_search_via_trigger
from tests.functional.selenium_utils import (
    wait_then_get_element,
    wait_until_hidden,
    wait_until_in_focus,
)
from tests.functional.utubs_ui.selenium_utils import delete_utub_as_creator

pytestmark = pytest.mark.home_ui

_USER_ID_FOR_TEST = 1

# Viewport widths straddling the 992px desktop/mobile (TABLET_WIDTH) breakpoint
# that governs `isMobile()` and the matchMedia handler reconciling LHS state.
_DESKTOP_VIEWPORT_WIDTH_PX = 1920
_DESKTOP_VIEWPORT_HEIGHT_PX = 1080
_MOBILE_VIEWPORT_WIDTH_PX = 420
_MOBILE_VIEWPORT_HEIGHT_PX = 900
_MAIN_PANEL_COLLAPSED_CLASS = "lhs-collapsed"


def _main_panel_has_collapsed_class(browser: WebDriver) -> bool:
    return bool(
        browser.execute_script(
            "return document.querySelector(arguments[0])"
            ".classList.contains(arguments[1]);",
            HPL.MAIN_PANEL,
            _MAIN_PANEL_COLLAPSED_CLASS,
        )
    )


def _login_and_select_first_utub(provide_app: Flask, browser: WebDriver):
    with provide_app.app_context():
        utub = Utubs.query.first()
        utub_id = utub.id
    login_user_and_select_utub_by_utubid(
        provide_app, browser, user_id=_USER_ID_FOR_TEST, utub_id=utub_id
    )


def _header_toggle_displayed(browser: WebDriver) -> bool:
    return browser.find_element(
        By.CSS_SELECTOR, HPL.LHS_TOGGLE_HEADER_BTN
    ).is_displayed()


def test_seam_toggle_hides_and_restores_lhs(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    GIVEN a logged-in user on the desktop home page with a UTub selected
    WHEN the user clicks the seam chevron toggle, then clicks it again
    THEN the first click collapses the LHS (URL deck reclaims width) and the
        second click restores it; the seam button itself stays visible/clickable
        while collapsed (it is a sibling of #leftPanel, not a child).
    """
    _login_and_select_first_utub(provide_app, browser)

    # Before-state: the LHS is visible (no collapsed class yet).
    assert_lhs_panels_visible(browser)

    toggle_lhs_panels(browser, via="seam")
    # assert_lhs_panels_hidden confirms the LHS animated to width:0/hidden,
    # which means the center panel has reclaimed the 350px gutter.
    assert_lhs_panels_hidden(browser)
    # The seam button is a sibling of #leftPanel (not a child), so the
    # collapsed-state `visibility: hidden` rule does not hide it — the user
    # can still click it to expand.
    assert browser.find_element(By.CSS_SELECTOR, HPL.LHS_TOGGLE_SEAM_BTN).is_displayed()

    toggle_lhs_panels(browser, via="seam")
    assert_lhs_panels_visible(browser)


def test_url_header_toggle_hides_and_restores_lhs(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    GIVEN a logged-in user on the desktop home page with a UTub selected
    WHEN the user clicks the mirror toggle in the URL deck header twice
    THEN the LHS collapses and then restores (the second affordance routes
        through the same shared resolver).
    """
    _login_and_select_first_utub(provide_app, browser)

    assert_lhs_panels_visible(browser)

    toggle_lhs_panels(browser, via="url_header")
    assert_lhs_panels_hidden(browser)

    toggle_lhs_panels(browser, via="url_header")
    assert_lhs_panels_visible(browser)


def test_seam_toggle_keyboard_activation_collapses_and_keeps_focus(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    GIVEN a logged-in user on the desktop home page with a UTub selected
    WHEN the user focuses the seam toggle button and presses Enter, then Space
    THEN the native <button> activates on both keys (Enter collapses, Space
        re-expands) and focus remains on the toggle throughout (it stays a
        focusable sibling of the collapsed panel).
    """
    _login_and_select_first_utub(provide_app, browser)

    assert_lhs_panels_visible(browser)

    seam_button = wait_then_get_element(browser, HPL.LHS_TOGGLE_SEAM_BTN, time=3)
    assert seam_button is not None
    browser.execute_script("arguments[0].focus();", seam_button)
    wait_until_in_focus(browser, HPL.LHS_TOGGLE_SEAM_BTN)

    # Enter activates the native button -> collapse.
    seam_button.send_keys(Keys.ENTER)
    assert_lhs_panels_hidden(browser)
    wait_until_in_focus(browser, HPL.LHS_TOGGLE_SEAM_BTN)

    # Space also activates a native <button> -> re-expand; focus is retained.
    seam_button.send_keys(Keys.SPACE)
    assert_lhs_panels_visible(browser)
    wait_until_in_focus(browser, HPL.LHS_TOGGLE_SEAM_BTN)


def test_url_header_toggle_hidden_on_initial_load_with_no_utub(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    GIVEN a logged-in user on the desktop home page with no UTub selected
    WHEN the page initializes
    THEN the URL-header LHS minify toggle is hidden (it is only meaningful once
        a UTub is open).
    """
    login_user_to_home_page(provide_app, browser, user_id=_USER_ID_FOR_TEST)

    wait_then_get_element(browser, HPL.URL_DECK, time=3)
    assert not _header_toggle_displayed(browser)


def test_url_header_toggle_visible_when_utub_selected(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    GIVEN a logged-in user on the desktop home page with no UTub selected
        (header toggle hidden)
    WHEN the user selects a UTub
    THEN the URL-header LHS minify toggle becomes visible.
    """
    login_user_to_home_page(provide_app, browser, user_id=_USER_ID_FOR_TEST)
    assert not _header_toggle_displayed(browser)

    _login_and_select_first_utub(provide_app, browser)

    WebDriverWait(browser, 10).until(lambda driver: _header_toggle_displayed(driver))
    assert _header_toggle_displayed(browser)


def test_url_header_toggle_hidden_after_leaving_utub(
    browser: WebDriver, create_test_utubmembers, provide_app: Flask
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
        provide_app, browser, _USER_ID_FOR_TEST, utub_user_member_of.name
    )

    assert _header_toggle_displayed(browser)

    leave_utub_as_member(browser, utub_user_member_of)

    WebDriverWait(browser, 10).until(
        lambda driver: not _header_toggle_displayed(driver)
    )
    assert not _header_toggle_displayed(browser)


def test_url_header_toggle_hidden_after_deleting_utub(
    browser: WebDriver, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN an owner has a UTub selected (header toggle visible)
    WHEN they delete the UTub, after which no UTub is selected (others remain)
    THEN the URL-header LHS minify toggle is hidden again.
    """
    utub_user_created = get_utub_this_user_created(provide_app, _USER_ID_FOR_TEST)
    login_user_and_select_utub_by_name(
        provide_app, browser, _USER_ID_FOR_TEST, utub_user_created.name
    )

    assert _header_toggle_displayed(browser)

    delete_utub_as_creator(browser, utub_user_created)

    WebDriverWait(browser, 10).until(
        lambda driver: not _header_toggle_displayed(driver)
    )
    assert not _header_toggle_displayed(browser)


@pytest.mark.mobile_ui
def test_lhs_toggle_not_visible_on_mobile(
    browser_mobile_portrait: WebDriver, create_test_tags, provide_app: Flask
):
    """
    GIVEN a logged-in user on a mobile-portrait viewport (below 992px)
    WHEN the home page is loaded
    THEN neither LHS toggle affordance is visible — the mobile single-screen
        nav governs panels there.
    """
    with provide_app.app_context():
        utub = Utubs.query.first()
        utub_id = utub.id

    login_user_and_select_utub_by_utubid_mobile(
        provide_app, browser_mobile_portrait, user_id=_USER_ID_FOR_TEST, utub_id=utub_id
    )

    assert not browser_mobile_portrait.find_element(
        By.CSS_SELECTOR, HPL.LHS_TOGGLE_SEAM_BTN
    ).is_displayed()
    assert not browser_mobile_portrait.find_element(
        By.CSS_SELECTOR, HPL.LHS_TOGGLE_HEADER_BTN
    ).is_displayed()


def _enter_cross_search_then_exit_via_escape(browser: WebDriver):
    """Open cross-UTub search via the navbar trigger, then close it with Escape.

    The trigger and the Escape close both route through the same
    `setSearchModeActive(...)` writer the LHS resolver composes with the manual
    collapse intent, so this exercises the real entry/exit path the resolver
    must survive.
    """
    open_cross_search_via_trigger(browser)
    assert_visible_css_selector(browser, HPL.CROSS_SEARCH_MODE, time=10)

    # Escape is delivered to the focused search input (the trigger focuses it on
    # open); waiting for focus first guarantees the keystroke lands.
    wait_until_in_focus(browser, HPL.CROSS_SEARCH_INPUT)
    browser.switch_to.active_element.send_keys(Keys.ESCAPE)
    wait_until_hidden(browser, HPL.CROSS_SEARCH_MODE, timeout=10)


def test_cross_search_round_trip_preserves_manual_lhs_collapse(
    browser: WebDriver, create_test_users, provide_app: Flask
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
        provide_app, browser, user_id=_USER_ID_FOR_TEST, utub_id=seeded[0]["utub_id"]
    )

    # Manually collapse the LHS, then prove it is collapsed before search opens.
    assert_lhs_panels_visible(browser)
    toggle_lhs_panels(browser, via="seam")
    assert_lhs_panels_hidden(browser)

    _enter_cross_search_then_exit_via_escape(browser)

    # The manual collapse survives the search round-trip.
    assert_lhs_panels_hidden(browser)


def test_cross_search_round_trip_restores_uncollapsed_lhs(
    browser: WebDriver, create_test_users, provide_app: Flask
):
    """
    GIVEN a desktop user who has NOT collapsed the LHS
    WHEN they enter cross-UTub search mode (which hides the LHS) and then exit
    THEN the LHS is restored to visible — search exit releases its own hide
        intent without leaving the panel stuck collapsed.
    """
    seeded = create_test_cross_utub_searchable_data(provide_app, _USER_ID_FOR_TEST)
    login_user_and_select_utub_by_utubid(
        provide_app, browser, user_id=_USER_ID_FOR_TEST, utub_id=seeded[0]["utub_id"]
    )

    # Before-state: LHS visible and no manual collapse recorded.
    assert_lhs_panels_visible(browser)

    _enter_cross_search_then_exit_via_escape(browser)

    # Search exit restores the LHS rather than stranding it collapsed.
    assert_lhs_panels_visible(browser)


def test_viewport_crossing_drops_then_reapplies_lhs_collapse(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    GIVEN a desktop user who has manually collapsed the LHS
    WHEN the viewport shrinks below the 992px breakpoint and then grows back
    THEN the `lhs-collapsed` desktop class is dropped on mobile (the mobile
        single-screen nav governs panels there) and re-applied on the return to
        desktop (the retained manual intent is re-asserted by the matchMedia
        reconciler).
    """
    _login_and_select_first_utub(provide_app, browser)

    # Collapse on desktop and confirm the collapsed state class is present.
    assert_lhs_panels_visible(browser)
    toggle_lhs_panels(browser, via="seam")
    assert_lhs_panels_hidden(browser)

    # Cross below the breakpoint -> mobile: the desktop collapse class is dropped.
    browser.set_window_size(
        width=_MOBILE_VIEWPORT_WIDTH_PX, height=_MOBILE_VIEWPORT_HEIGHT_PX
    )
    WebDriverWait(browser, 10).until(
        lambda driver: not _main_panel_has_collapsed_class(driver)
    )
    assert not _main_panel_has_collapsed_class(browser)

    # Cross back above the breakpoint -> desktop: the retained intent re-applies.
    browser.set_window_size(
        width=_DESKTOP_VIEWPORT_WIDTH_PX, height=_DESKTOP_VIEWPORT_HEIGHT_PX
    )
    WebDriverWait(browser, 10).until(_main_panel_has_collapsed_class)
    assert _main_panel_has_collapsed_class(browser)
