from flask import Flask
import pytest
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver

from locators import HomePageLocators as HPL
from src.models.users import Users
from src.models.utub_members import Member_Role, Utub_Members
from src.utils.strings.user_strs import MEMBER_DELETE_WARNING
from tests.functional.assert_utils import (
    assert_active_utub,
    assert_login_with_username,
    assert_on_429_page,
    assert_visited_403_on_invalid_csrf_and_reload,
)
from tests.functional.db_utils import (
    get_other_member_in_utub,
    get_utub_this_user_created,
    get_utub_this_user_did_not_create,
)
from tests.functional.login_utils import login_user_and_select_utub_by_name
from tests.functional.members_ui.selenium_utils import (
    delete_member_active_utub,
    get_all_member_usernames,
)
from tests.functional.selenium_utils import (
    add_forced_rate_limit_header,
    dismiss_modal_with_click_out,
    invalidate_csrf_token_on_page,
    wait_for_element_to_be_removed,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_hidden,
    wait_until_visible_css_selector,
)

pytestmark = pytest.mark.members_ui


def test_open_delete_member_modal(
    browser: WebDriver,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN a user owns a UTub with members
    WHEN they click on the delete member button after hovering over the member
    THEN ensure the modal to confirm deleting a member is shown
    """
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)
    other_member = get_other_member_in_utub(app, utub_user_created.id, user_id)

    member_name = other_member.username

    delete_member_active_utub(browser, member_name)

    warning_modal = wait_then_get_element(browser, HPL.HOME_MODAL)
    assert warning_modal is not None

    assert warning_modal.is_displayed()

    warning_modal_body = warning_modal.find_element(By.CSS_SELECTOR, HPL.BODY_MODAL)
    confirmation_modal_body_text = warning_modal_body.get_attribute("innerText")

    member_delete_check_text = MEMBER_DELETE_WARNING

    # Assert warning modal appears with appropriate text
    assert confirmation_modal_body_text == member_delete_check_text


def test_dismiss_delete_member_modal_btn(
    browser: WebDriver,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN a user owns a UTub with members
    WHEN they open the delete member modal, but dismiss it by clicking the cancel button
    THEN ensure the modal is then dismissed
    """
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)
    other_member = get_other_member_in_utub(app, utub_user_created.id, user_id)

    member_name = other_member.username

    delete_member_active_utub(browser, member_name)

    wait_then_click_element(browser, HPL.BUTTON_MODAL_DISMISS)

    create_member_input = wait_until_hidden(browser, HPL.HOME_MODAL)

    # Assert warning modal appears with appropriate text
    assert not create_member_input.is_displayed()


def test_dismiss_delete_member_modal_x(
    browser: WebDriver,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN a user owns a UTub with members
    WHEN they open the delete member modal, but dismiss it by clicking the X button on the modal
    THEN ensure the modal is then dismissed
    """
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)
    other_member = get_other_member_in_utub(app, utub_user_created.id, user_id)

    member_name = other_member.username

    delete_member_active_utub(browser, member_name)

    wait_until_visible_css_selector(browser, HPL.HOME_MODAL, timeout=3)
    home_modal = browser.find_element(By.CSS_SELECTOR, HPL.HOME_MODAL)
    x_btn = home_modal.find_element(By.CSS_SELECTOR, HPL.BUTTON_X_CLOSE)
    assert x_btn.is_displayed()
    x_btn.click()

    create_member_input = wait_until_hidden(browser, HPL.HOME_MODAL)

    # Assert warning modal appears with appropriate text
    assert not create_member_input.is_displayed()


def test_dismiss_delete_member_modal_click_outside_modal(
    browser: WebDriver,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN a user owns a UTub with members
    WHEN they open the delete member modal, but dismiss it by clicking outside the modal
    THEN ensure the modal is then dismissed
    """
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)
    other_member = get_other_member_in_utub(app, utub_user_created.id, user_id)

    member_name = other_member.username

    delete_member_active_utub(browser, member_name)

    wait_until_visible_css_selector(browser, HPL.HOME_MODAL, timeout=3)
    dismiss_modal_with_click_out(browser)

    create_member_input = wait_until_hidden(browser, HPL.HOME_MODAL)

    # Assert warning modal appears with appropriate text
    assert not create_member_input.is_displayed()


