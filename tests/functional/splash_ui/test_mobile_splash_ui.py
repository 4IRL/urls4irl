from flask import Flask
import pytest
from selenium.webdriver.remote.webdriver import WebDriver

from src.models.users import Users
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.locators import SplashPageLocators as SPL
from tests.functional.utils_for_test import (
    Decks,
    assert_not_visible_css_selector,
    assert_visible_css_selector,
    click_on_navbar,
    input_login_fields,
    verify_panel_visibility_mobile,
    wait_then_click_element,
)

pytestmark = pytest.mark.mobile_ui


def test_splash_page_ui_shows(browser_mobile_portrait: WebDriver):
    """
    Tests that the main buttons are visible on the splash page in mobile.

    GIVEN a fresh load of the U4I Splash page on mobile
    WHEN user views the web page
    THEN ensure the login, register, and navbar toggler buttons are visible
    """
    browser = browser_mobile_portrait
    assert_visible_css_selector(browser, SPL.BUTTON_REGISTER)
    assert_visible_css_selector(browser, SPL.BUTTON_LOGIN)
    assert_visible_css_selector(browser, SPL.NAVBAR_TOGGLER)


def test_navbar_on_mobile_splash_shows_login_register(
    browser_mobile_portrait: WebDriver,
):
    """
    Tests that the login and register buttons are visible in the navbar on mobile.

    GIVEN a fresh load of the U4I Splash page on mobile
    WHEN user clicks on navbar toggler
    THEN ensure the login and register buttons are shown
    """
    browser = browser_mobile_portrait

    click_on_navbar(browser)

    assert_visible_css_selector(browser, SPL.NAVBAR_LOGIN)
    assert_visible_css_selector(browser, SPL.NAVBAR_REGISTER)


def test_navbar_on_mobile_splash_hides_login_register(
    browser_mobile_portrait: WebDriver,
):
    """
    Tests that the login and register buttons are visible in the navbar on mobile.

    GIVEN a fresh load of the U4I Splash page on mobile
    WHEN user clicks on navbar toggler and then clicks to hide it
    THEN ensure the login and register buttons are no longer shown
    """
    browser = browser_mobile_portrait

    click_on_navbar(browser)

    click_on_navbar(browser)

    assert_not_visible_css_selector(browser, SPL.NAVBAR_LOGIN)
    assert_not_visible_css_selector(browser, SPL.NAVBAR_REGISTER)


def test_mobile_email_validation_brings_user_to_utub_panel(
    browser_mobile_portrait: WebDriver,
    create_user_unconfirmed_email,
    provide_app: Flask,
):
    """
    Tests that email validation on modal brings user to proper panel

    GIVEN a user validating their email after registration
    WHEN user clicks link in the email for email validation
    THEN ensure the UTub panel is shown on mobile
    """
    browser = browser_mobile_portrait

    app = provide_app
    validation_url_suffix = create_user_unconfirmed_email
    validation_url = browser.current_url + validation_url_suffix

    browser.get(validation_url)
    verify_panel_visibility_mobile(browser=browser, visible_deck=Decks.UTUBS)

    with app.app_context():
        user: Users = Users.query.filter(Users.username == UTS.TEST_USERNAME_1).first()
        assert user.is_email_authenticated()


def test_mobile_login_brings_user_to_utub_panel(
    browser_mobile_portrait: WebDriver,
    create_test_users,
):
    """
    Tests that email validation on modal brings user to proper panel

    GIVEN a user validating their email after registration
    WHEN user clicks link in the email for email validation
    THEN ensure the UTub panel is shown on mobile
    """
    browser = browser_mobile_portrait

    click_on_navbar(browser)

    wait_then_click_element(browser, SPL.NAVBAR_LOGIN)
    input_login_fields(browser)

    wait_then_click_element(browser, SPL.BUTTON_SUBMIT)

    verify_panel_visibility_mobile(browser=browser, visible_deck=Decks.UTUBS)
