import pytest

from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.support.wait import WebDriverWait

from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS
from tests.functional.assert_utils import (
    assert_not_visible_css_selector,
    assert_visible_css_selector,
)
from tests.functional.locators import SplashPageLocators as SPL
from tests.functional.selenium_utils import (
    add_cookie_banner_cookie,
    wait_for_element_visible,
    wait_then_click_element,
    wait_until_hidden,
    wait_until_visible_css_selector,
)

pytestmark = pytest.mark.splash_ui


def test_cookie_banner_visible_on_splash_page(
    browser_without_cookie_banner_cookie: WebDriver,
):
    """
    GIVEN a user visiting the splash page without a cookie banner cookie
    WHEN the user opens the site
    THEN ensure that the cookie banner is shown
    """
    browser = browser_without_cookie_banner_cookie
    wait_for_element_visible(browser, SPL.COOKIE_BANNER)
    assert_visible_css_selector(browser, SPL.COOKIE_BANNER)


def test_cookie_banner_not_visible_with_cookie(
    browser_without_cookie_banner_cookie: WebDriver,
):
    """
    GIVEN a user visiting the splash page with a cookie banner cookie
    WHEN the user opens the site
    THEN ensure that the cookie banner is not shown
    """
    browser = browser_without_cookie_banner_cookie
    add_cookie_banner_cookie(browser)
    assert_not_visible_css_selector(browser, SPL.COOKIE_BANNER)


def test_cookie_banner_hides_on_btn_click(
    browser_without_cookie_banner_cookie: WebDriver,
):
    """
    GIVEN a user visiting the splash page without a cookie banner cookie
    WHEN the user opens the site and sees the cookie banner
    THEN ensure that the cookie banner is hidden when they click on the cookie banner button
    """
    browser = browser_without_cookie_banner_cookie
    wait_for_element_visible(browser, SPL.COOKIE_BANNER_BTN)
    wait_then_click_element(browser, SPL.COOKIE_BANNER_BTN)
    wait_until_hidden(browser, SPL.COOKIE_BANNER)
    assert_not_visible_css_selector(browser, SPL.COOKIE_BANNER)


@pytest.mark.parametrize(
    "clickable_elem_selector",
    [
        SPL.BUTTON_LOGIN,
        SPL.BUTTON_REGISTER,
        SPL.NAVBAR_REGISTER,
        SPL.NAVBAR_LOGIN,
    ],
)
def test_cookie_banner_hides_on_clickable_elem_click(
    browser_without_cookie_banner_cookie: WebDriver,
    clickable_elem_selector: str,
):
    """
    GIVEN a user visiting the splash page without a cookie banner cookie
    WHEN the user opens the site and sees the cookie banner
    THEN ensure that the cookie banner is hidden when they click on any valid clickable element outside the banner
    """
    browser = browser_without_cookie_banner_cookie

    wait_for_element_visible(browser, SPL.COOKIE_BANNER)
    assert_visible_css_selector(browser, SPL.COOKIE_BANNER)

    wait_then_click_element(browser, clickable_elem_selector)
    wait_until_hidden(browser, SPL.COOKIE_BANNER)
    assert_not_visible_css_selector(browser, SPL.COOKIE_BANNER)


def test_cookie_banner_adds_cookie_on_hide(
    browser_without_cookie_banner_cookie: WebDriver,
):
    """
    GIVEN a user visiting the splash page without a cookie banner cookie
    WHEN the user opens the site and sees the cookie banner
    THEN ensure that the cookie is added to the browser when the banner is hidden
    """
    browser = browser_without_cookie_banner_cookie
    wait_until_visible_css_selector(browser, SPL.BUTTON_LOGIN)
    wait_then_click_element(browser, SPL.BUTTON_LOGIN)

    WebDriverWait(browser, 5).until(lambda d: d.get_cookie(UI_TEST_STRINGS.COOKIE_NAME))
    assert_not_visible_css_selector(browser, SPL.COOKIE_BANNER)

    cookie = browser.get_cookie(UI_TEST_STRINGS.COOKIE_NAME)
    assert cookie is not None
    assert cookie["value"] == UI_TEST_STRINGS.COOKIE_VALUE
