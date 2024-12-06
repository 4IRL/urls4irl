# External libraries
import random
from typing import Tuple
from flask.testing import FlaskCliRunner
import pytest
from flask import Flask
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver

# Internal libraries
from src.mocks.mock_constants import MOCK_URL_STRINGS
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.urls_ui.utils_for_test_url_ui import (
    login_select_utub_select_url_click_delete_get_modal_url,
)
from tests.functional.utils_for_test import (
    add_mock_urls,
    dismiss_modal_with_click_out,
    get_num_url_rows,
    verify_elem_with_url_string_exists,
    wait_for_element_to_be_removed,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_hidden,
)
from locators import MainPageLocators as MPL

pytestmark = pytest.mark.urls_ui


def test_delete_url_submit(
    browser: WebDriver, create_test_urls, provide_app_for_session_generation: Flask
):
    """
    Tests user's ability to delete a URL

    GIVEN a user, selected UTub and selected URL
    WHEN deleteURL button is selected and confirmation modal confirmed
    THEN ensure the URL is deleted from the UTub
    """
    user_id_for_test = 1

    # Login as test user, select first test UTub, and select first test URL
    delete_modal, url_elem_to_delete = (
        login_select_utub_select_url_click_delete_get_modal_url(
            browser=browser,
            app=provide_app_for_session_generation,
            user_id=user_id_for_test,
            utub_name=UTS.TEST_UTUB_NAME_1,
            url_string=UTS.TEST_URL_STRING_CREATE,
        )
    )

    css_selector = f'{MPL.URL_STRING_READ}[data-url="{UTS.TEST_URL_STRING_CREATE}"]'
    assert browser.find_element(By.CSS_SELECTOR, css_selector)

    init_num_url_rows = get_num_url_rows(browser)

    confirmation_modal_body_text = delete_modal.get_attribute("innerText")

    # Assert warning modal appears with appropriate text
    assert confirmation_modal_body_text == UTS.BODY_MODAL_URL_DELETE

    wait_then_click_element(browser, MPL.BUTTON_MODAL_SUBMIT)
    wait_until_hidden(browser, MPL.BUTTON_MODAL_SUBMIT)

    # Wait for animation to complete
    assert wait_for_element_to_be_removed(browser, url_elem_to_delete)

    # Assert URL no longer exists in UTub
    with pytest.raises(NoSuchElementException):
        browser.find_element(By.CSS_SELECTOR, css_selector)
    assert init_num_url_rows - 1 == get_num_url_rows(browser)


def test_delete_url_cancel_click_cancel_btn(
    browser: WebDriver, create_test_urls, provide_app_for_session_generation: Flask
):
    """
    Tests user's ability to delete a URL

    GIVEN a user, selected UTub and selected URL
    WHEN deleteURL button is selected and confirmation modal is cancelled by clicking the cancel btn
    THEN ensure the URL is not deleted from the UTub, and the modal is hidden
    """
    user_id_for_test = 1

    # Login as test user, select first test UTub, and select first test URL
    delete_modal, url_elem_to_delete = (
        login_select_utub_select_url_click_delete_get_modal_url(
            browser=browser,
            app=provide_app_for_session_generation,
            user_id=user_id_for_test,
            utub_name=UTS.TEST_UTUB_NAME_1,
            url_string=UTS.TEST_URL_STRING_CREATE,
        )
    )

    init_num_url_rows = get_num_url_rows(browser)

    confirmation_modal_body_text = delete_modal.get_attribute("innerText")

    # Assert warning modal appears with appropriate text
    assert confirmation_modal_body_text == UTS.BODY_MODAL_URL_DELETE

    wait_then_click_element(browser, MPL.BUTTON_MODAL_DISMISS)
    wait_until_hidden(browser, MPL.BUTTON_MODAL_DISMISS)

    # Assert URL no longer exists in UTub
    assert verify_elem_with_url_string_exists(browser, UTS.TEST_URL_STRING_CREATE)
    assert init_num_url_rows == get_num_url_rows(browser)
    assert url_elem_to_delete.is_displayed()


def test_delete_url_cancel_click_x_btn(
    browser: WebDriver, create_test_urls, provide_app_for_session_generation: Flask
):
    """
    Tests user's ability to delete a URL

    GIVEN a user, selected UTub and selected URL
    WHEN deleteURL button is selected and confirmation modal is cancelled by clicking the x btn
    THEN ensure the URL is not deleted from the UTub, and the modal is hidden
    """
    user_id_for_test = 1

    # Login as test user, select first test UTub, and select first test URL
    delete_modal, url_elem_to_delete = (
        login_select_utub_select_url_click_delete_get_modal_url(
            browser=browser,
            app=provide_app_for_session_generation,
            user_id=user_id_for_test,
            utub_name=UTS.TEST_UTUB_NAME_1,
            url_string=UTS.TEST_URL_STRING_CREATE,
        )
    )

    init_num_url_rows = get_num_url_rows(browser)

    confirmation_modal_body_text = delete_modal.get_attribute("innerText")

    # Assert warning modal appears with appropriate text
    assert confirmation_modal_body_text == UTS.BODY_MODAL_URL_DELETE

    wait_then_click_element(browser, MPL.BUTTON_X_CLOSE)
    wait_until_hidden(browser, MPL.BUTTON_X_CLOSE)

    # Assert URL no longer exists in UTub
    assert verify_elem_with_url_string_exists(browser, UTS.TEST_URL_STRING_CREATE)
    assert init_num_url_rows == get_num_url_rows(browser)
    assert url_elem_to_delete.is_displayed()


