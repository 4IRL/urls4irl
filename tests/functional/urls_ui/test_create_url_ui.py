from flask import Flask
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver

from src.cli.mock_constants import (
    MOCK_URL_TITLES,
    MOCK_URL_STRINGS,
)
from src.models.users import Users
from src.models.utub_urls import Utub_Urls
from src.utils.constants import CONSTANTS
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from src.utils.strings.url_strs import URL_FAILURE
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.utils_for_test import (
    assert_login_with_username,
    assert_not_visible_css_selector,
    assert_visited_403_on_invalid_csrf_and_reload,
    clear_then_send_keys,
    get_url_row_by_id,
    get_utub_this_user_created,
    invalidate_csrf_token_on_page,
    login_user_and_select_utub_by_name,
    login_user_and_select_utub_by_utubid,
    verify_url_coloring_is_correct,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_hidden,
    wait_until_visible_css_selector,
)
from tests.functional.urls_ui.utils_for_test_url_ui import (
    add_invalid_url_header_for_ui_test,
    create_url,
    fill_create_url_form,
    get_newly_added_utub_url_id_by_url_string,
)

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

    fill_create_url_form(browser, url_title, url_string)
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

    verify_url_coloring_is_correct(browser)


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

    fill_create_url_form(browser, url_title, url_string)
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

    verify_url_coloring_is_correct(browser)


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
        url_title_input_field, "a" * (CONSTANTS.URLS.MAX_URL_TITLE_LENGTH + 1)
    )

    create_url_title_input = wait_then_get_element(
        browser, HPL.INPUT_URL_TITLE_CREATE, time=3
    )
    assert create_url_title_input is not None
    new_url_title = create_url_title_input.get_attribute("value")
    assert new_url_title is not None

    assert len(new_url_title) == CONSTANTS.URLS.MAX_URL_TITLE_LENGTH


