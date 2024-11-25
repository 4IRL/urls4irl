# External libraries
import pytest
from selenium.webdriver.common.by import By

from selenium.webdriver.remote.webdriver import WebDriver

from selenium.webdriver.support import expected_conditions as EC

# Internal libraries
from tests.functional.locators import MainPageLocators as MPL
from tests.functional.locators import SplashPageLocators as SPL
from tests.functional.utils_for_test import (
    assert_login,
    login_user,
    login_utub,
    wait_then_click_element,
    wait_then_get_element,
)

pytestmark = pytest.mark.home_ui


def test_logout(browser: WebDriver, create_test_users):
    """
    Tests a user's ability to logout.

    GIVEN a fresh load of the U4I Home page
    WHEN user clicks the upper RHS logout button
    THEN ensure the U4I Splash page is displayed
    """
    login_user(browser)

    # Find submit button to login
    wait_then_click_element(browser, SPL.BUTTON_SUBMIT)

    logout_btn = wait_then_get_element(browser, MPL.BUTTON_LOGOUT)
    logout_btn.click()

    assert EC.staleness_of(logout_btn)

    welcome_text = wait_then_get_element(browser, SPL.WELCOME_TEXT)

    assert welcome_text.text == "Welcome to URLS4IRL"

    navbar = wait_then_get_element(browser, SPL.SPLASH_NAVBAR)

    login_btn = navbar.find_element(By.CSS_SELECTOR, SPL.BUTTON_LOGIN)

    assert login_btn.is_displayed()


def test_refresh_logo(browser: WebDriver, create_test_utubs):
    """
    Tests a user's ability to refresh the U4I Home page by clicking the upper LHS logo.

    GIVEN a fresh load of the U4I Home page, and any item selected
    WHEN user clicks upper LHS logo
    THEN ensure the Home page is re-displayed with nothing selected
    """
    # TODO: test async addition of component by 2nd test user in a shared UTub, then confirm 1st test user can see the update upon refresh

    login_utub(browser)

    # Find submit button to login
    wait_then_click_element(browser, SPL.BUTTON_SUBMIT)

    wait_then_click_element(browser, MPL.U4I_LOGO)

    assert_login(browser)

    active_utubs = wait_then_get_element(browser, MPL.SELECTOR_SELECTED_UTUB)

    assert EC.staleness_of(active_utubs)
