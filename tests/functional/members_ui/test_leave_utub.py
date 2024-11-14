# Standard library
from time import sleep

# External libraries
from selenium.webdriver.remote.webdriver import WebDriver

# Internal libraries
from locators import MainPageLocators as MPL
from src.mocks.mock_constants import MOCK_UTUB_NAME_BASE
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.members_ui.utils_for_test_members_ui import (
    leave_active_utub,
)
from tests.functional.utils_for_test import (
    get_num_utubs,
    login_user,
    select_utub_by_name,
    wait_then_click_element,
    wait_then_get_element,
)


# @pytest.mark.skip(reason="Testing another in isolation")
def test_leave_utub(browser: WebDriver, create_test_utubmembers):
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
