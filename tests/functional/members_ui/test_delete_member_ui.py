# External libraries
from time import sleep

# Internal libraries
from src.mocks.mock_constants import UTUB_NAME_BASE, USERNAME_BASE
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.members_ui.utils_for_test_members_ui import (
    delete_member_active_utub,
    get_all_member_usernames,
)
from tests.functional.utils_for_test import (
    login_user,
    select_utub_by_name,
    wait_then_click_element,
    wait_then_get_element,
)
from locators import MainPageLocators as MPL


# @pytest.mark.skip(reason="Testing another in isolation")
def test_delete_member(browser, create_test_utubmembers):
    """
    GIVEN a user trying to add a new UTub
    WHEN they submit the addUTub form
    THEN ensure the appropriate input field is shown and in focus
    """

    login_user(browser)

    utub_name = UTUB_NAME_BASE + "1"
    user_name = UTUB_NAME_BASE + "1"
    member_name = USERNAME_BASE + "2"

    select_utub_by_name(browser, utub_name)
    delete_member_active_utub(browser, user_name, member_name)

    warning_modal_body = wait_then_get_element(browser, MPL.BODY_MODAL)
    confirmation_modal_body_text = warning_modal_body.get_attribute("innerText")

    member_delete_check_text = UTS.BODY_MODAL_MEMBER_DELETE

    # Assert warning modal appears with appropriate text
    assert confirmation_modal_body_text == member_delete_check_text

    wait_then_click_element(browser, MPL.BUTTON_MODAL_SUBMIT)

    # Wait for DELETE request
    sleep(4)

    member_usernames = get_all_member_usernames(browser)

    # Assert member no longer exists
    assert member_name not in member_usernames