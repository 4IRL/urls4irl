from __future__ import annotations

from flask import Flask
import pytest
from playwright.sync_api import Page

from backend.models.users import Users
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.locators import SplashPageLocators as SPL
from tests.functional.playwright_assert_utils import (
    assert_not_visible_css_selector,
    assert_panel_visibility_mobile,
    assert_visible_css_selector,
)
from tests.functional.playwright_utils import (
    Decks,
    PageBundle,
    click_on_navbar,
    current_base_url,
    input_login_fields,
    wait_for_class_to_be_removed,
    wait_for_element_visible,
    wait_then_click_element,
)

pytestmark = pytest.mark.mobile_ui


def test_splash_page_ui_shows(page_mobile_portrait: Page):
    """
    Tests that the main buttons are visible on the splash page in mobile.

    GIVEN a fresh load of the U4I Splash page on mobile
    WHEN user views the web page
    THEN ensure the login, register, and navbar toggler buttons are visible
    """
    assert_visible_css_selector(
        page=page_mobile_portrait, css_selector=SPL.BUTTON_REGISTER
    )
    assert_visible_css_selector(
        page=page_mobile_portrait, css_selector=SPL.BUTTON_LOGIN
    )
    assert_visible_css_selector(
        page=page_mobile_portrait, css_selector=SPL.NAVBAR_TOGGLER
    )


def test_navbar_on_mobile_splash_shows_login_register(
    page_mobile_portrait: Page,
):
    """
    Tests that the login and register buttons are visible in the navbar on mobile.

    GIVEN a fresh load of the U4I Splash page on mobile
    WHEN user clicks on navbar toggler
    THEN ensure the login and register buttons are shown
    """
    click_on_navbar(page=page_mobile_portrait)

    assert_visible_css_selector(
        page=page_mobile_portrait, css_selector=SPL.NAVBAR_LOGIN
    )
    assert_visible_css_selector(
        page=page_mobile_portrait, css_selector=SPL.NAVBAR_REGISTER
    )


def test_navbar_on_mobile_splash_hides_login_register(
    page_mobile_portrait: Page,
):
    """
    Tests that the login and register buttons are visible in the navbar on mobile.

    GIVEN a fresh load of the U4I Splash page on mobile
    WHEN user clicks on navbar toggler and then clicks to hide it
    THEN ensure the login and register buttons are no longer shown
    """
    click_on_navbar(page=page_mobile_portrait)

    click_on_navbar(page=page_mobile_portrait)

    assert_not_visible_css_selector(
        page=page_mobile_portrait, css_selector=SPL.NAVBAR_LOGIN
    )
    assert_not_visible_css_selector(
        page=page_mobile_portrait, css_selector=SPL.NAVBAR_REGISTER
    )


def test_mobile_email_validation_brings_user_to_utub_panel(
    page_mobile_portrait: Page,
    create_user_unconfirmed_email,
    provide_app: Flask,
):
    """
    Tests that email validation on modal brings user to proper panel

    GIVEN a user validating their email after registration
    WHEN user clicks link in the email for email validation
    THEN ensure the UTub panel is shown on mobile
    """
    app = provide_app
    validation_url_suffix = create_user_unconfirmed_email
    validation_url = current_base_url(page=page_mobile_portrait) + validation_url_suffix

    page_mobile_portrait.goto(validation_url)
    assert_panel_visibility_mobile(page=page_mobile_portrait, visible_deck=Decks.UTUBS)

    with app.app_context():
        user: Users = Users.query.filter(Users.username == UTS.TEST_USERNAME_1).first()
        assert user.email_validated


def test_mobile_login_brings_user_to_utub_panel(
    page_mobile_portrait: Page,
    create_test_users,
):
    """
    Tests that email validation on modal brings user to proper panel

    GIVEN a user validating their email after registration
    WHEN user clicks link in the email for email validation
    THEN ensure the UTub panel is shown on mobile
    """
    click_on_navbar(page=page_mobile_portrait)

    wait_then_click_element(page=page_mobile_portrait, css_selector=SPL.NAVBAR_LOGIN)
    input_login_fields(page=page_mobile_portrait)

    wait_then_click_element(
        page=page_mobile_portrait, css_selector=SPL.LOGIN_BUTTON_SUBMIT
    )

    assert_panel_visibility_mobile(page=page_mobile_portrait, visible_deck=Decks.UTUBS)


def test_mobile_navbar_press_hides_cookie_banner(
    page_mobile_portrait_without_cookie_banner_cookie: PageBundle,
):
    """
    GIVEN a user visiting the splash page without a cookie banner cookie
    WHEN the user opens the site and sees the cookie banner
    THEN ensure that the cookie banner is hidden when they click on the mobile navbar
    """
    page = page_mobile_portrait_without_cookie_banner_cookie.page

    wait_for_element_visible(page=page, css_selector=SPL.COOKIE_BANNER)
    assert_visible_css_selector(page=page, css_selector=SPL.COOKIE_BANNER)

    wait_then_click_element(page=page, css_selector=SPL.NAVBAR_TOGGLER)
    # The banner hides via opacity transition (opacity:0) rather than
    # display:none, so check the is-visible class was removed.
    wait_for_class_to_be_removed(
        page=page, css_selector=SPL.COOKIE_BANNER, class_name="is-visible"
    )
    assert page.locator(f"{SPL.COOKIE_BANNER}.is-visible").count() == 0
