# Standard library
from time import sleep

# External libraries
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

# Internal libraries
from src.mocks.mock_constants import (
    MOCK_URL_STRINGS,
)
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.locators import MainPageLocators as MPL
from tests.functional.utils_for_test import (
    get_selected_url,
    login_utub_url,
    wait_then_get_element,
)
from tests.functional.urls_ui.utils_for_test_url_ui import (
    update_url_title,
    update_url_string,
)


# @pytest.mark.skip(reason="Test complete. Testing another in isolation")
def test_update_url_string(browser: WebDriver, create_test_urls):
    """
    Tests a user's ability to update the URL string of the selected URL.

    GIVEN a user has access to a URL
    WHEN the updateURL form is populated with a new URL
    THEN ensure the URL is updated accordingly
    """

    login_utub_url(browser)

    url_row = get_selected_url(browser)
    url_string = UTS.TEST_URL_STRING_UPDATE
    update_url_string(browser, url_row, url_string)

    # Wait for POST request
    sleep(4)

    # Extract URL string from updated URL row
    url_row_string = url_row.find_element(
        By.CSS_SELECTOR, MPL.URL_STRING_READ
    ).get_attribute("innerText")

    assert url_string == url_row_string
    # Confirm new link target associated with 'Access Link' button
    # Assert new tab opens? Assert new tab URL bar == url_string
    # assert url_string == url_anchor_target


# @pytest.mark.skip(reason="Testing another in isolation")
def test_update_url_title(browser: WebDriver, create_test_urls):
    """
    Tests a user's ability to update the URL title of a selected URL.

    GIVEN a user has access to a URL
    WHEN the updateURL form is populated with a new URL
    THEN ensure the URL is updated accordingly
    """

    login_utub_url(browser)

    url_row = get_selected_url(browser)
    url_title = UTS.TEST_URL_TITLE_UPDATE
    update_url_title(browser, url_row, url_title)

    # Wait for POST request
    sleep(4)

    # Extract URL string from updated URL row
    url_row_title = url_row.find_element(
        By.CSS_SELECTOR, MPL.URL_TITLE_READ
    ).get_attribute("innerText")

    assert url_title == url_row_title


@pytest.mark.skip(
    reason="Not on happy path. This test tests functionality that is not yet captured on the frontend"
)
def test_update_url_title_length_exceeded(browser: WebDriver, create_test_urls):
    """
    GIVEN a user trying to add a new UTub
    WHEN they submit the addUTub form
    THEN ensure the appropriate input field is shown and in focus
    """

    login_utub_url(browser)

    update_url_title(browser, UTS.MAX_CHAR_LIM_URL_TITLE, MOCK_URL_STRINGS[0])

    warning_modal_body = wait_then_get_element(browser, MPL.BODY_MODAL)

    # Assert new UTub is now active and displayed to user
    assert warning_modal_body.text == "Try shortening your UTub name"


@pytest.mark.skip(
    reason="Not on happy path. This test tests functionality that is not yet captured on the frontend"
)
def test_update_url_string_length_exceeded(browser: WebDriver, create_test_urls):
    """
    GIVEN a user trying to add a new UTub
    WHEN they submit the addUTub form
    THEN ensure the appropriate input field is shown and in focus
    """

    login_utub_url(browser)

    update_url_string(browser, MOCK_URL_STRINGS[0], UTS.MAX_CHAR_LIM_URL_STRING)

    warning_modal_body = wait_then_get_element(browser, MPL.BODY_MODAL)

    # Assert new UTub is now active and displayed to user
    assert warning_modal_body.text == "Try shortening your UTub name"
