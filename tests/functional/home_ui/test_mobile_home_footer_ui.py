from flask import Flask
import pytest
from playwright.sync_api import Page

from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_assert_utils import assert_logged_in_on_mobile
from tests.functional.playwright_utils import (
    click_on_navbar,
    login_user_to_home_page,
    visit_privacy_page,
    visit_terms_page,
    wait_then_click_element,
)

pytestmark = pytest.mark.mobile_ui


def test_privacy_policy(
    page_mobile_portrait: Page, create_test_users, provide_app: Flask
):
    """
    Tests a logged in mobile user's ability to visit the privacy page from the home page.

    GIVEN a fresh load of the U4I Home page
    WHEN user clicks the privacy button in the footer
    THEN ensure the U4I Privacy Policy is displayed
    """
    page = page_mobile_portrait
    app = provide_app
    user_id = 1
    login_user_to_home_page(app=app, page=page, user_id=user_id)

    visit_privacy_page(page=page)


@pytest.mark.parametrize("home_btn_css_selector", [HPL.U4I_LOGO, HPL.BACK_HOME_BTN])
def test_privacy_policy_return_home(
    page_mobile_portrait: Page,
    create_test_users,
    provide_app: Flask,
    home_btn_css_selector: str,
):
    """
    Tests a logged in mobile user's ability to visit the privacy page and then return to home page.

    GIVEN a fresh load of the U4I Home page
    WHEN user clicks the privacy button in the footer and then tries to go home via the buttons
    THEN ensure the home page is displayed
    """
    page = page_mobile_portrait
    app = provide_app
    user_id = 1
    login_user_to_home_page(app=app, page=page, user_id=user_id)

    visit_privacy_page(page=page)
    if home_btn_css_selector == HPL.BACK_HOME_BTN:
        click_on_navbar(page=page)
    wait_then_click_element(page=page, css_selector=home_btn_css_selector)
    assert_logged_in_on_mobile(page=page)


def test_terms_page(
    page_mobile_portrait: Page,
    create_test_users,
    provide_app: Flask,
):
    """
    Tests a mobile logged in user's ability to visit the terms page from the home page.

    GIVEN a fresh load of the U4I Home page
    WHEN user clicks the terms button in the footer
    THEN ensure the U4I Terms & Conditions are displayed
    """
    page = page_mobile_portrait
    app = provide_app
    user_id = 1
    login_user_to_home_page(app=app, page=page, user_id=user_id)

    visit_terms_page(page=page)


@pytest.mark.parametrize("home_btn_css_selector", [HPL.U4I_LOGO, HPL.BACK_HOME_BTN])
def test_terms_return_home(
    page_mobile_portrait: Page,
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
    page = page_mobile_portrait
    app = provide_app
    user_id = 1
    login_user_to_home_page(app=app, page=page, user_id=user_id)

    visit_terms_page(page=page)
    if home_btn_css_selector == HPL.BACK_HOME_BTN:
        click_on_navbar(page=page)
    wait_then_click_element(page=page, css_selector=home_btn_css_selector)
    assert_logged_in_on_mobile(page=page)
