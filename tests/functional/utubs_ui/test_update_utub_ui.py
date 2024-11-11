# Standard library
from time import sleep

# External libraries
import pytest
from selenium.webdriver.remote.webdriver import WebDriver

# Internal libraries
from locators import MainPageLocators as MPL
from src.mocks.mock_constants import MOCK_UTUB_NAME_BASE, MOCK_UTUB_DESCRIPTION
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.utils_for_test import (
    get_all_utub_selector_names,
    get_selected_utub_decsription,
    get_selected_utub_name,
    login_utub,
    wait_then_click_element,
    wait_then_get_element,
)
from tests.functional.utubs_ui.utils_for_test_utub_ui import (
    update_utub_name,
    update_utub_description,
)


def test_open_update_utub_name_input(browser: WebDriver, create_test_utubs):
    """
    Tests a user's ability to open the updateUTubName input using the plus button.

    GIVEN a fresh load of the U4I Home page
    WHEN user clicks the UTub module plus button
    THEN ensure the createUTub input opens
    """
    login_utub(browser)

    # Click createUTub button to show input
    wait_then_click_element(browser, MPL.BUTTON_UTUB_CREATE)

    create_utub_name_input = wait_then_get_element(browser, MPL.INPUT_UTUB_NAME_CREATE)

    assert create_utub_name_input.is_displayed()
    assert wait_then_get_element(
        browser, MPL.INPUT_UTUB_DESCRIPTION_CREATE
    ).is_displayed()

    assert create_utub_name_input == browser.switch_to.active_element


# @pytest.mark.skip(reason="Testing another in isolation")
def test_update_utub_name(browser: WebDriver, create_test_utubs):
    """
    Tests a UTub owner's ability to update a selected UTub's name.

    GIVEN a user owns a UTub
    WHEN they submit the editUTub form
    THEN ensure the form is hidden, the UTub selector name and URL deck header are updated.
    """

    login_utub(browser)

    new_utub_name = MOCK_UTUB_NAME_BASE + "2"

    update_utub_name(browser, new_utub_name)

    # Wait for POST request
    sleep(4)

    url_deck_header = get_selected_utub_name(browser)

    # Assert new UTub name is updated in URL Deck
    assert new_utub_name == url_deck_header

    utub_selector_names = get_all_utub_selector_names(browser)

    # Assert new UTub name is updated in UTub Deck
    assert new_utub_name in utub_selector_names


# @pytest.mark.skip(reason="Testing another in isolation")
def test_update_utub_name_similar(browser: WebDriver, create_test_utubmembers):
    """
    Tests a UTub owner's ability to update a selected UTub's name to a name similar to another UTub in their collection.

    GIVEN a user owns a UTub
    WHEN user submits the editUTub form
    THEN ensure a modal is presented.
    WHEN user submits
    THEN the form is hidden, the UTub selector name and URL deck header are updated.
    """

    login_utub(browser)

    utub_selector_names = get_all_utub_selector_names(browser)

    new_utub_name = utub_selector_names[1]

    update_utub_name(browser, new_utub_name)

    warning_modal_body = wait_then_get_element(browser, MPL.BODY_MODAL)
    confirmation_modal_body_text = warning_modal_body.get_attribute("innerText")

    utub_name_update_check_text = UTS.BODY_MODAL_UTUB_UPDATE_SAME_NAME

    # Assert warning modal appears with appropriate text
    assert confirmation_modal_body_text == utub_name_update_check_text

    wait_then_click_element(browser, MPL.BUTTON_MODAL_SUBMIT)

    # Wait for POST request
    sleep(4)

    url_deck_header = get_selected_utub_name(browser)

    # Assert new UTub name is updated in URL Deck
    assert new_utub_name == url_deck_header

    # Assert new UTub name is updated in UTub Deck
    assert new_utub_name in utub_selector_names


@pytest.mark.skip(reason="Testing another in isolation")
def test_update_utub_description(browser: WebDriver, create_test_utubs):
    """
    Tests a UTub owner's ability to update the selected UTub description.

    GIVEN a user is the UTub owner
    WHEN the utubDescriptionUpdate form is populated and submitted
    THEN ensure the new description is successfully added to the UTub.
    """

    login_utub(browser)

    update_utub_description(browser, MOCK_UTUB_DESCRIPTION)

    # Wait for POST request
    sleep(4)

    utub_description = get_selected_utub_decsription(browser)

    # Assert new member is added to UTub
    assert MOCK_UTUB_DESCRIPTION == utub_description
