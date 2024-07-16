# External libraries
from time import sleep
import pytest

# Internal libraries
from src.mocks.mock_constants import MOCK_URL_TITLES
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.urls_ui.utils_for_test_url_ui import delete_url
from tests.functional.utils_for_test import (
    get_url_row_by_title,
    login_user,
    select_utub_by_name,
    wait_then_click_element,
    wait_then_get_element,
)
from locators import MainPageLocators as MPL


# @pytest.mark.skip(reason="Testing another in isolation")
def test_delete_url(browser, create_test_urls):
    """
    GIVEN a user trying to add a new UTub
    WHEN they submit the addUTub form
    THEN ensure the appropriate input field is shown and in focus
    """

    login_user(browser)

    utub_name = UTS.TEST_UTUB_NAME_1
    select_utub_by_name(browser, utub_name)

    url_title = MOCK_URL_TITLES[0]
    url_row = get_url_row_by_title(browser, url_title)
    url_row.click()

    delete_url(browser, url_row)

    warning_modal_body = wait_then_get_element(browser, MPL.BODY_MODAL)
    confirmation_modal_body_text = warning_modal_body.get_attribute("innerText")

    url_delete_check_text = UTS.BODY_MODAL_URL_DELETE

    # Assert warning modal appears with appropriate text
    assert confirmation_modal_body_text == url_delete_check_text

    wait_then_click_element(browser, MPL.BUTTON_MODAL_SUBMIT)

    # Wait for DELETE request
    sleep(4)

    # Assert URL no longer exists in UTub
    assert not get_url_row_by_title(browser, url_title)


@pytest.mark.skip(reason="Test not yet implemented")
def test_delete_last_url(browser, create_test_urls):
    """
    GIVEN a user has one UTub
    WHEN they delete the UTub
    THEN ensure the main page shows appropriate prompts to create a new UTub
    """

    login_user(browser)

    delete_url(browser)

    # Extract confirming result
    selector_UTub1 = wait_then_get_element(browser, MPL.SELECTOR_SELECTED_UTUB)

    # Assert new UTub selector was created with input UTub Name
    assert selector_UTub1.text == MOCK_URL_TITLES[0] + "1"
    # Assert new UTub is now active and displayed to user
    assert "active" in selector_UTub1.get_attribute("class")
