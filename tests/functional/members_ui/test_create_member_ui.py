from flask import Flask
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver

from src.cli.mock_constants import USERNAME_BASE
from src.models.users import Users
from src.models.utub_members import Utub_Members
from src.utils.strings.user_strs import MEMBER_FAILURE, USER_FAILURE
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.members_ui.utils_for_test_members_ui import (
    create_member_active_utub,
    get_all_member_usernames,
)
from tests.functional.utils_for_test import (
    login_user_and_select_utub_by_name,
    select_utub_by_name,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_hidden,
    wait_until_visible_css_selector,
)
from tests.functional.utubs_ui.utils_for_test_utub_ui import (
    get_utub_this_user_created,
    get_utub_this_user_did_not_create,
)

pytestmark = pytest.mark.members_ui


def test_open_input_create_member(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    Tests a UTub owner's ability to open the create member input field.

    GIVEN a user is the UTub owner with the UTub selected
    WHEN the user clicks the createMember plus button
    THEN ensure the createMember form is opened.
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)

    wait_then_click_element(browser, HPL.BUTTON_MEMBER_CREATE)

    create_member_input = wait_then_get_element(browser, HPL.INPUT_MEMBER_CREATE)
    assert create_member_input is not None

    assert create_member_input.is_displayed()


def test_cancel_input_create_member_x(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    Tests a UTub owner's ability to close the create member input field.

    GIVEN a user is the UTub owner with the UTub selected
    WHEN the user clicks the createMember plus button, then clicks the x button
    THEN ensure the createMember form is not shown.
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)

    wait_then_click_element(browser, HPL.BUTTON_MEMBER_CREATE)

    wait_then_click_element(browser, HPL.BUTTON_MEMBER_CANCEL_CREATE)

    create_member_input = wait_until_hidden(browser, HPL.INPUT_MEMBER_CREATE)

    assert not create_member_input.is_displayed()


def test_cancel_input_create_member_key(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    Tests a UTub owner's ability to close the create member input field.

    GIVEN a user is the UTub owner with the UTub selected
    WHEN the user clicks the createMember plus button, then presses the esc key
    THEN ensure the createMember form is not shown.
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)

    wait_then_click_element(browser, HPL.BUTTON_MEMBER_CREATE)

    browser.switch_to.active_element.send_keys(Keys.ESCAPE)

    create_member_input = wait_until_hidden(browser, HPL.INPUT_MEMBER_CREATE)

    assert not create_member_input.is_displayed()


def test_create_member_btn(browser: WebDriver, create_test_utubs, provide_app: Flask):
    """
    Tests a UTub owner's ability to create a member by adding another U4I user to the UTub.

    GIVEN a user is the UTub owner
    WHEN the createMember form is populated and submitted
    THEN ensure the new member is successfully added to the UTub.
    """

    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)

    new_member_username = USERNAME_BASE + "2"
    create_member_active_utub(browser, new_member_username)

    # Submits new member form
    wait_then_click_element(browser, HPL.BUTTON_MEMBER_SUBMIT_CREATE)

    # Wait for POST request
    wait_until_hidden(browser, HPL.BUTTON_MEMBER_SUBMIT_CREATE, timeout=3)

    member_usernames = get_all_member_usernames(browser)

    # Assert new member is added to UTub
    assert new_member_username in member_usernames


def test_create_member_key(browser: WebDriver, create_test_utubs, provide_app: Flask):
    """
    Tests a UTub owner's ability to create a member by adding another U4I user to the UTub.

    GIVEN a user is the UTub owner
    WHEN the createMember form is populated and submitted
    THEN ensure the new member is successfully added to the UTub.
    """

    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)

    new_member_username = USERNAME_BASE + "2"
    create_member_active_utub(browser, new_member_username)

    # Submits new member form
    browser.switch_to.active_element.send_keys(Keys.ENTER)

    # Wait for POST request
    wait_until_hidden(browser, HPL.BUTTON_MEMBER_SUBMIT_CREATE, timeout=3)

    member_usernames = get_all_member_usernames(browser)

    # Assert new member is added to UTub
    assert new_member_username in member_usernames


