# External libraries
import pytest
from time import sleep

# Internal libraries
from src.mocks.mock_constants import (
    MOCK_UTUB_NAME_BASE,
    MOCK_URL_TITLES,
    MOCK_URL_STRINGS,
)
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.utils_for_test import (
    login_user,
    select_utub_by_name,
    wait_then_get_element,
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

    utub_name = MOCK_UTUB_NAME_BASE + "1"

    select_utub_by_name(browser, utub_name)
    create_url(browser, MOCK_URL_TITLES[0], MOCK_URL_STRINGS[0])

    # Wait for POST request
    sleep(4)

    # Extract URL title and string from new card in URL deck


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

    warning_modal_body = wait_then_get_element(browser, "#confirmModalBody")

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


@pytest.mark.skip(reason="Testing another in isolation")
def test_toggle_url(browser, create_test_urls):
    """
    GIVEN a user trying to add a new UTub
    WHEN they submit the addUTub form
    THEN ensure the appropriate input field is shown and in focus
    """

    login_user(browser)
