# Standard library
from time import sleep

# External libraries
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver

# Internal libraries
from locators import MainPageLocators as MPL
from src.mocks.mock_constants import MOCK_UTUB_NAME_BASE, MOCK_UTUB_DESCRIPTION
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.utils_for_test import (
    get_all_url_ids_in_selected_utub,
    get_all_utub_selector_names,
    get_selected_utub_decsription,
    get_selected_utub_name,
    login_utub,
    select_utub_by_name,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_hidden,
)
from tests.functional.utubs_ui.utils_for_test_utub_ui import (
    assert_active_utub,
    open_update_input,
    update_utub_name,
    update_utub_description,
)


def test_select_utub(browser: WebDriver, create_test_urls):
    """
    Tests a user's ability to select a specific UTub and observe the changes in display.

    GIVEN a fresh load of the U4I Home page
    WHEN user selects a UTub, then selects another UTub
    THEN ensure the URL deck header changes and TODO: displayed URLs change (currently addmock adds same URLs to all UTubs))
    """
    login_utub(browser)

    current_utub_url_ids = get_all_url_ids_in_selected_utub(browser)

    utub_selector_names = get_all_utub_selector_names(browser)

    next_utub_name = utub_selector_names[1]

    select_utub_by_name(browser, next_utub_name)

    next_utub_url_ids = get_all_url_ids_in_selected_utub(browser)

    assert_active_utub(browser, next_utub_name)

    for id in current_utub_url_ids:
        assert id not in next_utub_url_ids


def test_open_update_utub_name_input(browser: WebDriver, create_test_utubs):
    """
    Tests a user's ability to open the updateUTubName input using the pencil button.

    GIVEN a fresh load of the U4I Home page
    WHEN user selects a UTub, then clicks the edit UTub name button
    THEN ensure the updateUTubName input opens
    """
    login_utub(browser)

    utub_name = wait_then_get_element(browser, MPL.HEADER_URL_DECK).text

    open_update_input(browser, 1)

    utub_name_update_input = wait_then_get_element(browser, MPL.INPUT_UTUB_NAME_UPDATE)

    assert utub_name_update_input.is_displayed()

    assert utub_name == utub_name_update_input.get_attribute("value")


def test_close_update_utub_name_input_btn(browser: WebDriver, create_test_utubs):
    """
    Tests a user's ability to close the createUTub input by clicking the 'x' button

    GIVEN a fresh load of the U4I Home page
    WHEN user opens the createUTub input, then clicks the 'x'
    THEN ensure the createUTub input is closed
    """
    login_utub(browser)

    open_update_input(browser, 1)

    wait_then_click_element(browser, MPL.BUTTON_UTUB_NAME_CANCEL_UPDATE)

    update_utub_name_input = wait_until_hidden(browser, MPL.INPUT_UTUB_NAME_UPDATE, 5)

    assert not update_utub_name_input.is_displayed()


def test_close_update_utub_name_input_key(browser: WebDriver, create_test_utubs):
    """
    Tests a user's ability to close the createUTub input by pressing the Escape key

    GIVEN a fresh load of the U4I Home page
    WHEN user opens the createUTub input, then presses 'Esc'
    THEN ensure the createUTub input is closed
    """
    login_utub(browser)

    open_update_input(browser, 1)

    browser.switch_to.active_element.send_keys(Keys.ESCAPE)

    update_utub_name_input = wait_until_hidden(browser, MPL.INPUT_UTUB_NAME_UPDATE, 5)

    assert not update_utub_name_input.is_displayed()


# @pytest.mark.skip(reason="Testing another in isolation")
def test_update_utub_name_btn(browser: WebDriver, create_test_utubs):
    """
    Tests a UTub owner's ability to update a selected UTub's name.

    GIVEN a user owns a UTub
    WHEN they submit the editUTub form
    THEN ensure the form is hidden, the UTub selector name and URL deck header are updated.
    """

    login_utub(browser)

    new_utub_name = MOCK_UTUB_NAME_BASE + "2"

    update_utub_name(browser, new_utub_name)

    # Submits new UTub name
    wait_then_click_element(browser, MPL.BUTTON_UTUB_NAME_SUBMIT_UPDATE)

    # Wait for POST request
    sleep(4)

    url_deck_header = get_selected_utub_name(browser)

    # Assert new UTub name is updated in URL Deck
    assert new_utub_name == url_deck_header

    utub_selector_names = get_all_utub_selector_names(browser)

    # Assert new UTub name is updated in UTub Deck
    assert new_utub_name in utub_selector_names


