# Standard library
from time import sleep

# External libraries
import pytest

# Internal libraries
from locators import MainPageLocators as MPL
from src.mocks.mock_constants import UTUB_NAME_BASE
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.members_ui.utils_for_test_members_ui import (
    leave_active_utub,
    leave_all_utubs,
)
from tests.functional.utils_for_test import (
    get_current_user_name,
    get_num_utubs,
    login_user,
    select_utub_by_name,
    wait_then_click_element,
    wait_then_get_element,
)


# @pytest.mark.skip("Test is complete. Frontend functionality incomplete.")
def test_leave_utub(browser, create_test_utubmembers):
    """
    GIVEN a user is the UTub owner
    WHEN they submit the createMember form
    THEN ensure the new member is successfully added to the UTub.
    """

    login_user(browser)

    utub_name = UTUB_NAME_BASE + "2"
    num_utubs = get_num_utubs(browser)

    select_utub_by_name(browser, utub_name)
    leave_active_utub(browser)

    warning_modal_body = wait_then_get_element(browser, MPL.BODY_MODAL)
    confirmation_modal_body_text = warning_modal_body.get_attribute("innerText")

    leave_utub_check_text = UTS.BODY_MODAL_LEAVE_UTUB

    # Assert warning modal appears with appropriate text
    assert confirmation_modal_body_text == leave_utub_check_text

    wait_then_click_element(browser, MPL.BUTTON_MODAL_SUBMIT)

    # Wait for POST request
    sleep(4)

    # Assert member no longer has access to UTub
    assert not select_utub_by_name(browser, utub_name)

    # Assert UTub count is one less than before
    assert get_num_utubs(browser) == num_utubs - 1


@pytest.mark.skip("Test is incomplete. Frontend functionality complete.")
def test_leave_all_utubs(browser, create_test_utubmembers):
    """
    GIVEN a user is the UTub owner
    WHEN they submit the createMember form
    THEN ensure the new member is successfully added to the UTub.
    """

    login_user(browser)

    utub_name = UTUB_NAME_BASE + "2"

    print(get_current_user_name(browser))

    select_utub_by_name(browser, utub_name)
    leave_all_utubs(browser)

    num_utubs = get_num_utubs(browser)

    # Assert member no longer has access to UTub
    assert not select_utub_by_name(browser, utub_name)
    # Assert UTub count is one less than before
    assert get_num_utubs(browser) == num_utubs - 1
