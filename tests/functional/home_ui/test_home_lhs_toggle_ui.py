import pytest
from flask import Flask
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver

from backend.models.utubs import Utubs
from tests.functional.home_ui.selenium_utils import (
    assert_lhs_panels_hidden,
    assert_lhs_panels_visible,
    toggle_lhs_panels,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.login_utils import (
    login_user_and_select_utub_by_utubid,
    login_user_and_select_utub_by_utubid_mobile,
)
from tests.functional.selenium_utils import (
    wait_then_get_element,
    wait_until_in_focus,
)

pytestmark = pytest.mark.home_ui

_USER_ID_FOR_TEST = 1


def _login_and_select_first_utub(provide_app: Flask, browser: WebDriver):
    with provide_app.app_context():
        utub = Utubs.query.first()
        utub_id = utub.id
    login_user_and_select_utub_by_utubid(
        provide_app, browser, user_id=_USER_ID_FOR_TEST, utub_id=utub_id
    )


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
