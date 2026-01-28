from flask import Flask
import pytest

from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.support.wait import WebDriverWait

from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS
from tests.functional.assert_utils import (
    assert_not_visible_css_selector,
    assert_visible_css_selector,
)
from tests.functional.db_utils import get_utub_this_user_created
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.login_utils import (
    login_user_and_select_utub_by_utubid,
    login_user_and_visit_preselected_utub,
)
from tests.functional.selenium_utils import (
    add_cookie_banner_cookie,
    wait_for_element_visible,
    wait_then_click_element,
    wait_until_hidden,
)

pytestmark = pytest.mark.home_ui


def test_cookie_banner_visible_on_home_page(
    browser_without_cookie_banner_cookie: WebDriver,
):
    """
    GIVEN a user visiting the home page without a cookie banner cookie
    WHEN the user opens the site
    THEN ensure that the cookie banner is shown
    """
    browser = browser_without_cookie_banner_cookie
    wait_for_element_visible(browser, HPL.COOKIE_BANNER)
    assert_visible_css_selector(browser, HPL.COOKIE_BANNER)


def test_cookie_banner_not_visible_with_cookie(
    browser_without_cookie_banner_cookie: WebDriver,
):
    """
    GIVEN a user visiting the home page with a cookie banner cookie
    WHEN the user opens the site
    THEN ensure that the cookie banner is not shown
    """
    browser = browser_without_cookie_banner_cookie
    add_cookie_banner_cookie(browser)
    assert_not_visible_css_selector(browser, HPL.COOKIE_BANNER)


def test_cookie_banner_hides_on_btn_click(
    browser_without_cookie_banner_cookie: WebDriver,
):
    """
    GIVEN a user visiting the home page without a cookie banner cookie
    WHEN the user opens the site and sees the cookie banner
    THEN ensure that the cookie banner is hidden when they click on the cookie banner button
    """
    browser = browser_without_cookie_banner_cookie
    wait_for_element_visible(browser, HPL.COOKIE_BANNER_BTN)
    wait_then_click_element(browser, HPL.COOKIE_BANNER_BTN)
    wait_until_hidden(browser, HPL.COOKIE_BANNER)
    assert_not_visible_css_selector(browser, HPL.COOKIE_BANNER)


@pytest.mark.parametrize(
    "clickable_elem_selector",
    [
        HPL.SELECTORS_UTUB,
        HPL.BUTTON_UTUB_CREATE,
        HPL.BUTTON_UTUB_DELETE,
        HPL.UTUB_OPEN_SEARCH_ICON,
        HPL.BUTTON_MEMBER_CREATE,
        HPL.BUTTON_UTUB_TAG_CREATE,
        HPL.BUTTON_UPDATE_TAG_BTN_ALL_OPEN,
        HPL.ROWS_URLS,
        HPL.BUTTON_CORNER_URL_CREATE,
    ],
)
def test_cookie_banner_hides_on_clickable_elem_click(
    browser_without_cookie_banner_cookie: WebDriver,
    create_test_tags,
    provide_app: Flask,
    clickable_elem_selector: str,
):
    """
    GIVEN a user visiting the home page without a cookie banner cookie
    WHEN the user opens the site and sees the cookie banner
    THEN ensure that the cookie banner is hidden when they click on any valid clickable element outside the banner
    """
    browser = browser_without_cookie_banner_cookie
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    login_user_and_visit_preselected_utub(
        app, browser, user_id_for_test, utub_user_created.id
    )

    wait_for_element_visible(browser, HPL.COOKIE_BANNER)
    assert_visible_css_selector(browser, HPL.COOKIE_BANNER)

    wait_then_click_element(browser, clickable_elem_selector)
    wait_until_hidden(browser, HPL.COOKIE_BANNER)
    assert_not_visible_css_selector(browser, HPL.COOKIE_BANNER)


def test_cookie_banner_adds_cookie_on_hide(
    browser_without_cookie_banner_cookie: WebDriver,
    create_test_utubs,
    provide_app: Flask,
):
    """
    GIVEN a user visiting the home page without a cookie banner cookie
    WHEN the user opens the site and sees the cookie banner
    THEN ensure that the cookie is added to the browser when the banner is hidden
    """
    browser = browser_without_cookie_banner_cookie
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)

    # Clicking on UTub will hide banner, which should add cookie
    login_user_and_select_utub_by_utubid(
        app, browser, user_id_for_test, utub_user_created.id
    )
    WebDriverWait(browser, 5).until(lambda d: d.get_cookie(UI_TEST_STRINGS.COOKIE_NAME))
    assert_not_visible_css_selector(browser, HPL.COOKIE_BANNER)

    cookie = browser.get_cookie(UI_TEST_STRINGS.COOKIE_NAME)
    assert cookie is not None
    assert cookie["value"] == UI_TEST_STRINGS.COOKIE_VALUE
