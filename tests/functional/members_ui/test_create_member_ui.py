# ndard library
from time import sleep

# External libraries
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver

# Internal libraries
from src.mocks.mock_constants import MOCK_UTUB_NAME_BASE, USERNAME_BASE
from tests.functional.locators import MainPageLocators as MPL
from tests.functional.members_ui.utils_for_test_members_ui import (
    create_member_active_utub,
    get_all_member_usernames,
)
from tests.functional.utils_for_test import (
    login_utub,
    select_utub_by_name,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_hidden,
)


def test_open_input_create_member(browser: WebDriver, create_test_utubs):
    """
    Tests a UTub owner's ability to open the create member input field.

    GIVEN a user is the UTub owner with the UTub selected
    WHEN the user clicks the createMember plus button
    THEN ensure the createMember form is opened.
    """
    login_utub(browser)

    wait_then_click_element(browser, MPL.BUTTON_MEMBER_CREATE)

    create_member_input = wait_then_get_element(browser, MPL.INPUT_MEMBER_CREATE)

    assert create_member_input.is_displayed()


def test_cancel_input_create_member_x(browser: WebDriver, create_test_utubs):
    """
    Tests a UTub owner's ability to close the create member input field.

    GIVEN a user is the UTub owner with the UTub selected
    WHEN the user clicks the createMember plus button, then clicks the x button
    THEN ensure the createMember form is not shown.
    """
    login_utub(browser)

    wait_then_click_element(browser, MPL.BUTTON_MEMBER_CREATE)

    wait_then_click_element(browser, MPL.BUTTON_MEMBER_CANCEL_CREATE)

    create_member_input = wait_until_hidden(browser, MPL.INPUT_MEMBER_CREATE)

    assert not create_member_input.is_displayed()


def test_cancel_input_create_member_key(browser: WebDriver, create_test_utubs):
    """
    Tests a UTub owner's ability to close the create member input field.

    GIVEN a user is the UTub owner with the UTub selected
    WHEN the user clicks the createMember plus button, then presses the esc key
    THEN ensure the createMember form is not shown.
    """
    login_utub(browser)

    wait_then_click_element(browser, MPL.BUTTON_MEMBER_CREATE)

    create_member_input = wait_then_get_element(browser, MPL.INPUT_MEMBER_CREATE)

    browser.switch_to.active_element.send_keys(Keys.ESCAPE)

    assert not create_member_input.is_displayed()


def test_create_member_btn(browser: WebDriver, create_test_utubs):
    """
    Tests a UTub owner's ability to create a member by adding another U4I user to the UTub.

    GIVEN a user is the UTub owner
    WHEN the createMember form is populated and submitted
    THEN ensure the new member is successfully added to the UTub.
    """

    login_utub(browser)

    new_member_username = USERNAME_BASE + "2"
    create_member_active_utub(browser, new_member_username)

    # Submits new member form
    wait_then_click_element(browser, MPL.BUTTON_MEMBER_SUBMIT_CREATE)

    # Wait for POST request
    sleep(4)

    member_usernames = get_all_member_usernames(browser)

    # Assert new member is added to UTub
    assert new_member_username in member_usernames


def test_create_member_key(browser: WebDriver, create_test_utubs):
    """
    Tests a UTub owner's ability to create a member by adding another U4I user to the UTub.

    GIVEN a user is the UTub owner
    WHEN the createMember form is populated and submitted
    THEN ensure the new member is successfully added to the UTub.
    """

    login_utub(browser)

    new_member_username = USERNAME_BASE + "2"
    create_member_active_utub(browser, new_member_username)

    # Submits new member form
    browser.switch_to.active_element.send_keys(Keys.ENTER)

    # Wait for POST request
    sleep(4)

    member_usernames = get_all_member_usernames(browser)

    # Assert new member is added to UTub
    assert new_member_username in member_usernames


def test_create_member_denied(browser: WebDriver, create_test_utubmembers):
    """
    Tests a UTub member's inability to create a member in the UTub.

    GIVEN a user is a UTub member
    THEN the user does not have access to the createMember plus button
    """

    login_utub(browser)

    member_utub = MOCK_UTUB_NAME_BASE + "2"
    select_utub_by_name(browser, member_utub)

    create_member_btn = wait_until_hidden(browser, MPL.BUTTON_MEMBER_CREATE)

    assert not create_member_btn.is_displayed()
