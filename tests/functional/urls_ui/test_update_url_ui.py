# Standard library
import pytest
from time import sleep

# External libraries
from selenium.webdriver.common.by import By

# Internal libraries
from src.mocks.mock_constants import (
    MOCK_URL_STRINGS,
)
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.locators import MainPageLocators as MPL
from tests.functional.utils_for_test import (
    login_user,
    get_url_row_by_title,
    select_utub_by_name,
    wait_then_get_element,
)
from tests.functional.urls_ui.utils_for_test_url_ui import (
    update_url_title,
    update_url_string,
)


@pytest.mark.skip(reason="Test complete. Testing another in isolation")
def test_update_url_string(browser, create_test_urls):
    """
    GIVEN a user has access to a URL
    WHEN they submit the updateURL form
    THEN ensure the URL is updated accordingly
    """

    login_user(browser)

    select_utub_by_name(browser, UTS.TEST_UTUB_NAME_1)

    url_string = UTS.TEST_URL_STRING_UPDATE

    url_row = get_url_row_by_title(browser, UTS.TEST_URL_TITLE)
    url_row.click()
    update_url_string(browser, url_row, url_string)

    # Wait for POST request
    sleep(4)

    # Extract URL string from updated URL row
    url_row_string = url_row.find_element(By.CLASS_NAME, "urlString").get_attribute(
        "innerText"
    )
    url_row.find_element(By.CLASS_NAME, "urlBtnAccess").click()

    assert url_string == url_row_string
    # Confirm new link target associated with 'Access Link' button
    # Assert new tab opens? Assert new tab URL bar == url_string
    # assert url_string == url_anchor_target


# @pytest.mark.skip(reason="Testing another in isolation")
def test_update_url_title(browser, create_test_urls):
    """
    GIVEN a user trying to add a new UTub
    WHEN they submit the addUTub form
    THEN ensure the appropriate input field is shown and in focus
    """

    login_user(browser)

    select_utub_by_name(browser, UTS.TEST_UTUB_NAME_1)

    url_title = UTS.TEST_URL_TITLE_UPDATE

    url_row = get_url_row_by_title(browser, UTS.TEST_URL_TITLE)
    url_row.click()
    update_url_title(browser, url_row, url_title)

    # Wait for POST request
    sleep(4)

    # Extract URL string from updated URL row
    url_row_title = url_row.find_element(By.CLASS_NAME, "urlTitle").get_attribute(
        "innerText"
    )

    assert url_title == url_row_title


@pytest.mark.skip(
    reason="Not on happy path. This test tests functionality that is not yet captured on the frontend"
)
def test_update_url_title_length_exceeded(browser, create_test_utubs):
    """
    GIVEN a user trying to add a new UTub
    WHEN they submit the addUTub form
    THEN ensure the appropriate input field is shown and in focus
    """

    login_user(browser)

    update_url_title(browser, UTS.MAX_CHAR_LIM_URL_TITLE, MOCK_URL_STRINGS[0])

    warning_modal_body = wait_then_get_element(browser, MPL.BODY_MODAL)

    # Assert new UTub is now active and displayed to user
    assert warning_modal_body.text == "Try shortening your UTub name"


@pytest.mark.skip(
    reason="Not on happy path. This test tests functionality that is not yet captured on the frontend"
)
def test_update_url_string_length_exceeded(browser, create_test_utubs):
    """
    GIVEN a user trying to add a new UTub
    WHEN they submit the addUTub form
    THEN ensure the appropriate input field is shown and in focus
    """

    login_user(browser)

    update_url_string(browser, MOCK_URL_STRINGS[0], UTS.MAX_CHAR_LIM_URL_STRING)

    warning_modal_body = wait_then_get_element(browser, "#confirmModalBody")

    # Assert new UTub is now active and displayed to user
    assert warning_modal_body.text == "Try shortening your UTub name"
