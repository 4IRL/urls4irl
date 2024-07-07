# External libraries
from time import sleep
import pytest

# Internal libraries
from src.mocks.mock_constants import UTUB_NAME_BASE, USERNAME_BASE
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.utils_for_test import (
    login_user,
    select_utub_by_name,
    wait_then_click_element,
    wait_then_get_element,
)
from locators import MainPageLocators as MPL
from tests.functional.utubs_ui.utils_for_test_utub_ui import delete_active_utub


# @pytest.mark.skip(reason="Testing another in isolation")
def test_delete_utub(browser, create_test_utubs):
    """
    GIVEN a user trying to add a new UTub
    WHEN they submit the addUTub form
    THEN ensure the appropriate input field is shown and in focus
    """

    login_user(browser)

    utub_name = UTUB_NAME_BASE + "1"
    user_name = USERNAME_BASE + "1"

    select_utub_by_name(browser, utub_name)
    delete_active_utub(browser, user_name)

    warning_modal_body = wait_then_get_element(browser, MPL.BODY_MODAL)
    confirmation_modal_body_text = warning_modal_body.get_attribute("innerText")

    utub_delete_check_text = UTS.BODY_MODAL_UTUB_DELETE

    # Assert warning modal appears with appropriate text
    assert confirmation_modal_body_text == utub_delete_check_text

    wait_then_click_element(browser, MPL.BUTTON_MODAL_SUBMIT)

    # Wait for DELETE request
    sleep(4)

    # Assert UTub selector no longer exists
    assert not select_utub_by_name(browser, utub_name)


@pytest.mark.skip(reason="Test not yet implemented")
def test_delete_last_utub(browser, create_test_utub):
    """
    GIVEN a user has one UTub
    WHEN they delete the UTub
    THEN ensure the main page shows appropriate prompts to create a new UTub
    """

    login_user(browser)

    delete_active_utub(browser)

    # Extract confirming result
    selector_UTub1 = wait_then_get_element(browser, MPL.SELECTOR_SELECTED_UTUB)

    # Assert new UTub selector was created with input UTub Name
    assert selector_UTub1.text == UTUB_NAME_BASE + "1"
    # Assert new UTub is now active and displayed to user
    assert "active" in selector_UTub1.get_attribute("class")
