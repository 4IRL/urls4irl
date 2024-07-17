# External libraries
import pytest
from time import sleep
from selenium.webdriver.common.by import By

# Internal libraries
from src.mocks.mock_constants import (
    MOCK_URL_TITLES,
    MOCK_URL_STRINGS,
)
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.locators import MainPageLocators as MPL
from tests.functional.utils_for_test import (
    login_user,
    select_utub_by_name,
    wait_then_get_element,
    wait_then_get_elements,
)
from tests.functional.urls_ui.utils_for_test_url_ui import create_url


# @pytest.mark.skip(reason="Testing another in isolation")
def test_create_url(browser, create_test_utubs):
    """
    GIVEN a user trying to add a new UTub
    WHEN they submit the addUTub form
    THEN ensure the appropriate input field is shown and in focus
    """

    login_user(browser)

    select_utub_by_name(browser, UTS.TEST_UTUB_NAME_1)

    url_title = MOCK_URL_TITLES[0]
    url_string = MOCK_URL_STRINGS[0]
    create_url(browser, url_title, url_string)

    # Wait for POST request
    sleep(4)

    # Extract URL title and string from new row in URL deck
    url_row = wait_then_get_elements(browser, MPL.ROWS_URLS)[0]
    url_row_title = url_row.find_elements(By.CLASS_NAME, "urlTitle")[0].get_attribute(
        "innerText"
    )
    url_row_string = url_row.find_elements(By.CLASS_NAME, "urlString")[0].get_attribute(
        "innerText"
    )

    assert url_title == url_row_title
    assert url_string == url_row_string
    assert browser.find_element(
        By.CSS_SELECTOR, MPL.BUTTON_ACCESS_ALL_URLS
    ).is_displayed


@pytest.mark.skip(
    reason="Not on happy path. This test tests functionality that is not yet captured on the frontend"
)
def test_create_url_title_length_exceeded(browser, create_test_utubs):
    """
    GIVEN a user trying to add a new UTub
    WHEN they submit the addUTub form
    THEN ensure the appropriate input field is shown and in focus
    """

    login_user(browser)

    create_url(browser, UTS.MAX_CHAR_LIM_URL_TITLE, MOCK_URL_STRINGS[0])

    warning_modal_body = wait_then_get_element(browser, MPL.BODY_MODAL)

    # Assert new UTub is now active and displayed to user
    assert warning_modal_body.text == "Try shortening your UTub name"


@pytest.mark.skip(
    reason="Not on happy path. This test tests functionality that is not yet captured on the frontend"
)
def test_create_url_string_length_exceeded(browser, create_test_utubs):
    """
    GIVEN a user trying to add a new UTub
    WHEN they submit the addUTub form
    THEN ensure the appropriate input field is shown and in focus
    """

    login_user(browser)

    create_url(browser, MOCK_URL_TITLES[0], UTS.MAX_CHAR_LIM_URL_STRING)

    warning_modal_body = wait_then_get_element(browser, "#confirmModalBody")

    # Assert new UTub is now active and displayed to user
    assert warning_modal_body.text == "Try shortening your UTub name"


# @pytest.mark.skip(reason="Testing another in isolation")
def test_activate_url(browser, create_test_urls):
    """
    GIVEN a user trying to add a new UTub
    WHEN they submit the addUTub form
    THEN ensure the appropriate input field is shown and in focus
    """

    login_user(browser)

    select_utub_by_name(browser, UTS.TEST_UTUB_NAME_1)

    # Click first URL to activate
    url_row = wait_then_get_elements(browser, MPL.ROWS_URLS)[0]
    url_row.click()
    assert "true" == url_row.get_attribute("urlselected")
