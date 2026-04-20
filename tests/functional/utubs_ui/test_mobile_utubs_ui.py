from flask import Flask
import pytest
from selenium.webdriver.remote.webdriver import WebDriver
from backend.cli.mock_constants import MOCK_UTUB_DESCRIPTION
from backend.models.utubs import Utubs
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.assert_utils import (
    assert_not_visible_css_selector,
    assert_panel_visibility_mobile,
    assert_visible_css_selector,
)
from tests.functional.db_utils import get_utub_this_user_created
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.login_utils import (
    login_user_and_select_utub_by_utubid_mobile,
    login_user_to_home_page,
)
from tests.functional.selenium_utils import (
    Decks,
    click_on_navbar,
    select_utub_by_id_mobile,
    wait_then_click_element,
    wait_until_hidden,
    wait_until_visible_css_selector,
)
from tests.functional.utubs_ui.selenium_utils import (
    create_utub,
    open_update_utub_desc_input,
)

pytestmark = pytest.mark.mobile_ui


def test_create_utub_shows_url_deck_mobile(
    browser_mobile_portrait: WebDriver, create_test_users, provide_app: Flask
):
    """
    Tests a user's ability to create a UTub on mobile

    GIVEN a user attempting to make a UTub
    WHEN the createUTub form is populated and submitted by the 'check' button on mobile
    THEN ensure the user is taken to the URL deck upon successful creation
    """
    browser = browser_mobile_portrait
    app = provide_app
    USER_ID = 1
    login_user_to_home_page(app, browser, USER_ID)

    utub_name = UTS.TEST_UTUB_NAME_1

    create_utub(browser, utub_name, MOCK_UTUB_DESCRIPTION)

    # Submits new UTub
    wait_then_click_element(browser, HPL.BUTTON_UTUB_SUBMIT_CREATE)

    # Wait for POST request
    wait_until_hidden(browser, HPL.INPUT_UTUB_NAME_CREATE, timeout=3)

    assert_panel_visibility_mobile(browser=browser, visible_deck=Decks.URLS)


def test_tap_on_already_selected_utub_shows_url_deck_mobile(
    browser_mobile_portrait: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    Tests a user's ability to re-select a UTub on mobile

    GIVEN a user attempting to re-select a UTub
    WHEN the UTub is already selected and the user taps on it
    THEN ensure the user is taken to the URL deck
    """
    browser = browser_mobile_portrait
    app = provide_app
    USER_ID = 1
    utub: Utubs = get_utub_this_user_created(app, USER_ID)
    login_user_and_select_utub_by_utubid_mobile(
        app=app, browser=browser, utub_id=utub.id, user_id=USER_ID
    )
    assert_panel_visibility_mobile(browser=browser, visible_deck=Decks.URLS)

    # Travel back
    click_on_navbar(browser)

    wait_then_click_element(browser, HPL.NAVBAR_UTUB_DECK, time=10)
    assert_panel_visibility_mobile(browser=browser, visible_deck=Decks.UTUBS)

    select_utub_by_id_mobile(browser, utub.id)
    assert_panel_visibility_mobile(browser=browser, visible_deck=Decks.URLS)


def test_open_update_utub_description_hides_add_url_btn_and_search_mobile(
    browser_mobile_portrait: WebDriver, create_test_urls, provide_app: Flask
):
    """
    GIVEN a user owns a UTub with URLs on mobile (search icon visible)
    WHEN the user opens the description edit input
    THEN the Add URL button and search icon are hidden, and restored on cancel
    """
    browser = browser_mobile_portrait
    app = provide_app
    user_id = 1
    utub: Utubs = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_utubid_mobile(
        app=app, browser=browser, utub_id=utub.id, user_id=user_id
    )
    assert_panel_visibility_mobile(browser=browser, visible_deck=Decks.URLS)
    wait_until_visible_css_selector(browser, HPL.BUTTON_CORNER_URL_CREATE, timeout=3)
    wait_until_visible_css_selector(browser, HPL.URL_OPEN_SEARCH_ICON, timeout=3)

    open_update_utub_desc_input(browser)

    assert_not_visible_css_selector(browser, HPL.BUTTON_CORNER_URL_CREATE)
    assert_not_visible_css_selector(browser, HPL.URL_OPEN_SEARCH_ICON)

    wait_then_click_element(browser, HPL.BUTTON_UTUB_DESCRIPTION_CANCEL_UPDATE)

    wait_until_visible_css_selector(browser, HPL.BUTTON_CORNER_URL_CREATE, timeout=3)
    assert_visible_css_selector(browser, HPL.BUTTON_CORNER_URL_CREATE)
    wait_until_visible_css_selector(browser, HPL.URL_OPEN_SEARCH_ICON, timeout=3)
    assert_visible_css_selector(browser, HPL.URL_OPEN_SEARCH_ICON)
