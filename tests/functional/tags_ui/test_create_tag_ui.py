# Standard library
from time import sleep

# External libraries
import pytest
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver

# Internal libraries
from src.cli.mock_constants import (
    MOCK_URL_TITLES,
    MOCK_URL_STRINGS,
)
from src.utils.strings.tag_strs import FIVE_TAGS_MAX
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.tags_ui.utils_for_test_tag_ui import create_tag
from tests.functional.utils_for_test import (
    get_selected_url,
    get_tag_badge_by_name,
    get_tag_filter_by_name,
    login_utub_url,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_hidden,
)
from tests.functional.urls_ui.utils_for_test_url_ui import create_url

pytestmark = pytest.mark.tags_ui


def test_open_input_create_tag(browser: WebDriver, create_test_urls):
    """
    Tests a UTub member's ability to open the create tag input field on a given URL.

    GIVEN a user is a UTub member with the UTub selected
    WHEN the user selects a URL, and clicks the 'Add Tag' button
    THEN ensure the createTag form is opened.
    """
    login_utub_url(browser)

    selected_url_row = get_selected_url(browser)
    create_tag(browser, selected_url_row)


def test_cancel_input_create_tag_btn(browser: WebDriver, create_test_urls):
    """
    Tests a UTub owner's ability to close the create tag input field.

    GIVEN a user is the UTub owner with the UTub selected
    WHEN the user clicks the createMember plus button, then clicks the x button
    THEN ensure the createMember form is not shown.
    """
    login_utub_url(browser)

    selected_url_row = get_selected_url(browser)
    create_tag(browser, selected_url_row)

    wait_then_click_element(browser, HPL.BUTTON_TAG_CANCEL_CREATE)

    create_tag_input = wait_until_hidden(browser, HPL.INPUT_MEMBER_CREATE)

    assert not create_tag_input.is_displayed()


def test_cancel_input_create_tag_key(browser: WebDriver, create_test_urls):
    """
    Tests a UTub owner's ability to close the create member input field.

    GIVEN a user is the UTub owner with the UTub selected
    WHEN the user clicks the createMember plus button, then presses the esc key
    THEN ensure the createMember form is not shown.
    """
    login_utub_url(browser)

    selected_url_row = get_selected_url(browser)
    create_tag(browser, selected_url_row)

    browser.switch_to.active_element.send_keys(Keys.ESCAPE)

    create_tag_input = wait_until_hidden(browser, HPL.INPUT_MEMBER_CREATE)

    assert not create_tag_input.is_displayed()


# @pytest.mark.skip(reason="Testing another in isolation")
def test_create_tag_btn(browser: WebDriver, create_test_urls):
    """
    Tests a user's ability to create a tag to a URL.

    GIVEN a user has access to UTubs with URLs
    WHEN the createTag form is populated with a tag value that is not yet present and submitted
    THEN ensure the appropriate tag is applied and displayed
    """

    login_utub_url(browser)

    selected_url_row = get_selected_url(browser)
    tag_text = UTS.TEST_TAG_NAME_1

    create_tag(browser, selected_url_row, tag_text)

    # Submit
    wait_then_click_element(browser, HPL.BUTTON_TAG_SUBMIT_CREATE)

    # Wait for POST request
    sleep(4)

    # Confirm tag badge added to URL

    tag_badge = get_tag_badge_by_name(selected_url_row, tag_text)

    assert tag_badge.tag_name == "span"

    # Confirm tag displayed in Tag Deck
    # Extract tag text from newly created filter
    tag_filter = get_tag_filter_by_name(browser, tag_text)

    assert tag_filter.tag_name == "div"


# @pytest.mark.skip(reason="Testing another in isolation")
def test_create_tag_key(browser: WebDriver, create_test_urls):
    """
    Tests a user's ability to create a tag to a URL.

    GIVEN a user has access to UTubs with URLs
    WHEN the createTag form is populated with a tag value that is not yet present and submitted
    THEN ensure the appropriate tag is applied and displayed
    """

    login_utub_url(browser)

    selected_url_row = get_selected_url(browser)
    tag_text = UTS.TEST_TAG_NAME_1

    create_tag(browser, selected_url_row, tag_text)

    # Submit
    browser.switch_to.active_element.send_keys(Keys.ENTER)

    # Wait for POST request
    sleep(4)

    # Confirm tag badge added to URL

    tag_badge = get_tag_badge_by_name(selected_url_row, tag_text)

    assert tag_badge.tag_name == "span"

    # Confirm tag displayed in Tag Deck
    # Extract tag text from newly created filter
    tag_filter = get_tag_filter_by_name(browser, tag_text)

    assert tag_filter.tag_name == "div"


@pytest.mark.skip(reason="Not on happy path. Not yet implemented")
def test_create_existing_tag(browser: WebDriver, create_test_tags):
    """
    Tests the site error response to a user's attempt to create a tag with the same name as another already on the selected URL.

    GIVEN a user has access to UTubs with URLs and tags applied
    WHEN the createTag form is populated with a tag value that is already applied to the selected URL and submitted
    THEN ensure the appropriate error is presented to the user.
    """

    login_utub_url(browser)

    create_url(browser, UTS.MAX_CHAR_LIM_URL_TITLE, MOCK_URL_STRINGS[0])

    warning_modal_body = wait_then_get_element(browser, HPL.BODY_MODAL)

    # Assert new UTub is now active and displayed to user
    assert warning_modal_body.text == "Try shortening your UTub name"


@pytest.mark.skip(reason="Not on happy path.")
def test_create_sixth_tag(browser: WebDriver, create_test_tags):
    """
    Tests the site error response to a user's attempt to create an additional unique tag once a URL already has the maximum number of tags applied

    GIVEN a user has access to UTubs with URLs and a maximum of tags applied
    WHEN the createTag form is populated and submitted
    THEN ensure the appropriate error is presented to the user.
    """
    login_utub_url(browser)

    selected_url_row = get_selected_url(browser)
    tag_text = UTS.TEST_TAG_NAME_1

    create_tag(browser, selected_url_row, tag_text)

    # Submit
    wait_then_click_element(browser, HPL.BUTTON_TAG_SUBMIT_CREATE)

    # Wait for POST request
    sleep(4)

    tag_error = wait_then_get_element(browser, HPL.ERROR_TAG_CREATE)

    # Assert error text is displayed
    assert "visible" in tag_error.get_attribute("class")
    assert tag_error.text == FIVE_TAGS_MAX


@pytest.mark.skip(reason="Not on happy path. Not yet implemented")
def test_create_tag_text_length_exceeded(browser: WebDriver, create_test_urls):
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
