from flask import Flask
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver

# Internal libraries
from src.cli.mock_constants import (
    MOCK_URL_TITLES,
    MOCK_URL_STRINGS,
)
from src.utils.constants import CONSTANTS
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.utils_for_test import (
    assert_not_visible_css_selector,
    clear_then_send_keys,
    get_selected_url,
    get_url_row_by_id,
    login_user_and_select_utub_by_name,
    login_user_and_select_utub_by_utubid,
    login_user_select_utub_by_name_and_url_by_title,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_hidden,
)
from tests.functional.urls_ui.utils_for_test_url_ui import (
    get_newly_added_utub_url_id_by_url_string,
)
from tests.functional.utubs_ui.utils_for_test_utub_ui import get_utub_this_user_created

pytestmark = pytest.mark.urls_ui


def test_create_url_open_input_no_urls_corner_btn(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    Test that clicking on the + in the URL Deck opens up the new URL input when
    there are no URLs previously generated

    GIVEN a user and selected UTub
    WHEN they submit the addUTub form
    THEN ensure the appropriate input field is shown and in focus
    """
    app = provide_app
    user_id_for_test = 1
    login_user_and_select_utub_by_name(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1
    )

    url_creation_row = browser.find_element(By.CSS_SELECTOR, HPL.WRAP_URL_CREATE)
    assert not url_creation_row.is_displayed()

    wait_then_click_element(browser, HPL.BUTTON_CORNER_URL_CREATE)

    url_creation_row = wait_then_get_element(browser, HPL.WRAP_URL_CREATE)
    assert url_creation_row is not None
    assert url_creation_row.is_displayed()

    assert_not_visible_css_selector(browser, HPL.BUTTON_DECK_URL_CREATE)

    url_title_create_elemnent = browser.find_element(
        By.CSS_SELECTOR, HPL.INPUT_URL_TITLE_CREATE
    )

    assert browser.switch_to.active_element == url_title_create_elemnent


def test_create_url_open_input_no_urls_deck_btn(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    Test that clicking on the 'Add One!' button in the URL Deck opens up the new URL input when
    there are no URLs previously generated

    GIVEN a user and selected UTub
    WHEN they submit the addUTub form
    THEN ensure the appropriate input field is shown and in focus
    """
    app = provide_app
    user_id_for_test = 1
    login_user_and_select_utub_by_name(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1
    )

    url_creation_row = browser.find_element(By.CSS_SELECTOR, HPL.WRAP_URL_CREATE)
    assert not url_creation_row.is_displayed()

    wait_then_click_element(browser, HPL.BUTTON_DECK_URL_CREATE)

    url_creation_row = wait_then_get_element(browser, HPL.WRAP_URL_CREATE)
    assert url_creation_row is not None
    assert url_creation_row.is_displayed()

    assert_not_visible_css_selector(browser, HPL.BUTTON_DECK_URL_CREATE)

    url_title_create_elemnent = browser.find_element(
        By.CSS_SELECTOR, HPL.INPUT_URL_TITLE_CREATE
    )

    assert browser.switch_to.active_element == url_title_create_elemnent


def test_create_url_open_input_with_added_urls(
    browser: WebDriver,
    create_test_utubs,
    create_test_urls,
    provide_app: Flask,
):
    """
    Test that clicking on the + in the URL Deck opens up the new URL input when
    there previously generated URLs

    GIVEN a user and selected UTub
    WHEN click on the + to add a new URL after URLs have already been added
    THEN ensure the appropriate input field is shown and in focus
    """
    app = provide_app
    user_id_for_test = 1
    login_user_and_select_utub_by_name(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1
    )

    url_creation_row = browser.find_element(By.CSS_SELECTOR, HPL.WRAP_URL_CREATE)
    assert not url_creation_row.is_displayed()

    wait_then_click_element(browser, HPL.BUTTON_CORNER_URL_CREATE)

    url_creation_row = wait_then_get_element(browser, HPL.WRAP_URL_CREATE)
    assert url_creation_row is not None
    assert url_creation_row.is_displayed()

    url_title_create_elemnent = browser.find_element(
        By.CSS_SELECTOR, HPL.INPUT_URL_TITLE_CREATE
    )

    assert browser.switch_to.active_element == url_title_create_elemnent


def test_create_url_cancel_input_click_button(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    Tests a user's ability to escape URL creation input by clicking the cancel button

    GIVEN a user attempting to create a URL
    WHEN they are focused on the input  boxes in the URL creation elements and click the cancel button
    THEN ensure the input is closed

    """
    app = provide_app
    user_id_for_test = 1
    login_user_and_select_utub_by_name(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1
    )

    url_creation_row = browser.find_element(By.CSS_SELECTOR, HPL.WRAP_URL_CREATE)
    assert not url_creation_row.is_displayed()

    wait_then_click_element(browser, HPL.BUTTON_CORNER_URL_CREATE)

    url_creation_row = wait_then_get_element(browser, HPL.WRAP_URL_CREATE)
    assert url_creation_row is not None
    assert url_creation_row.is_displayed()

    wait_then_click_element(browser, HPL.BUTTON_URL_CANCEL_CREATE)

    url_creation_row = browser.find_element(By.CSS_SELECTOR, HPL.WRAP_URL_CREATE)
    assert not url_creation_row.is_displayed()


def test_create_url_cancel_input_escape(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    Tests a user's ability to escape URL creation input by using escape key

    GIVEN a user attempting to create a URL
    WHEN they are focused on the input  boxes in the URL creation elements and use the escape key
    THEN ensure the input is closed

    """
    app = provide_app
    user_id_for_test = 1
    login_user_and_select_utub_by_name(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1
    )

    url_creation_row = browser.find_element(By.CSS_SELECTOR, HPL.WRAP_URL_CREATE)
    assert not url_creation_row.is_displayed()

    wait_then_click_element(browser, HPL.BUTTON_CORNER_URL_CREATE)

    url_creation_row = wait_then_get_element(browser, HPL.WRAP_URL_CREATE)
    assert url_creation_row is not None
    assert url_creation_row.is_displayed()

    browser.switch_to.active_element.send_keys(Keys.ESCAPE)

    url_creation_row = browser.find_element(By.CSS_SELECTOR, HPL.WRAP_URL_CREATE)
    assert not url_creation_row.is_displayed()


def test_create_url_submit_btn(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    Tests a user's ability to create a new URL in a selected UTub

    GIVEN a user and selected UTub
    WHEN they submit a new URL using the submit button
    THEN ensure the URL is added, input is hidden, and access all URLs button is shown
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)

    login_user_and_select_utub_by_utubid(
        app, browser, user_id_for_test, utub_user_created.id
    )

    url_title = MOCK_URL_TITLES[0]
    url_string = MOCK_URL_STRINGS[0]

    wait_then_click_element(browser, HPL.BUTTON_CORNER_URL_CREATE)

    url_creation_row = wait_then_get_element(browser, HPL.WRAP_URL_CREATE)
    assert url_creation_row is not None
    assert url_creation_row.is_displayed()

    # Input new URL Title
    url_title_input_field = wait_then_get_element(browser, HPL.INPUT_URL_TITLE_CREATE)
    assert url_title_input_field is not None
    clear_then_send_keys(url_title_input_field, url_title)

    # Input new URL String
    url_string_input_field = wait_then_get_element(browser, HPL.INPUT_URL_STRING_CREATE)
    assert url_string_input_field is not None
    clear_then_send_keys(url_string_input_field, url_string)

    wait_then_click_element(browser, HPL.BUTTON_URL_SUBMIT_CREATE, time=3)

    # Wait for HTTP request to complete
    wait_until_hidden(browser, HPL.INPUT_URL_STRING_CREATE, timeout=3)
    url_creation_row = browser.find_element(By.CSS_SELECTOR, HPL.WRAP_URL_CREATE)
    assert not url_creation_row.is_displayed()

    # Extract URL title and string from new row in URL deck
    utub_url_id = get_newly_added_utub_url_id_by_url_string(
        app, utub_user_created.id, url_string
    )
    url_row = get_url_row_by_id(browser, utub_url_id)
    assert url_row is not None

    url_row_title = url_row.find_element(By.CSS_SELECTOR, HPL.URL_TITLE_READ).text
    url_row_string = url_row.find_element(By.CSS_SELECTOR, HPL.URL_STRING_READ).text

    assert url_title == url_row_title
    assert url_string == url_row_string

    assert browser.find_element(
        By.CSS_SELECTOR, HPL.BUTTON_ACCESS_ALL_URLS
    ).is_displayed()


def test_create_url_using_enter_key(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    Tests a user's ability to create a new URL in a selected UTub

    GIVEN a user and selected UTub
    WHEN they submit a new URL using the submit button
    THEN ensure the URL is added, input is hidden, and access all URLs button is shown
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)

    login_user_and_select_utub_by_utubid(
        app, browser, user_id_for_test, utub_user_created.id
    )

    url_title = MOCK_URL_TITLES[0]
    url_string = MOCK_URL_STRINGS[0]

    wait_then_click_element(browser, HPL.BUTTON_CORNER_URL_CREATE)

    url_creation_row = wait_then_get_element(browser, HPL.WRAP_URL_CREATE)
    assert url_creation_row is not None
    assert url_creation_row.is_displayed()

    # Input new URL Title
    url_title_input_field = wait_then_get_element(browser, HPL.INPUT_URL_TITLE_CREATE)
    assert url_title_input_field is not None
    clear_then_send_keys(url_title_input_field, url_title)

    # Input new URL String
    url_string_input_field = wait_then_get_element(browser, HPL.INPUT_URL_STRING_CREATE)
    assert url_string_input_field is not None
    clear_then_send_keys(url_string_input_field, url_string)

    browser.switch_to.active_element.send_keys(Keys.ENTER)

    # Wait for HTTP request to complete
    wait_until_hidden(browser, HPL.INPUT_URL_STRING_CREATE, timeout=3)
    url_creation_row = browser.find_element(By.CSS_SELECTOR, HPL.WRAP_URL_CREATE)
    assert not url_creation_row.is_displayed()

    # Extract URL title and string from new row in URL deck
    utub_url_id = get_newly_added_utub_url_id_by_url_string(
        app, utub_user_created.id, url_string
    )
    url_row = get_url_row_by_id(browser, utub_url_id)
    assert url_row is not None

    url_row_title = url_row.find_element(By.CSS_SELECTOR, HPL.URL_TITLE_READ).text
    url_row_string = url_row.find_element(By.CSS_SELECTOR, HPL.URL_STRING_READ).text

    assert url_title == url_row_title
    assert url_string == url_row_string

    assert browser.find_element(
        By.CSS_SELECTOR, HPL.BUTTON_ACCESS_ALL_URLS
    ).is_displayed()


def test_create_url_title_length_exceeded(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    Tests the site error response to a user's attempt to create a new URL with a title that exceeds the maximum character length limit.

    GIVEN a user and selected UTub
    WHEN the createURL form is populated and submitted with a title that exceeds character limits
    THEN ensure the appropriate error and prompt is shown to user.
    """

    # Login test user and select first test UTub
    app = provide_app

    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    login_user_and_select_utub_by_utubid(
        app, browser, user_id_for_test, utub_user_created.id
    )

    wait_then_click_element(browser, HPL.BUTTON_CORNER_URL_CREATE)

    url_creation_row = wait_then_get_element(browser, HPL.WRAP_URL_CREATE)
    assert url_creation_row is not None
    assert url_creation_row.is_displayed()

    # Input new URL Title
    url_title_input_field = wait_then_get_element(browser, HPL.INPUT_URL_TITLE_CREATE)
    assert url_title_input_field is not None
    clear_then_send_keys(
        url_title_input_field, "a" * CONSTANTS.URLS.MAX_URL_TITLE_LENGTH
    )

    create_url_title_input = wait_then_get_element(
        browser, HPL.INPUT_URL_TITLE_CREATE, time=3
    )
    assert create_url_title_input is not None
    new_url_title = create_url_title_input.get_attribute("value")
    assert new_url_title is not None

    assert len(new_url_title) == CONSTANTS.URLS.MAX_URL_TITLE_LENGTH


def test_select_url(browser: WebDriver, create_test_urls, provide_app: Flask):
    """
    Tests a user's ability to select a URL and see more details

    GIVEN a user trying to add a new UTub
    WHEN they submit the addUTub form
    THEN ensure the appropriate input field is shown and in focus
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    login_user_select_utub_by_name_and_url_by_title(
        app, browser, user_id_for_test, utub_user_created.name, UTS.TEST_URL_TITLE_1
    )

    url_row = get_selected_url(browser)

    assert "true" == url_row.get_attribute("urlselected")
    assert url_row.find_element(By.CSS_SELECTOR, HPL.URL_TAGS_READ).is_displayed()
    assert url_row.find_element(
        By.CSS_SELECTOR, HPL.URL_BUTTONS_OPTIONS_READ
    ).is_displayed()
    url_string = url_row.find_element(By.CSS_SELECTOR, HPL.URL_STRING_READ)
    assert url_string.get_attribute(HPL.URL_STRING_IN_DATA) in MOCK_URL_STRINGS


# TODO: Check url title sanitization for sad path tests
# TODO Check invalid CSRF token for sad path tests
