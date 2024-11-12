# Standard library
from time import sleep

# External libraries
import pytest
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver

# Internal libraries
from src.mocks.mock_constants import MOCK_UTUB_DESCRIPTION
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.utils_for_test import (
    login_user,
    wait_then_click_element,
    wait_then_get_element,
    wait_then_get_elements,
    wait_until_hidden,
)
from tests.functional.locators import MainPageLocators as MPL
from utils_for_test_utub_ui import assert_create_utub, create_utub


def test_open_create_utub_input(browser: WebDriver, create_test_users):
    """
    Tests a user's ability to open the createUTub input using the plus button.

    GIVEN a fresh load of the U4I Home page
    WHEN user clicks the UTub module plus button
    THEN ensure the createUTub input opens
    """
    login_user(browser)

    # Click createUTub button to show input
    wait_then_click_element(browser, MPL.BUTTON_UTUB_CREATE)

    create_utub_name_input = wait_then_get_element(browser, MPL.INPUT_UTUB_NAME_CREATE)

    assert create_utub_name_input.is_displayed()
    assert wait_then_get_element(
        browser, MPL.INPUT_UTUB_DESCRIPTION_CREATE
    ).is_displayed()

    assert create_utub_name_input == browser.switch_to.active_element


def test_close_create_utub_input_btn(browser: WebDriver, create_test_users):
    """
    Tests a user's ability to close the createUTub input by clicking the 'x' button

    GIVEN a fresh load of the U4I Home page
    WHEN user opens the createUTub input, then clicks the 'x'
    THEN ensure the createUTub input is closed
    """
    login_user(browser)

    # Click createUTub button to show input
    wait_then_click_element(browser, MPL.BUTTON_UTUB_CREATE)

    wait_then_click_element(browser, MPL.BUTTON_UTUB_CANCEL_CREATE)

    create_utub_name_input = wait_until_hidden(browser, MPL.INPUT_UTUB_NAME_CREATE, 5)

    assert not create_utub_name_input.is_displayed()


def test_close_create_utub_input_key(browser: WebDriver, create_test_users):
    """
    Tests a user's ability to close the createUTub input by pressing the Escape key

    GIVEN a fresh load of the U4I Home page
    WHEN user opens the createUTub input, then presses 'Esc'
    THEN ensure the createUTub input is closed
    """
    login_user(browser)

    # Click createUTub button to show input
    wait_then_click_element(browser, MPL.BUTTON_UTUB_CREATE)

    browser.switch_to.active_element.send_keys(Keys.ESCAPE)

    create_utub_name_input = wait_until_hidden(browser, MPL.INPUT_UTUB_NAME_CREATE, 5)

    assert not create_utub_name_input.is_displayed()


# @pytest.mark.skip(reason="Testing another in isolation")
def test_create_utub_btn(browser: WebDriver, create_test_users):
    """
    Tests a user's ability to create a UTub

    GIVEN a user
    WHEN the createUTub form is populated and submitted by the 'check' button
    THEN ensure the new UTub is successfully added to the user's UTub Deck and is selected.
    """

    login_user(browser)

    utub_name = UTS.TEST_UTUB_NAME_1

    create_utub(browser, utub_name, MOCK_UTUB_DESCRIPTION)

    # Submits new UTub
    wait_then_click_element(browser, MPL.BUTTON_UTUB_SUBMIT_CREATE)

    # Wait for POST request
    sleep(4)

    assert_create_utub(browser, utub_name)


def test_create_utub_key(browser: WebDriver, create_test_users):
    """
    Tests a user's ability to create a UTub

    GIVEN a user
    WHEN the createUTub form is populated and submitted by pressing the 'Enter' key
    THEN ensure the new UTub is successfully added to the user's UTub Deck and is selected.
    """

    login_user(browser)

    utub_name = UTS.TEST_UTUB_NAME_1

    create_utub(browser, utub_name, MOCK_UTUB_DESCRIPTION)

    browser.switch_to.active_element.send_keys(Keys.ENTER)

    # Wait for POST request
    sleep(4)

    assert_create_utub(browser, utub_name)


@pytest.mark.skip(
    reason="Not on happy path. This test tests functionality that is not yet captured on the frontend"
)
def test_create_utub_name_length_exceeded(browser: WebDriver, create_test_users):
    """
    Tests the site error response to a user's attempt to create a new UTub with a name that exceeds the maximum character length limit.

    GIVEN a user
    WHEN the createUTub form is populated and submitted with a name that exceeds character limits
    THEN ensure the appropriate error and prompt is shown to user.
    """

    login_user(browser)

    create_utub(browser, UTS.MAX_CHAR_LIM_UTUB_NAME)

    warning_modal_body = wait_then_get_element(browser, MPL.BODY_MODAL)

    # Assert new UTub is now active and displayed to user
    assert warning_modal_body.text == "Try shortening your UTub name"


# @pytest.mark.skip(reason="Testing another in isolation")
def test_create_utub_name_similar(browser: WebDriver, create_test_utubs):
    """
    Tests the site warning response to a user's attempt to create a new UTub with a name that is similar to one already in their UTub Deck.

    GIVEN a user
    WHEN the createUTub form is populated and submitted with a name that is similar to one already in their UTub Deck
    THEN ensure the appropriate warning and prompt for confirmation is shown to user.
    """

    login_user(browser)

    # Extract name of a pre-existing UTub
    UTub_selectors = wait_then_get_elements(browser, MPL.SELECTORS_UTUB)
    first_UTub_selector = UTub_selectors[0]
    utub_name = first_UTub_selector.text

    # Attempt to add a new UTub with the same name
    create_utub(browser, utub_name, MOCK_UTUB_DESCRIPTION)
    # Submits new UTub
    wait_then_click_element(browser, MPL.BUTTON_UTUB_SUBMIT_CREATE)

    # Extract modal body element
    confirmation_modal_body = wait_then_get_element(browser, MPL.BODY_MODAL)
    confirmation_modal_body_text = confirmation_modal_body.get_attribute("innerText")
    utub_same_name_check_text = UTS.BODY_MODAL_UTUB_CREATE_SAME_NAME

    # Assert modal prompts user to consider duplicate UTub naming
    assert confirmation_modal_body_text == utub_same_name_check_text