def test_dismiss_delete_member_modal_key(
    browser: WebDriver,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN a user owns a UTub with members
    WHEN they open the delete member modal, but dismiss it by pressing the escape key
    THEN ensure the modal is then dismissed
    """
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)
    other_member = get_other_member_in_utub(app, utub_user_created.id, user_id)

    member_name = other_member.username
    delete_member_active_utub(browser, other_member.username)

    delete_member_active_utub(browser, member_name)

    home_modal = wait_then_get_element(browser, HPL.HOME_MODAL)
    assert home_modal is not None

    home_modal.send_keys(Keys.ESCAPE)

    create_member_input = wait_until_hidden(browser, HPL.HOME_MODAL)

    # Assert warning modal appears with appropriate text
    assert not create_member_input.is_displayed()


def test_delete_member_btn(
    browser: WebDriver,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN a user owns a UTub with members
    WHEN they submit the delete UTub Member modal
    THEN ensure the member is removed from the UTub
    """
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)
    other_member = get_other_member_in_utub(app, utub_user_created.id, user_id)

    member_name = other_member.username
    delete_member_active_utub(browser, other_member.username)

    wait_then_click_element(browser, HPL.BUTTON_MODAL_SUBMIT)

    # Wait for DELETE request
    member_selector = f'{HPL.BADGES_MEMBERS}[memberid="{other_member.id}"]'
    member_elem = browser.find_element(By.CSS_SELECTOR, member_selector)
    wait_until_hidden(browser, HPL.BUTTON_MODAL_SUBMIT, timeout=3)
    wait_for_element_to_be_removed(browser, member_elem)

    member_usernames = get_all_member_usernames(browser)

    # Assert member no longer exists
    assert member_name not in member_usernames


def test_delete_member_rate_limits(
    browser: WebDriver,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN a user owns a UTub with members but they are rate limited
    WHEN they submit the delete UTub Member modal
    THEN ensure the 429 error page is shown
    """
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)
    other_member = get_other_member_in_utub(app, utub_user_created.id, user_id)

    delete_member_active_utub(browser, other_member.username)

    add_forced_rate_limit_header(browser)
    wait_then_click_element(browser, HPL.BUTTON_MODAL_SUBMIT)
    assert_on_429_page(browser)


def test_open_delete_member_modal_fails_as_member(
    browser: WebDriver,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN a user who is a member of a UTub
    WHEN they hover over another member in the UTub
    THEN ensure delete member button is not shown to the user
    """
    app = provide_app

    user_id = 1
    utub_user_member_of = get_utub_this_user_did_not_create(app, user_id)
    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_member_of.name)

    with app.app_context():
        other_member: Utub_Members = Utub_Members.query.filter(
            Utub_Members.user_id != user_id,
            Utub_Members.utub_id == utub_user_member_of.id,
            Utub_Members.member_role == Member_Role.MEMBER,
        ).first()
        other_user = other_member.to_user

    member_selector = f'{HPL.BADGES_MEMBERS}[memberid="{other_user.id}"]'

    other_member_element = wait_then_get_element(browser, member_selector, time=3)
    assert other_member_element is not None

    actions = ActionChains(browser)
    actions.move_to_element(other_member_element).perform()
    actions.pause(1).perform()

    with pytest.raises(NoSuchElementException):
        other_member_element.find_element(By.CSS_SELECTOR, HPL.BUTTON_MEMBER_DELETE)


def test_delete_member_invalid_csrf_token(
    browser: WebDriver,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN a user owns a UTub with members
    WHEN they submit the delete UTub Member modal with an invalid CSRF token
    THEN ensure U4I responds with a proper error message
    """
    app = provide_app

    user_id = 1
    with app.app_context():
        user: Users = Users.query.get(user_id)
        username = user.username
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)
    other_member = get_other_member_in_utub(app, utub_user_created.id, user_id)

    member_name = other_member.username
    delete_member_active_utub(browser, member_name)

    invalidate_csrf_token_on_page(browser)
    wait_then_click_element(browser, HPL.BUTTON_MODAL_SUBMIT)

    assert_visited_403_on_invalid_csrf_and_reload(browser)

    # Page reloads after user clicks button in CSRF 403 error page
    assert_login_with_username(browser, username)

    # Reload will bring user back to the UTub they were in before
    assert_active_utub(browser, utub_user_created.name)

    delete_utub_submit_btn_modal = wait_until_hidden(
        browser, HPL.BUTTON_MODAL_SUBMIT, timeout=3
    )
    assert not delete_utub_submit_btn_modal.is_displayed()
