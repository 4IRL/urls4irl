# External libraries
import time
import pytest

# Internal libraries
from src.mocks.mock_constants import UTUB_NAME_BASE, USERNAME_BASE
from tests.functional.utils_for_test import (
    delete_active_utub,
    select_utub_by_name,
    wait_then_click_element,
    wait_then_get_element,
)
from locators import MainPageLocators as MPL


# @pytest.mark.skip(reason="Testing another in isolation")
def test_delete_utub(create_test_utubs):
    """
    GIVEN a user trying to add a new UTub
    WHEN they submit the addUTub form
    THEN ensure the appropriate input field is shown and in focus
    """

    browser = create_test_utubs

    utub_name = UTUB_NAME_BASE + "1"
    user_name = USERNAME_BASE + "1"

    select_utub_by_name(browser, utub_name)
    delete_active_utub(browser, user_name)

    warning_modal_body = wait_then_get_element(browser, MPL.BODY_MODAL)
    confirmation_modal_body_text = warning_modal_body.get_attribute("innerText")

    # Assert warning modal appears with appropriate text
    assert confirmation_modal_body_text == "This action is irreverisible!"

    wait_then_click_element(browser, MPL.BUTTON_MODAL_SUBMIT)

    # Wait for DELETE request
    time.sleep(4)

    # Assert UTub selector no longer exists
    assert not select_utub_by_name(browser, utub_name)


@pytest.mark.skip(reason="Testing another in isolation")
def test_delete_last_utub(create_test_utub):
    """
    GIVEN a user has one UTub
    WHEN they delete the UTub
    THEN ensure the main page shows appropriate prompts to create a new UTub
    """

    browser = create_test_utub

    delete_active_utub(browser)

    # Extract confirming result
    selector_UTub1 = wait_then_get_element(browser, MPL.SELECTED_UTUB_SELECTOR)

    # Assert new UTub selector was created with input UTub Name
    assert selector_UTub1.text == UTUB_NAME_BASE + "1"
    # Assert new UTub is now active and displayed to user
    assert "active" in selector_UTub1.get_attribute("class")


@pytest.mark.skip(reason="Testing another in isolation")
def test_add_utub_name_similar(create_test_utubs):
    """
    GIVEN a user trying to add a new UTub
    WHEN they submit the addUTub form
    THEN ensure the appropriate input field is shown and in focus
    """

    browser = create_test_utubs

    # Extract name of a pre-existing UTub
    first_UTub_selector = wait_then_get_element(browser, ".UTubSelector")
    utub_name = first_UTub_selector.get_attribute("innerText")

    print(utub_name)

    # Extract modal body element
    confirmation_modal_body = wait_then_get_element(
        browser, "#confirmModalBody", False, 100
    )

    # Assert modal prompts user to consider duplicate UTub naming
    assert (
        confirmation_modal_body.text == "A UTub in your repository has a similar name."
    )
