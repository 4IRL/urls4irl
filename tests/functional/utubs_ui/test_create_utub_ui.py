# External libraries
import pytest
from time import sleep

# Internal libraries
from src.mocks.mock_constants import MOCK_UTUB_DESCRIPTION, MOCK_UTUB_NAME_BASE
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.utils_for_test import (
    login_user,
    wait_then_get_element,
    wait_then_get_elements,
)
from tests.functional.locators import MainPageLocators as MPL
from utils_for_test_utub_ui import create_utub


# @pytest.mark.skip(reason="Testing another in isolation")
def test_create_utub(browser, create_test_users):
    """
    GIVEN a user trying to add a new UTub
    WHEN they submit the addUTub form
    THEN ensure the appropriate input field is shown and in focus
    """

    login_user(browser)

    utub_name = MOCK_UTUB_NAME_BASE + "1"

    create_utub(browser, utub_name, MOCK_UTUB_DESCRIPTION)

    # Wait for POST request
    sleep(4)

    # Extract new UTub selector. Selector should be active.
    selector_UTub = wait_then_get_element(browser, MPL.SELECTOR_SELECTED_UTUB)

    # Assert new UTub selector was created with input UTub Name
    assert selector_UTub.text == utub_name

    selector_UTub.click()
    # Assert new UTub is now active and displayed to user
    assert "active" in selector_UTub.get_attribute("class")


@pytest.mark.skip(
    reason="Not on happy path. This test tests functionality that is not yet captured on the frontend"
)
def test_create_utub_name_length_exceeded(browser, create_test_users):
    """
    GIVEN a user trying to add a new UTub
    WHEN they submit the addUTub form
    THEN ensure the appropriate input field is shown and in focus
    """

    login_user(browser)

    create_utub(browser, UTS.MAX_CHAR_LIM_UTUB_NAME)

    warning_modal_body = wait_then_get_element(browser, "#confirmModalBody")

    # Assert new UTub is now active and displayed to user
    assert warning_modal_body.text == "Try shortening your UTub name"


# @pytest.mark.skip(reason="Testing another in isolation")
def test_create_utub_name_similar(browser, create_test_utubs):
    """
    GIVEN a user trying to add a new UTub
    WHEN they submit the addUTub form
    THEN ensure the appropriate input field is shown and in focus
    """

    login_user(browser)

    # Extract name of a pre-existing UTub
    UTub_selectors = wait_then_get_elements(browser, MPL.SELECTORS_UTUB)
    first_UTub_selector = UTub_selectors[0]
    utub_name = first_UTub_selector.text

    # Attempt to add a new UTub with the same name
    create_utub(browser, utub_name, MOCK_UTUB_DESCRIPTION)

    # Extract modal body element
    confirmation_modal_body = wait_then_get_element(browser, MPL.BODY_MODAL)
    confirmation_modal_body_text = confirmation_modal_body.get_attribute("innerText")
    utub_same_name_check_text = UTS.BODY_MODAL_UTUB_SAME_NAME

    # Assert modal prompts user to consider duplicate UTub naming
    assert confirmation_modal_body_text == utub_same_name_check_text