def test_delete_url_cancel_press_esc_key(
    browser: WebDriver, create_test_urls, provide_app_for_session_generation: Flask
):
    """
    Tests user's ability to delete a URL

    GIVEN a user, selected UTub and selected URL
    WHEN deleteURL button is selected and confirmation modal is cancelled by pressing esc key
    THEN ensure the URL is not deleted from the UTub, and the modal is hidden
    """
    user_id_for_test = 1

    # Login as test user, select first test UTub, and select first test URL
    delete_modal, url_elem_to_delete = (
        login_select_utub_select_url_click_delete_get_modal_url(
            browser=browser,
            app=provide_app_for_session_generation,
            user_id=user_id_for_test,
            utub_name=UTS.TEST_UTUB_NAME_1,
            url_string=UTS.TEST_URL_STRING_CREATE,
        )
    )

    init_num_url_rows = get_num_url_rows(browser)

    confirmation_modal_body_text = delete_modal.get_attribute("innerText")

    # Assert warning modal appears with appropriate text
    assert confirmation_modal_body_text == UTS.BODY_MODAL_URL_DELETE

    browser.switch_to.active_element.send_keys(Keys.ESCAPE)
    wait_until_hidden(browser, MPL.BUTTON_X_CLOSE)

    # Assert URL no longer exists in UTub
    assert verify_elem_with_url_string_exists(browser, UTS.TEST_URL_STRING_CREATE)
    assert init_num_url_rows == get_num_url_rows(browser)
    assert url_elem_to_delete.is_displayed()


def test_delete_url_cancel_click_outside_modal(
    browser: WebDriver, create_test_urls, provide_app_for_session_generation: Flask
):
    """
    Tests user's ability to delete a URL

    GIVEN a user, selected UTub and selected URL
    WHEN deleteURL button is selected and confirmation modal is cancelled by clicking outside the modal
    THEN ensure the URL is not deleted from the UTub, and the modal is hidden
    """
    user_id_for_test = 1

    # Login as test user, select first test UTub, and select first test URL
    delete_modal, url_elem_to_delete = (
        login_select_utub_select_url_click_delete_get_modal_url(
            browser=browser,
            app=provide_app_for_session_generation,
            user_id=user_id_for_test,
            utub_name=UTS.TEST_UTUB_NAME_1,
            url_string=UTS.TEST_URL_STRING_CREATE,
        )
    )

    init_num_url_rows = get_num_url_rows(browser)

    confirmation_modal_body_text = delete_modal.get_attribute("innerText")

    # Assert warning modal appears with appropriate text
    assert confirmation_modal_body_text == UTS.BODY_MODAL_URL_DELETE

    dismiss_modal_with_click_out(browser)
    wait_until_hidden(browser, MPL.BUTTON_X_CLOSE)

    # Assert URL still exists in UTub
    assert verify_elem_with_url_string_exists(browser, UTS.TEST_URL_STRING_CREATE)
    assert init_num_url_rows == get_num_url_rows(browser)
    assert url_elem_to_delete.is_displayed()


def test_delete_last_url(
    browser: WebDriver,
    runner: Tuple[Flask, FlaskCliRunner],
    create_test_utubs,
    provide_app_for_session_generation: Flask,
):
    """
    Confirms site UI prompts user to create a URL when last URL is deleted.

    GIVEN a user has URLs
    WHEN all URLs are deleted
    THEN ensure the empty UTub prompts user to create a URL.
    """
    _, cli_runner = runner

    random_url_to_add_as_last = random.sample(MOCK_URL_STRINGS, 1)[0]

    add_mock_urls(
        cli_runner,
        [
            random_url_to_add_as_last,
        ],
    )

    user_id_for_test = 1

    # Login as test user, select first test UTub, and select first test URL
    _, url_elem_to_delete = login_select_utub_select_url_click_delete_get_modal_url(
        browser=browser,
        app=provide_app_for_session_generation,
        user_id=user_id_for_test,
        utub_name=UTS.TEST_UTUB_NAME_1,
        url_string=random_url_to_add_as_last,
    )

    css_selector = f'{MPL.URL_STRING_READ}[data-url="{random_url_to_add_as_last}"]'
    assert browser.find_element(By.CSS_SELECTOR, css_selector)

    wait_then_click_element(browser, MPL.BUTTON_MODAL_SUBMIT)
    wait_until_hidden(browser, MPL.BUTTON_MODAL_SUBMIT)
    assert wait_for_element_to_be_removed(browser, url_elem_to_delete)
    with pytest.raises(NoSuchElementException):
        browser.find_element(By.CSS_SELECTOR, css_selector)

    no_url_subheader = wait_then_get_element(browser, MPL.SUBHEADER_NO_URLS)
    assert no_url_subheader is not None
