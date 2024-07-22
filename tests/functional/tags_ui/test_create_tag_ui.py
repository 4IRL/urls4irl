# External libraries
import pytest
from time import sleep
from selenium.webdriver.common.by import By

# Internal libraries
from src.mocks.mock_constants import (
    MOCK_URL_TITLES,
    MOCK_URL_STRINGS,
)
from src.utils.strings.tag_strs import FIVE_TAGS_MAX
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.locators import MainPageLocators as MPL
from tests.functional.tags_ui.utils_for_test_tag_ui import create_tag
from tests.functional.utils_for_test import (
    get_selected_url,
    get_tag_badge_by_name,
    get_tag_filter_by_name,
    login_utub_url,
    select_url_by_title,
    login_user,
    select_utub_by_name,
    wait_then_get_element,
)
from tests.functional.urls_ui.utils_for_test_url_ui import create_url


# @pytest.mark.skip(reason="Testing another in isolation")
def test_create_tag(browser, create_test_urls):
    """
    Tests a user's ability to create a tag to a URL.

    GIVEN a user has access to UTubs with URLs
    WHEN the createTag form is populated with a tag value that is not yet present and submitted
    THEN ensure the appropriate tag is applied and displayed
    """

    login_utub_url(browser)

    url_row = get_selected_url(browser, UTS.TEST_URL_TITLE)

    tag_text = UTS.TEST_TAG_1
    create_tag(browser, url_row, tag_text)

    # Wait for POST request
    sleep(4)

    # Confirm tag badge added to URL
    # Extract tag text from newly created badge
    tag_badge = get_tag_badge_by_name(url_row, tag_text)
    url_row_tag_text = tag_badge.find_element(By.CLASS_NAME, "tagText").get_attribute(
        "innerText"
    )

    assert tag_text == url_row_tag_text

    # Confirm tag displayed in Tag Deck
    # Extract tag text from newly created filter
    tag_filter = get_tag_filter_by_name(browser, tag_text)
    tag_filter_text = tag_filter.find_element(By.CLASS_NAME, "tagText").get_attribute(
        "innerText"
    )

    assert tag_text == tag_filter_text


@pytest.mark.skip(reason="Not on happy path. Not yet implemented")
def test_create_existing_tag(browser, create_test_tags):
    """
    Tests the site error response to a user's attempt to create a tag with the same name as another already on the selected URL.

    GIVEN a user has access to UTubs with URLs and tags applied
    WHEN the createTag form is populated with a tag value that is already applied to the selected URL and submitted
    THEN ensure the appropriate error is presented to the user.
    """

    login_utub_url(browser)

    create_url(browser, UTS.MAX_CHAR_LIM_URL_TITLE, MOCK_URL_STRINGS[0])

    warning_modal_body = wait_then_get_element(browser, MPL.BODY_MODAL)

    # Assert new UTub is now active and displayed to user
    assert warning_modal_body.text == "Try shortening your UTub name"


# @pytest.mark.skip(
#     reason="Not on happy path."
# )
def test_create_sixth_tag(browser, create_test_tags):
    """
    Tests the site error response to a user's attempt to create an additional unique tag once a URL already has the maximum number of tags applied

    GIVEN a user has access to UTubs with URLs and a maximum of tags applied
    WHEN the createTag form is populated and submitted
    THEN ensure the appropriate error is presented to the user.
    """
    login_user(browser)

    select_utub_by_name(browser, UTS.TEST_UTUB_NAME_1)

    url_row = select_url_by_title(browser, UTS.TEST_URL_TITLE)

    tag_text = UTS.TEST_TAG_NEW
    create_tag(browser, url_row, tag_text)

    # Wait for POST request
    sleep(4)

    tag_error = wait_then_get_element(browser, MPL.ERROR_TAG_CREATE)

    # Assert error text is displayed
    assert "visible" in tag_error.get_attribute("class")
    assert tag_error.text == FIVE_TAGS_MAX


@pytest.mark.skip(reason="Not on happy path. Not yet implemented")
def test_create_tag_text_length_exceeded(browser, create_test_urls):
    """
    Tests the site error response to a user's attempt to create a tag with name that exceeds the character limit.

    GIVEN a user has access to UTubs with URLs
    WHEN the createTag form is populated nd submitted with a tag value that exceeds character limits
    THEN ensure the appropriate error is presented to the user.
    """

    login_utub_url(browser)

    create_url(browser, MOCK_URL_TITLES[0], UTS.MAX_CHAR_LIM_URL_STRING)

    warning_modal_body = wait_then_get_element(browser, "#confirmModalBody")

    # Assert new UTub is now active and displayed to user
    assert warning_modal_body.text == "Try shortening your UTub name"
