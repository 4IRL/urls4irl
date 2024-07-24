# Standard library
from time import sleep

# External libraries
import pytest

# Internal libraries
from locators import MainPageLocators as MPL
from src.mocks.mock_constants import MOCK_UTUB_NAME_BASE
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.members_ui.utils_for_test_members_ui import (
    leave_active_utub,
    leave_all_utubs,
)
from tests.functional.utils_for_test import (
    get_num_utubs,
    login_user,
    select_utub_by_name,
    wait_then_click_element,
    wait_then_get_element,
)


# @pytest.mark.skip(reason="Testing another in isolation")
def test_leave_utub(browser, create_test_utubmembers):
    """
    Tests a UTub user's ability to leave a UTub.

    GIVEN a user is a UTub member
    WHEN the memberSelfBtnDelete button is selected
    THEN ensure the user is successfully removed from the UTub.
    """

    login_user(browser)

    utub_name = MOCK_UTUB_NAME_BASE + "2"
    num_utubs = get_num_utubs(browser)

    select_utub_by_name(browser, utub_name)
    leave_active_utub(browser)

    warning_modal_body = wait_then_get_element(browser, MPL.BODY_MODAL)
    confirmation_modal_body_text = warning_modal_body.get_attribute("innerText")

    # Assert warning modal appears with appropriate text
    assert confirmation_modal_body_text == UTS.BODY_MODAL_LEAVE_UTUB

    wait_then_click_element(browser, MPL.BUTTON_MODAL_SUBMIT)

    # Wait for POST request
    sleep(4)

    # Assert member no longer has access to UTub
    assert not select_utub_by_name(browser, utub_name)

    # Assert UTub count is one less than before
    assert get_num_utubs(browser) == num_utubs - 1


@pytest.mark.skip(reason="Test complete. Frontend functionality incomplete.")
def test_leave_all_utubs(browser, create_test_utubmembers):
    """
    Tests the site response to a user leaving the final instance of membership to UTubs. (Current addmocks require deletion of the user's own UTub first.)

    GIVEN a user has access to UTubs
    WHEN user clicks the memberSelfBtnDelete button on the last instance of accessible UTubs
    THEN ensure the user is supplied a prompt to create a UTub.
    """

    login_user(browser)

    leave_all_utubs(browser)

    subheader_utub_deck = wait_then_get_element(browser, MPL.SUBHEADER_UTUB_DECK)
    subheader_utub_deck_text = subheader_utub_deck.get_attribute("innerText")

    # Assert U4I prompts user to Create UTub
    assert subheader_utub_deck_text == UTS.MESSAGE_NO_UTUBS
    # Assert UTub count is one less than before
    assert get_num_utubs(browser) == 0