# @pytest.mark.skip(reason="Testing another in isolation")
def test_update_utub_name_key(browser: WebDriver, create_test_utubs):
    """
    Tests a UTub owner's ability to update a selected UTub's name.

    GIVEN a user owns a UTub
    WHEN they submit the editUTub form
    THEN ensure the form is hidden, the UTub selector name and URL deck header are updated.
    """

    login_utub(browser)

    new_utub_name = MOCK_UTUB_NAME_BASE + "2"

    update_utub_name(browser, new_utub_name)

    # Submits new UTub name
    browser.switch_to.active_element.send_keys(Keys.ENTER)

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

    # Submits new UTub name
    wait_then_click_element(browser, MPL.BUTTON_UTUB_NAME_SUBMIT_UPDATE)

    # Wait for POST request
    sleep(4)

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


# @pytest.mark.skip(reason="Testing another in isolation")
def test_open_update_utub_description_input(browser: WebDriver, create_test_utubs):
    """
    Tests a user's ability to open the updateUTubDescription input using the pencil button.

    GIVEN a fresh load of the U4I Home page
    WHEN user selects a UTub, then clicks the edit UTub description button
    THEN ensure the updateUTubDescription input opens
    """
    login_utub(browser)

    utub_description = wait_then_get_element(browser, MPL.SUBHEADER_URL_DECK).text

    open_update_input(browser, 0)

    utub_description_update_input = wait_then_get_element(
        browser, MPL.INPUT_UTUB_DESCRIPTION_UPDATE
    )

    assert utub_description_update_input.is_displayed()

    assert utub_description == utub_description_update_input.get_attribute("value")


def test_close_update_utub_description_input_btn(browser: WebDriver, create_test_utubs):
    """
    Tests a user's ability to close the updateUTubDescription input by clicking the 'x' button

    GIVEN a fresh load of the U4I Home page
    WHEN user opens the updateUTubDescription input, then clicks the 'x'
    THEN ensure the updateUTubDescription input is closed
    """
    login_utub(browser)

    open_update_input(browser, 0)

    wait_then_click_element(browser, MPL.BUTTON_UTUB_DESCRIPTION_CANCEL_UPDATE)

    update_utub_name_input = wait_until_hidden(browser, MPL.INPUT_UTUB_NAME_UPDATE, 5)

    assert not update_utub_name_input.is_displayed()


def test_close_update_utub_description_input_key(browser: WebDriver, create_test_utubs):
    """
    Tests a user's ability to close the updateUTubDescription input by pressing the Escape key

    GIVEN a fresh load of the U4I Home page
    WHEN user opens the updateUTubDescription input, then presses 'Esc'
    THEN ensure the updateUTubDescription input is closed
    """
    login_utub(browser)

    open_update_input(browser, 0)

    browser.switch_to.active_element.send_keys(Keys.ESCAPE)

    update_utub_name_input = wait_until_hidden(browser, MPL.INPUT_UTUB_NAME_UPDATE, 5)

    assert not update_utub_name_input.is_displayed()


# @pytest.mark.skip(reason="Testing another in isolation")
def test_update_utub_description_btn(browser: WebDriver, create_test_utubs):
    """
    Tests a UTub owner's ability to update the selected UTub description.

    GIVEN a user is the UTub owner
    WHEN the utubDescriptionUpdate form is populated and submitted
    THEN ensure the new description is successfully added to the UTub.
    """

    login_utub(browser)

    update_utub_description(browser, MOCK_UTUB_DESCRIPTION)

    # Submits new UTub description
    wait_then_click_element(browser, MPL.BUTTON_UTUB_DESCRIPTION_SUBMIT_UPDATE)

    # Wait for POST request
    sleep(4)

    utub_description = get_selected_utub_decsription(browser)

    # Assert new member is added to UTub
    assert MOCK_UTUB_DESCRIPTION == utub_description


# @pytest.mark.skip(reason="Testing another in isolation")
def test_update_utub_description_key(browser: WebDriver, create_test_utubs):
    """
    Tests a UTub owner's ability to update the selected UTub description.

    GIVEN a user is the UTub owner
    WHEN the utubDescriptionUpdate form is populated and submitted
    THEN ensure the new description is successfully added to the UTub.
    """

    login_utub(browser)

    update_utub_description(browser, MOCK_UTUB_DESCRIPTION)

    # Submits new UTub description
    browser.switch_to.active_element.send_keys(Keys.ENTER)

    # Wait for POST request
    sleep(4)

    utub_description = get_selected_utub_decsription(browser)

    # Assert new member is added to UTub
    assert MOCK_UTUB_DESCRIPTION == utub_description