def test_create_member_denied(
    browser: WebDriver,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    Tests a UTub member's inability to create a member in the UTub.

    GIVEN a user is a UTub member
    THEN the user does not have access to the createMember plus button
    """
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    utub_user_member_of = get_utub_this_user_did_not_create(app, user_id)
    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)

    select_utub_by_name(browser, utub_user_member_of.name)

    create_member_btn = wait_until_hidden(browser, HPL.BUTTON_MEMBER_CREATE)

    assert not create_member_btn.is_displayed()


def test_create_member_username_not_exist(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a user is the UTub owner
    WHEN the createMember form is populated and submitted with a username that does not exist
    THEN ensure U4I responds appropriately with error message.
    """

    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)

    new_member_username = USERNAME_BASE + "999A"
    create_member_active_utub(browser, new_member_username)

    # Submits new member form
    wait_then_click_element(browser, HPL.BUTTON_MEMBER_SUBMIT_CREATE)

    # Wait for POST request
    wait_until_visible_css_selector(browser, HPL.INPUT_MEMBER_CREATE_ERROR, timeout=3)
    member_error_elem = browser.find_element(
        By.CSS_SELECTOR, HPL.INPUT_MEMBER_CREATE_ERROR
    )
    assert member_error_elem is not None
    assert USER_FAILURE.USER_NOT_EXIST == member_error_elem.text


def test_create_member_username_field_empty(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a user is the UTub owner
    WHEN the createMember form is submitted with an empty field
    THEN ensure U4I responds appropriately with error message.
    """

    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)

    new_member_username = ""
    create_member_active_utub(browser, new_member_username)

    # Submits new member form
    wait_then_click_element(browser, HPL.BUTTON_MEMBER_SUBMIT_CREATE)

    # Wait for POST request
    wait_until_visible_css_selector(browser, HPL.INPUT_MEMBER_CREATE_ERROR, timeout=3)
    member_error_elem = browser.find_element(
        By.CSS_SELECTOR, HPL.INPUT_MEMBER_CREATE_ERROR
    )
    assert member_error_elem is not None
    assert MEMBER_FAILURE.FIELD_REQUIRED_STR == member_error_elem.text


def test_create_member_duplicate_member(
    browser: WebDriver, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a user is the UTub owner
    WHEN the createMember form is submitted with a user that is already a member
    THEN ensure U4I responds appropriately with error message.
    """

    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)
    with app.app_context():
        utub_member: Utub_Members = Utub_Members.query.filter(
            Utub_Members.user_id != user_id,
            Utub_Members.utub_id == utub_user_created.id,
        ).first()
        utub_member_user: Users = utub_member.to_user
        utub_member_username = utub_member_user.username

    create_member_active_utub(browser, utub_member_username)

    # Submits new member form
    wait_then_click_element(browser, HPL.BUTTON_MEMBER_SUBMIT_CREATE)

    # Wait for POST request
    wait_until_visible_css_selector(browser, HPL.INPUT_MEMBER_CREATE_ERROR, timeout=3)
    member_error_elem = browser.find_element(
        By.CSS_SELECTOR, HPL.INPUT_MEMBER_CREATE_ERROR
    )
    assert member_error_elem is not None
    assert MEMBER_FAILURE.MEMBER_ALREADY_IN_UTUB == member_error_elem.text


def test_create_member_form_resets_on_close(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a user is the UTub owner
    WHEN the createMember form is populated and submitted with a username that does not exist, an error is shown, and the user closes the form
    THEN ensure the form is reset without errors
    """

    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)

    new_member_username = USERNAME_BASE + "999A"
    create_member_active_utub(browser, new_member_username)

    # Submits new member form
    wait_then_click_element(browser, HPL.BUTTON_MEMBER_SUBMIT_CREATE)

    # Wait for POST request
    wait_until_visible_css_selector(browser, HPL.INPUT_MEMBER_CREATE_ERROR, timeout=3)

    # Close form
    wait_then_click_element(browser, HPL.BUTTON_MEMBER_CANCEL_CREATE, time=3)

    wait_then_click_element(browser, HPL.BUTTON_MEMBER_CREATE, time=3)
    member_error_elem = browser.find_element(
        By.CSS_SELECTOR, HPL.INPUT_MEMBER_CREATE_ERROR
    )
    assert member_error_elem is not None
    assert not member_error_elem.is_displayed()
    assert "" == member_error_elem.text
