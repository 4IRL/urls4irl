# External libraries
import time
import pytest

# Internal libraries
from src.mocks.mock_constants import UTUB_NAME_BASE, USERNAME_BASE
from tests.functional.members_ui.utils_for_test_members_ui import (
    create_member_active_utub,
)
from tests.functional.utils_for_test import (
    get_current_user_name,
    login_user,
    select_utub_by_name,
    wait_then_click_element,
    wait_then_get_element,
)
from locators import MainPageLocators as MPL


@pytest.mark.skip(reason="Not yet fully implemented")
def test_add_member(browser, add_test_utub):
    """
    GIVEN a user is the UTub owner
    WHEN they submit the createMember form
    THEN ensure the new member is successfully added to the UTub.
    """

    login_user(browser)

    member_name = USERNAME_BASE + "2"
    utub_name = UTUB_NAME_BASE + "1"
    user_name = get_current_user_name(browser)

    select_utub_by_name(browser, utub_name)
    create_member_active_utub(browser, user_name, member_name)

    warning_modal_body = wait_then_get_element(browser, MPL.BODY_MODAL)
    confirmation_modal_body_text = warning_modal_body.get_attribute("innerText")

    utub_delete_check_text = "This action is irreverisible!"

    # Assert warning modal appears with appropriate text
    assert confirmation_modal_body_text == utub_delete_check_text

    wait_then_click_element(browser, MPL.BUTTON_MODAL_SUBMIT)

    # Wait for DELETE request
    time.sleep(4)

    # Assert UTub selector no longer exists
    assert not select_utub_by_name(browser, utub_name)
