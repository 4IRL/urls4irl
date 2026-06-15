import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

from tests.functional.assert_utils import (
    assert_on_429_page,
    assert_visible_css_selector,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.locators import SplashPageLocators as SPL
from tests.functional.selenium_utils import (
    modify_navigational_link_for_rate_limit,
    scroll_footer_link_into_view,
    visit_contact_us_page,
    visit_privacy_page,
    visit_terms_page,
    wait_then_click_element,
)

pytestmark = pytest.mark.splash_ui


def test_privacy_policy(browser: WebDriver):
    """
    Tests a non-logged in user's ability to visit the privacy page from the splash page.

    GIVEN a fresh load of the U4I Splash page
    WHEN user clicks the privacy button in the footer
    THEN ensure the U4I Privacy Policy is displayed
    """
    visit_privacy_page(browser)


def test_privacy_policy_rate_limits(browser: WebDriver):
    """
    Tests a non-logged in user's ability to visit the privacy page from the splash page, but they are rate limited.

    GIVEN a fresh load of the U4I Splash page
    WHEN user clicks the privacy button in the footer
    THEN ensure the rate limited error page is shown
    """
    modify_navigational_link_for_rate_limit(browser, HPL.PRIVACY_BTN.lstrip("#"))
    scroll_footer_link_into_view(browser, HPL.PRIVACY_BTN)
    wait_then_click_element(browser, HPL.PRIVACY_BTN)
    assert_on_429_page(browser)


@pytest.mark.parametrize("splash_btn_css_selector", [SPL.U4I_LOGO, SPL.BACK_SPLASH_BTN])
def test_privacy_policy_return_splash(browser: WebDriver, splash_btn_css_selector: str):
    """
    Tests a non-logged in user's ability to visit the privacy page and then return to splash page.

    GIVEN a fresh load of the U4I Splash page
    WHEN user clicks the privacy button in the footer and then tries to go splash via the buttons
    THEN ensure the splash page is displayed
    """
    visit_privacy_page(browser)
    wait_then_click_element(browser, splash_btn_css_selector, time=3)
    assert_visible_css_selector(browser, SPL.WELCOME_TEXT)


def test_terms_page(browser: WebDriver):
    """
    Tests a non-logged in user's ability to visit the terms page from the splash page.

    GIVEN a fresh load of the U4I Splash page
    WHEN user clicks the terms button in the footer
    THEN ensure the U4I Terms & Conditions are displayed
    """
    visit_terms_page(browser)


def test_terms_page_rate_limits(browser: WebDriver):
    """
    Tests a non-logged in user's ability to visit the terms page from the splash page but they are rate limited.

    GIVEN a fresh load of the U4I Splash page
    WHEN user clicks the terms button in the footer
    THEN ensure the 429 error page is shown
    """
    modify_navigational_link_for_rate_limit(browser, HPL.TERMS_BTN.lstrip("#"))
    scroll_footer_link_into_view(browser, HPL.TERMS_BTN)
    wait_then_click_element(browser, HPL.TERMS_BTN)
    assert_on_429_page(browser)


@pytest.mark.parametrize("splash_btn_css_selector", [SPL.U4I_LOGO, SPL.BACK_SPLASH_BTN])
def test_terms_return_splash(browser: WebDriver, splash_btn_css_selector: str):
    """
    Tests a non-logged in user's ability to visit the terms page and then return to splash page.

    GIVEN a fresh load of the U4I Splash page
    WHEN user clicks the terms button in the footer and then tries to go splash via the buttons
    THEN ensure the splash page is displayed
    """
    visit_terms_page(browser)
    wait_then_click_element(browser, splash_btn_css_selector, time=3)
    assert_visible_css_selector(browser, SPL.WELCOME_TEXT)


def test_visit_contact_page(browser: WebDriver):
    """
    GIVEN a fresh load of the U4I splash page
    WHEN user clicks on the Contact Us button in the footer
    THEN ensure the Contact Us page is shown
    """
    visit_contact_us_page(browser)


@pytest.mark.parametrize("splash_btn_css_selector", [SPL.U4I_LOGO, SPL.BACK_SPLASH_BTN])
def test_visit_contact_page_return_splash(
    browser: WebDriver, splash_btn_css_selector: str
):
    """
    GIVEN a fresh load of the U4I Contact Us Page
    WHEN user clicks on the return to Splash buttons
    THEN ensure the Splash page is shown
    """
    visit_contact_us_page(browser)
    wait_then_click_element(browser, splash_btn_css_selector, time=3)
    assert_visible_css_selector(browser, SPL.WELCOME_TEXT)


EXPECTED_TEXTAREA_MIN_HEIGHT_PX = "320px"

NARROW_VIEWPORT_WIDTH_PX = 380
NARROW_VIEWPORT_HEIGHT_PX = 812
EXPECTED_PRIVACY_BTN_COLOR_AT_380PX = "rgb(255, 255, 255)"


def test_privacy_btn_color_passes_wcag_at_380px(browser: WebDriver):
    """
    GIVEN a fresh load of the U4I Splash page at a 380px-wide viewport
    WHEN the footer renders
    THEN ensure the #PrivacyBtn link color is white (--UTubDescriptionColor),
        confirming the narrow-viewport contrast rule lands and was not overridden
    """
    browser.set_window_size(NARROW_VIEWPORT_WIDTH_PX, NARROW_VIEWPORT_HEIGHT_PX)
    browser.refresh()
    scroll_footer_link_into_view(browser, HPL.PRIVACY_BTN)
    privacy_btn_color = browser.execute_script(
        "return getComputedStyle(document.getElementById('PrivacyBtn')).color"
    )
    assert privacy_btn_color == EXPECTED_PRIVACY_BTN_COLOR_AT_380PX


def test_contact_textarea_min_height(browser: WebDriver):
    """
    GIVEN a fresh load of the U4I Contact Us page
    WHEN user views the contact form
    THEN ensure the textarea#content element has min-height: 20rem (320px) applied
    """
    visit_contact_us_page(browser)
    textarea = browser.find_element(By.CSS_SELECTOR, HPL.CONTACT_CONTENT_INPUT)
    min_height = textarea.value_of_css_property("min-height")
    assert min_height == EXPECTED_TEXTAREA_MIN_HEIGHT_PX
