from flask import Flask
import pytest
from selenium.webdriver.remote.webdriver import WebDriver

from tests.functional.assert_utils import (
    assert_login,
    assert_on_429_page,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.login_utils import (
    create_user_session_and_provide_session_id,
    login_user_with_cookie_from_session,
)
from tests.functional.selenium_utils import (
    modify_navigational_link_for_rate_limit,
    visit_privacy_page,
    visit_terms_page,
    wait_then_click_element,
)

pytestmark = pytest.mark.home_ui


def test_privacy_policy(browser: WebDriver, create_test_users, provide_app: Flask):
    """
    Tests a logged in user's ability to visit the privacy page from the home page.

    GIVEN a fresh load of the U4I Home page
    WHEN user clicks the privacy button in the footer
    THEN ensure the U4I Privacy Policy is displayed
    """
    app = provide_app
    user_id = 1
    session_id = create_user_session_and_provide_session_id(app, user_id)
    login_user_with_cookie_from_session(browser, session_id)

    visit_privacy_page(browser)


def test_privacy_policy_rate_limits(
    browser: WebDriver, create_test_users, provide_app: Flask
):
    """
    Tests a logged in user's ability to visit the privacy page from the home page but they are rate limited.

    GIVEN a fresh load of the U4I Home page and the user is rate limited.
    WHEN user clicks the privacy button in the footer
    THEN ensure the 429 error page is shown
    """
    app = provide_app
    user_id = 1
    session_id = create_user_session_and_provide_session_id(app, user_id)
    login_user_with_cookie_from_session(browser, session_id)

    modify_navigational_link_for_rate_limit(browser, HPL.PRIVACY_BTN.lstrip("#"))
    wait_then_click_element(browser, HPL.PRIVACY_BTN, time=3)
    assert_on_429_page(browser)


@pytest.mark.parametrize("home_btn_css_selector", [HPL.U4I_LOGO, HPL.BACK_HOME_BTN])
def test_privacy_policy_return_home(
    browser: WebDriver,
    create_test_users,
    provide_app: Flask,
    home_btn_css_selector: str,
):
    """
    Tests a logged in user's ability to visit the privacy page and then return to home page.

    GIVEN a fresh load of the U4I Home page
    WHEN user clicks the privacy button in the footer and then tries to go home via the buttons
    THEN ensure the home page is displayed
    """
    app = provide_app
    user_id = 1
    session_id = create_user_session_and_provide_session_id(app, user_id)
    login_user_with_cookie_from_session(browser, session_id)

    visit_privacy_page(browser)
    wait_then_click_element(browser, home_btn_css_selector, time=3)
    assert_login(browser)


def test_terms_page(browser: WebDriver, create_test_users, provide_app: Flask):
    """
    Tests a logged in user's ability to visit the terms page from the home page.

    GIVEN a fresh load of the U4I Home page
    WHEN user clicks the terms button in the footer
    THEN ensure the U4I Terms & Conditions are displayed
    """
    app = provide_app
    user_id = 1
    session_id = create_user_session_and_provide_session_id(app, user_id)
    login_user_with_cookie_from_session(browser, session_id)

    visit_terms_page(browser)


def test_terms_page_rate_limits(
    browser: WebDriver, create_test_users, provide_app: Flask
):
    """
    Tests a logged in user's ability to visit the terms page from the home page and is rate limited.

    GIVEN a fresh load of the U4I Home page and user is rate limited
    WHEN user clicks the terms button in the footer
    THEN ensure the 429 error page is shown
    """
    app = provide_app
    user_id = 1
    session_id = create_user_session_and_provide_session_id(app, user_id)
    login_user_with_cookie_from_session(browser, session_id)

    modify_navigational_link_for_rate_limit(browser, HPL.TERMS_BTN.lstrip("#"))
    wait_then_click_element(browser, HPL.TERMS_BTN)
    assert_on_429_page(browser)


@pytest.mark.parametrize("home_btn_css_selector", [HPL.U4I_LOGO, HPL.BACK_HOME_BTN])
def test_terms_return_home(
    browser: WebDriver,
    create_test_users,
    provide_app: Flask,
    home_btn_css_selector: str,
):
    """
    Tests a logged in user's ability to visit the terms page and then return to home page.

    GIVEN a fresh load of the U4I Home page
    WHEN user clicks the terms button in the footer and then tries to go home via the buttons
    THEN ensure the home page is displayed
    """
    app = provide_app
    user_id = 1
    session_id = create_user_session_and_provide_session_id(app, user_id)
    login_user_with_cookie_from_session(browser, session_id)

    visit_terms_page(browser)
    wait_then_click_element(browser, home_btn_css_selector, time=3)
    assert_login(browser)
