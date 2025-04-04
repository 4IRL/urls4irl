from flask import Flask
from selenium.webdriver.remote.webdriver import WebDriver
from src.cli.mock_constants import MOCK_UTUB_DESCRIPTION
from src.models.utubs import Utubs
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.utils_for_test import (
    Decks,
    click_on_navbar,
    get_utub_this_user_created,
    login_user_and_select_utub_by_utubid_mobile,
    login_user_to_home_page,
    select_utub_by_id_mobile,
    verify_panel_visibility_mobile,
    wait_then_click_element,
    wait_until_hidden,
)
from tests.functional.utubs_ui.utils_for_test_utub_ui import create_utub


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

    verify_panel_visibility_mobile(browser=browser, visible_deck=Decks.URLS)


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
    verify_panel_visibility_mobile(browser=browser, visible_deck=Decks.URLS)

    # Travel back
    click_on_navbar(browser)

    wait_then_click_element(browser, HPL.NAVBAR_UTUB_DECK, time=10)
    verify_panel_visibility_mobile(browser=browser, visible_deck=Decks.UTUBS)

    select_utub_by_id_mobile(browser, utub.id)
    verify_panel_visibility_mobile(browser=browser, visible_deck=Decks.URLS)