def test_create_url_empty_fields(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    Tests the site error response to a user's attempt to create a new URL with empty fields.

    GIVEN a user and selected UTub
    WHEN the createURL form is submitted empty
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

    # Submit URL
    wait_then_click_element(browser, HPL.BUTTON_URL_SUBMIT_CREATE, time=3)

    invalid_url_title_error = wait_then_get_element(
        browser, HPL.INPUT_URL_TITLE_CREATE + HPL.INVALID_FIELD_SUFFIX, time=3
    )
    assert invalid_url_title_error is not None
    assert invalid_url_title_error.text == URL_FAILURE.FIELD_REQUIRED_STR

    invalid_url_string_error = wait_then_get_element(
        browser, HPL.INPUT_URL_STRING_CREATE + HPL.INVALID_FIELD_SUFFIX, time=3
    )
    assert invalid_url_string_error is not None
    assert invalid_url_string_error.text == URL_FAILURE.FIELD_REQUIRED_STR


def test_create_url_empty_title(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    Tests the site error response to a user's attempt to create a new URL with an empty URL title.

    GIVEN a user and selected UTub
    WHEN the createURL form is submitted with an empty URL title
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

    url_string_input_field = wait_then_get_element(browser, HPL.INPUT_URL_STRING_CREATE)
    assert url_string_input_field is not None
    clear_then_send_keys(url_string_input_field, MOCK_URL_STRINGS[0])

    # Submit URL
    wait_then_click_element(browser, HPL.BUTTON_URL_SUBMIT_CREATE, time=3)

    invalid_url_title_error = wait_then_get_element(
        browser, HPL.INPUT_URL_TITLE_CREATE + HPL.INVALID_FIELD_SUFFIX, time=3
    )
    assert invalid_url_title_error is not None
    assert invalid_url_title_error.text == URL_FAILURE.FIELD_REQUIRED_STR


def test_create_url_empty_string(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    Tests the site error response to a user's attempt to create a new URL with an empty URL string.

    GIVEN a user and selected UTub
    WHEN the createURL form is submitted with an empty URL string
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

    url_title_input_field = wait_then_get_element(browser, HPL.INPUT_URL_TITLE_CREATE)
    assert url_title_input_field is not None
    clear_then_send_keys(url_title_input_field, "Testing")

    # Submit URL
    wait_then_click_element(browser, HPL.BUTTON_URL_SUBMIT_CREATE, time=3)

    invalid_url_string_error = wait_then_get_element(
        browser, HPL.INPUT_URL_STRING_CREATE + HPL.INVALID_FIELD_SUFFIX, time=3
    )
    assert invalid_url_string_error is not None
    assert invalid_url_string_error.text == URL_FAILURE.FIELD_REQUIRED_STR


@pytest.mark.skip(reason="Test cannot pass until JS is bundled")
def test_invalid_url_input(browser: WebDriver, create_test_utubs, provide_app: Flask):
    """
    Tests the site error response to a user's attempt to create an invalid URL

    GIVEN a user and selected UTub
    WHEN the createURL form is submitted with an invalid URL
    THEN ensure the appropriate error and prompt is shown to user.
    """
    # Login test user and select first test UTub
    app = provide_app

    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    login_user_and_select_utub_by_utubid(
        app, browser, user_id_for_test, utub_user_created.id
    )

    add_invalid_url_header_for_ui_test(browser)

    create_url(browser, url_title="Test", url_string="Test")

    wait_until_visible_css_selector(
        browser, HPL.INPUT_URL_STRING_CREATE + HPL.INVALID_FIELD_SUFFIX, timeout=3
    )

    invalid_url_string_error = wait_then_get_element(
        browser, HPL.INPUT_URL_STRING_CREATE + HPL.INVALID_FIELD_SUFFIX, time=3
    )
    assert invalid_url_string_error is not None
    assert invalid_url_string_error.text == URL_FAILURE.UNABLE_TO_VALIDATE_THIS_URL


def test_create_url_sanitized_title(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    Tests the site error response to a user's attempt to create a URL with a title that
    contains improper or unsanitized inputs

    GIVEN a user and selected UTub
    WHEN the createURL form is submitted with an invalid URL title that is sanitized
    THEN ensure the appropriate error and prompt is shown to user.
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    login_user_and_select_utub_by_utubid(
        app, browser, user_id_for_test, utub_user_created.id
    )

    create_url(browser, url_title='<img src="evl.jpg">', url_string=MOCK_URL_STRINGS[0])
    wait_until_visible_css_selector(
        browser, HPL.INPUT_URL_TITLE_CREATE + HPL.INVALID_FIELD_SUFFIX, timeout=3
    )

    invalid_url_title_error = wait_then_get_element(
        browser, HPL.INPUT_URL_TITLE_CREATE + HPL.INVALID_FIELD_SUFFIX, time=3
    )
    assert invalid_url_title_error is not None
    assert invalid_url_title_error.text == URL_FAILURE.INVALID_INPUT


def test_create_url_duplicate_url(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    Tests the site error response to a user's attempt to create a URL that is already in the UTub

    GIVEN a user and selected UTub
    WHEN the createURL form is submitted with a duplicate URL string
    THEN ensure the appropriate error and prompt is shown to user.
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    with app.app_context():
        utub_url: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_user_created.id
        ).first()
        url_string_already_added = utub_url.standalone_url.url_string

    login_user_and_select_utub_by_utubid(
        app, browser, user_id_for_test, utub_user_created.id
    )

    create_url(browser, url_title="Testing", url_string=url_string_already_added)

    invalid_url_string_error = wait_then_get_element(
        browser, HPL.INPUT_URL_STRING_CREATE + HPL.INVALID_FIELD_SUFFIX, time=3
    )
    assert invalid_url_string_error is not None
    assert invalid_url_string_error.text == URL_FAILURE.URL_IN_UTUB


def test_create_url_invalid_csrf_token(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    Tests a user's ability to attempt to create a new URL with an invalid CSRF token

    GIVEN a user attempting to create a new URL in a UTub
    WHEN the createURL form is sent with an invalid CSRF token
    THEN ensure U4I responds with a proper error message
    """
    app = provide_app
    user_id_for_test = 1
    with app.app_context():
        user: Users = Users.query.get(user_id_for_test)
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    login_user_and_select_utub_by_utubid(
        app, browser, user_id_for_test, utub_user_created.id
    )

    invalidate_csrf_token_on_page(browser)
    create_url(browser, url_title="Testing", url_string=MOCK_URL_STRINGS[0])

    assert_visited_403_on_invalid_csrf_and_reload(browser)

    # Page reloads after user clicks button in CSRF 403 error page
    create_utub_name_input = wait_until_hidden(
        browser, HPL.INPUT_URL_STRING_CREATE, timeout=3
    )
    assert not create_utub_name_input.is_displayed()
    assert_login_with_username(browser, user.username)
