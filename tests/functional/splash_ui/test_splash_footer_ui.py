import pytest
from selenium.webdriver.remote.webdriver import WebDriver

from tests.functional.assert_utils import (
    assert_visible_css_selector,
)
from tests.functional.locators import SplashPageLocators as SPL
from tests.functional.selenium_utils import (
    visit_privacy_page,
    visit_terms_page,
    wait_then_click_element,
)

pytestmark = pytest.mark.splash_ui


def test_privacy_policy(browser: WebDriver):
    """
    Tests a non-logged in user's ability to visit the privacy page from the home page.

    GIVEN a fresh load of the U4I Home page
    WHEN user clicks the privacy button in the footer
    THEN ensure the U4I Privacy Policy is displayed
    """
    visit_privacy_page(browser)


@pytest.mark.parametrize("splash_btn_css_selector", [SPL.U4I_LOGO, SPL.BACK_SPLASH_BTN])
def test_privacy_policy_return_home(browser: WebDriver, splash_btn_css_selector: str):
    """
    Tests a non-logged in user's ability to visit the privacy page and then return to home page.

    GIVEN a fresh load of the U4I Home page
    WHEN user clicks the privacy button in the footer and then tries to go home via the buttons
    THEN ensure the home page is displayed
    """
    visit_privacy_page(browser)
    wait_then_click_element(browser, splash_btn_css_selector, time=3)
    assert_visible_css_selector(browser, SPL.WELCOME_TEXT)


def test_terms_page(browser: WebDriver):
    """
    Tests a non-logged in user's ability to visit the terms page from the home page.

    GIVEN a fresh load of the U4I Home page
    WHEN user clicks the terms button in the footer
    THEN ensure the U4I Terms & Conditions are displayed
    """
    visit_terms_page(browser)


@pytest.mark.parametrize("splash_btn_css_selector", [SPL.U4I_LOGO, SPL.BACK_SPLASH_BTN])
def test_terms_return_home(browser: WebDriver, splash_btn_css_selector: str):
    """
    Tests a non-logged in user's ability to visit the terms page and then return to home page.

    GIVEN a fresh load of the U4I Home page
    WHEN user clicks the terms button in the footer and then tries to go home via the buttons
    THEN ensure the home page is displayed
    """
    visit_terms_page(browser)
    wait_then_click_element(browser, splash_btn_css_selector, time=3)
    assert_visible_css_selector(browser, SPL.WELCOME_TEXT)
