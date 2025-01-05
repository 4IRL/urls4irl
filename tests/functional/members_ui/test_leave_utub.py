from flask import Flask
import pytest
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver

from locators import HomePageLocators as HPL
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.utils_for_test import (
    dismiss_modal_with_click_out,
    get_num_utubs,
    login_user_and_select_utub_by_name,
    wait_for_element_to_be_removed,
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


def test_open_leave_utub_modal(
    browser: WebDriver,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    Tests a UTub user's ability to open the leave UTub modal

    GIVEN a user is a UTub member
    WHEN the memberSelfBtnDelete button is clicked
    THEN ensure the user is shown the modal confirming if they want to leave the UTub
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_member_of = get_utub_this_user_did_not_create(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app, browser, user_id_for_test, utub_user_member_of.name
    )

    leave_utub_btn = wait_then_get_element(browser, HPL.BUTTON_UTUB_LEAVE, time=3)
    assert leave_utub_btn is not None
    assert leave_utub_btn.is_displayed()

    leave_utub_btn.click()

    warning_modal_body = wait_then_get_element(browser, HPL.BODY_MODAL, time=3)
    assert warning_modal_body is not None
    assert warning_modal_body.is_displayed()

    confirmation_modal_body_text = warning_modal_body.text

    # Assert warning modal appears with appropriate text
    assert confirmation_modal_body_text == UTS.BODY_MODAL_LEAVE_UTUB


def test_dismiss_leave_utub_modal_btn(
    browser: WebDriver,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    Tests a UTub user's ability to dismiss the leave UTub modal

    GIVEN a user is a UTub member, and has opened the leave UTub modal
    WHEN the "Stay In UTub" button is clicked
    THEN ensure the modal is hidden
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_member_of = get_utub_this_user_did_not_create(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app, browser, user_id_for_test, utub_user_member_of.name
    )

    wait_then_click_element(browser, HPL.BUTTON_UTUB_LEAVE, time=3)
    wait_until_visible_css_selector(browser, HPL.HOME_MODAL, timeout=3)

    dismiss_modal_btn = browser.find_element(By.CSS_SELECTOR, HPL.BUTTON_MODAL_DISMISS)
    assert dismiss_modal_btn.is_displayed()
    dismiss_modal_btn.click()

    modal = wait_until_hidden(browser, HPL.BODY_MODAL, timeout=3)
    assert not modal.is_displayed()


def test_dismiss_leave_utub_modal_x(
    browser: WebDriver,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    Tests a UTub user's ability to dismiss the leave UTub modal

    GIVEN a user is a UTub member, and has opened the leave UTub modal
    WHEN the user clicks the X button on the modal
    THEN ensure the modal is hidden
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_member_of = get_utub_this_user_did_not_create(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app, browser, user_id_for_test, utub_user_member_of.name
    )

    wait_then_click_element(browser, HPL.BUTTON_UTUB_LEAVE, time=3)
    wait_until_visible_css_selector(browser, HPL.HOME_MODAL, timeout=3)

    home_modal = browser.find_element(By.CSS_SELECTOR, HPL.HOME_MODAL)
    x_btn = home_modal.find_element(By.CSS_SELECTOR, HPL.BUTTON_X_CLOSE)
    assert x_btn.is_displayed()
    x_btn.click()

    modal = wait_until_hidden(browser, HPL.BODY_MODAL, timeout=3)
    assert not modal.is_displayed()


def test_dismiss_leave_utub_modal_key(
    browser: WebDriver,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    Tests a UTub user's ability to dismiss the leave UTub modal

    GIVEN a user is a UTub member, and has opened the leave UTub modal
    WHEN the user presses the escape key
    THEN ensure the modal is hidden
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_member_of = get_utub_this_user_did_not_create(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app, browser, user_id_for_test, utub_user_member_of.name
    )

    wait_then_click_element(browser, HPL.BUTTON_UTUB_LEAVE, time=3)
    wait_until_visible_css_selector(browser, HPL.HOME_MODAL, timeout=3)

    home_modal = browser.find_element(By.CSS_SELECTOR, HPL.HOME_MODAL)
    home_modal.send_keys(Keys.ESCAPE)

    modal = wait_until_hidden(browser, HPL.BODY_MODAL, timeout=3)
    assert not modal.is_displayed()


def test_dismiss_leave_utub_modal_click_outside_modal(
    browser: WebDriver,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    Tests a UTub user's ability to dismiss the leave UTub modal

    GIVEN a user is a UTub member, and has opened the leave UTub modal
    WHEN the user clicks outside the modal
    THEN ensure the modal is hidden
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_member_of = get_utub_this_user_did_not_create(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app, browser, user_id_for_test, utub_user_member_of.name
    )

    wait_then_click_element(browser, HPL.BUTTON_UTUB_LEAVE, time=3)
    wait_until_visible_css_selector(browser, HPL.HOME_MODAL, timeout=3)
    dismiss_modal_with_click_out(browser)

    modal = wait_until_hidden(browser, HPL.BODY_MODAL, timeout=3)
    assert not modal.is_displayed()


def test_leave_utub(
    browser: WebDriver,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    Tests a UTub user's ability to leave a UTub.

    GIVEN a user is a UTub member
    WHEN the memberSelfBtnDelete button is selected and user submits the confirm modal
    THEN ensure the user is successfully removed from the UTub.
    """

    app = provide_app
    user_id_for_test = 1
    utub_user_member_of = get_utub_this_user_did_not_create(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app, browser, user_id_for_test, utub_user_member_of.name
    )

    init_num_utubs = get_num_utubs(browser)

    wait_then_click_element(browser, HPL.BUTTON_UTUB_LEAVE, time=3)

    warning_modal_body = wait_then_get_element(browser, HPL.BODY_MODAL)
    assert warning_modal_body is not None

    # Get UTub selector to verify it will be deleted
    utub_css_selector = f'{HPL.SELECTORS_UTUB}[utubid="{utub_user_member_of.id}"]'
    utub_selector = browser.find_element(By.CSS_SELECTOR, utub_css_selector)

    wait_then_click_element(browser, HPL.BUTTON_MODAL_SUBMIT, time=3)
    wait_until_hidden(browser, HPL.BUTTON_MODAL_SUBMIT, timeout=3)
    wait_for_element_to_be_removed(browser, utub_selector)

    # Assert UTub count is one less than before
    assert get_num_utubs(browser) == init_num_utubs - 1

    with pytest.raises(NoSuchElementException):
        browser.find_element(By.CSS_SELECTOR, utub_css_selector)

    # Assert no UTub is selector
    with pytest.raises(NoSuchElementException):
        browser.find_element(By.CSS_SELECTOR, HPL.SELECTOR_SELECTED_UTUB)


def test_cannot_leave_utub_as_utub_creator(
    browser: WebDriver,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN a user is a UTub creator
    WHEN the user tries to leave the UTub
    THEN ensure the leave UTub button is not visible to the user
    """

    app = provide_app
    user_id_for_test = 1
    utub_user_creator_of = get_utub_this_user_created(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app, browser, user_id_for_test, utub_user_creator_of.name
    )

    leave_utub_btn = browser.find_element(By.CSS_SELECTOR, HPL.BUTTON_UTUB_LEAVE)
    assert not leave_utub_btn.is_displayed()
