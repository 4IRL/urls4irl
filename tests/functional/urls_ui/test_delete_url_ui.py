# Standard library
from time import sleep

# import pytest

# External libraries
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

# Internal libraries
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.urls_ui.utils_for_test_url_ui import delete_all_urls, delete_url
from tests.functional.utils_for_test import (
    get_selected_url,
    login_utub,
    select_url_by_title,
    login_utub_url,
    wait_then_click_element,
    wait_then_get_element,
)
from locators import MainPageLocators as MPL


# @pytest.mark.skip(reason="Testing another in isolation")
def test_delete_url(browser: WebDriver, create_test_urls):
    """
    Tests user's ability to delete a URL

    GIVEN a user, selected UTub and selected URL
    WHEN deleteURL button is selected and confirmation modal confirmed
    THEN ensure the URL is deleted from the UTub
    """

    # Login as test user, select first test UTub, and select first test URL
    url_title = UTS.TEST_URL_TITLE_1
    login_utub_url(browser, url_title=url_title)

    url_row = get_selected_url(browser)
    delete_url(browser, url_row)

    warning_modal_body = wait_then_get_element(browser, MPL.BODY_MODAL)
    confirmation_modal_body_text = warning_modal_body.get_attribute("innerText")

    # Assert warning modal appears with appropriate text
    assert confirmation_modal_body_text == UTS.BODY_MODAL_URL_DELETE

    wait_then_click_element(browser, MPL.BUTTON_MODAL_SUBMIT)

    # Wait for DELETE request
    sleep(4)

    # Assert URL no longer exists in UTub
    assert not select_url_by_title(browser, url_title)


# @pytest.mark.skip(reason="Test not yet implemented")
def test_delete_last_url(browser: WebDriver, create_test_urls):
    """
    Confirms site UI prompts user to create a URL when last URL is deleted.

    GIVEN a user has URLs
    WHEN all URLs are deleted
    THEN ensure the empty UTub prompts user to create a URL.
    """

    login_utub(browser)

    delete_all_urls(browser)

    subheader_url_deck = browser.find_element(By.CSS_SELECTOR, MPL.SUBHEADER_NO_URLS)

    assert subheader_url_deck.is_displayed
    assert subheader_url_deck.get_attribute("innerText") == UTS.MESSAGE_NO_URLS


# @pytest.mark.skip(reason="Not happy path")
def test_delete_url_cancel(browser: WebDriver, create_test_urls):
    """
    Tests user's ability to cancel a URL deletion request.

    GIVEN a user, selected UTub and selected URL
    WHEN deleteURL button is selected and confirmation modal is dismissed
    THEN ensure the URL is not deleted from the UTub
    """

    # Login as test user, select first test UTub, and select first test URL
    url_title = UTS.TEST_URL_TITLE_1
    login_utub_url(browser, url_title=url_title)

    url_row = get_selected_url(browser)
    delete_url(browser, url_row)

    warning_modal_body = wait_then_get_element(browser, MPL.BODY_MODAL)
    confirmation_modal_body_text = warning_modal_body.get_attribute("innerText")

    # Assert warning modal appears with appropriate text
    assert confirmation_modal_body_text == UTS.BODY_MODAL_URL_DELETE

    wait_then_click_element(browser, MPL.BUTTON_MODAL_DISMISS)

    # Pause for modal to clear
    sleep(1)

    # Assert URL still exists in UTub
    assert select_url_by_title(browser, url_title)
