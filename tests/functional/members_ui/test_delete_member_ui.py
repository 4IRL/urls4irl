# Standard library
from time import sleep

# External libraries
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver

# Internal libraries
from locators import MainPageLocators as MPL
from src.mocks.mock_constants import USERNAME_BASE
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
    wait_until_hidden,
)

pytestmark = pytest.mark.members_ui


def test_open_delete_member_modal(browser: WebDriver, create_test_utubmembers):
    """
    Tests a UTub owner's ability to open the delete member modal.

    GIVEN a user owns a UTub with members
    WHEN they submit the addUTub form
    THEN ensure the appropriate input field is shown and in focus
    """

    login_user(browser)

    member_name = USERNAME_BASE + "2"

    select_utub_by_name(browser, UTS.TEST_UTUB_NAME_1)
    delete_member_active_utub(browser, member_name)

    warning_modal = wait_then_get_element(browser, MPL.HOME_MODAL)

    assert warning_modal.is_displayed()

    warning_modal_body = warning_modal.find_element(By.CSS_SELECTOR, MPL.BODY_MODAL)
    confirmation_modal_body_text = warning_modal_body.get_attribute("innerText")

    member_delete_check_text = UTS.BODY_MODAL_MEMBER_DELETE

    # Assert warning modal appears with appropriate text
    assert confirmation_modal_body_text == member_delete_check_text


def test_dismiss_delete_member_modal_btn(browser: WebDriver, create_test_utubmembers):
    """
    Tests a UTub owner's ability to close the delete member modal.

    GIVEN a user owns a UTub with members
    WHEN they submit the addUTub form
    THEN ensure the appropriate input field is shown and in focus
    """

    login_user(browser)

    member_name = USERNAME_BASE + "2"

    select_utub_by_name(browser, UTS.TEST_UTUB_NAME_1)
    delete_member_active_utub(browser, member_name)

    wait_then_click_element(browser, MPL.BUTTON_MODAL_DISMISS)

    create_member_input = wait_until_hidden(browser, MPL.HOME_MODAL)

    # Assert warning modal appears with appropriate text
    assert not create_member_input.is_displayed()


def test_dismiss_delete_member_modal_key(browser: WebDriver, create_test_utubmembers):
    """
    Tests a UTub owner's ability to delete a member from the UTub.

    GIVEN a user owns a UTub with members
    WHEN they submit the addUTub form
    THEN ensure the appropriate input field is shown and in focus
    """

    login_user(browser)

    member_name = USERNAME_BASE + "2"

    select_utub_by_name(browser, UTS.TEST_UTUB_NAME_1)
    delete_member_active_utub(browser, member_name)

    browser.switch_to.active_element.send_keys(Keys.ESCAPE)

    create_member_input = wait_until_hidden(browser, MPL.HOME_MODAL)

    # Assert warning modal appears with appropriate text
    assert not create_member_input.is_displayed()


def test_delete_member_btn(browser: WebDriver, create_test_utubmembers):
    """
    Tests a UTub owner's ability to delete a member from the UTub.

    GIVEN a user owns a UTub with members
    WHEN they submit the addUTub form
    THEN ensure the appropriate input field is shown and in focus
    """

    login_user(browser)

    member_name = USERNAME_BASE + "2"

    select_utub_by_name(browser, UTS.TEST_UTUB_NAME_1)
    delete_member_active_utub(browser, member_name)

    wait_then_click_element(browser, MPL.BUTTON_MODAL_SUBMIT)

    # Wait for DELETE request
    sleep(4)

    member_usernames = get_all_member_usernames(browser)

    # Assert member no longer exists
    assert member_name not in member_usernames
