import random
from typing import Tuple
from urllib.parse import urlsplit

from flask import Flask
from flask.testing import FlaskCliRunner
import pytest
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver

from src.cli.mock_constants import (
    MOCK_URL_STRINGS,
)
from src.models.users import Users
from src.models.utub_urls import Utub_Urls
from src.models.utubs import Utubs
from src.utils.constants import URL_CONSTANTS
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from src.utils.strings.url_strs import URL_FAILURE
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.utils_for_test import (
    add_mock_urls,
    assert_login_with_username,
    assert_visited_403_on_invalid_csrf_and_reload,
    get_selected_url,
    invalidate_csrf_token_on_page,
    login_user_select_utub_by_name_and_url_by_string,
    login_user_select_utub_by_name_and_url_by_title,
    verify_update_url_state_is_hidden,
    verify_update_url_state_is_shown,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_hidden,
    wait_until_in_focus,
    wait_until_visible_css_selector,
)
from tests.functional.urls_ui.utils_for_test_url_ui import (
    add_invalid_url_header_for_ui_test,
    update_url_title,
    update_url_string,
)

pytestmark = pytest.mark.urls_ui


def test_update_url_string_submit_btn(
    browser: WebDriver,
    create_test_utubs,
    runner: Tuple[Flask, FlaskCliRunner],
    provide_app: Flask,
):
    """
    Tests a user's ability to update the URL string of the selected URL.

    GIVEN a user has access to a URL
    WHEN the updateURL form is populated with a new URL and user presses submit
    THEN ensure the URL is updated accordingly
    """

    _, cli_runner = runner
    app = provide_app
    random_url_to_add, random_url_to_change_to = random.sample(MOCK_URL_STRINGS, 2)
    add_mock_urls(
        cli_runner,
        [
            random_url_to_add,
        ],
    )

    user_id_for_test = 1
    login_user_select_utub_by_name_and_url_by_string(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1, random_url_to_add
    )

    url_row = get_selected_url(browser)

    update_url_string(browser, url_row, random_url_to_change_to)
    verify_update_url_state_is_shown(url_row)
    url_row.find_element(By.CSS_SELECTOR, HPL.BUTTON_URL_STRING_SUBMIT_UPDATE).click()

    wait_until_hidden(browser, HPL.UPDATE_URL_STRING_WRAP)
    verify_update_url_state_is_hidden(url_row)

    url_row_string_elem = url_row.find_element(By.CSS_SELECTOR, HPL.URL_STRING_READ)

    # Extract URL string from updated URL row
    url_row_string_display = url_row_string_elem.text
    url_row_data_attrib = url_row_string_elem.get_attribute("data-url")

    assert url_row_data_attrib == url_row_string_display

    host_changed_to = urlsplit(random_url_to_change_to).hostname
    actual_host = urlsplit(url_row_data_attrib).hostname
    assert isinstance(host_changed_to, str)
    assert isinstance(actual_host, str)

    assert host_changed_to in actual_host or actual_host in host_changed_to

    with pytest.raises(NoSuchElementException):
        browser.find_element(By.CSS_SELECTOR, HPL.BUTTON_BIG_URL_STRING_CANCEL_UPDATE)

    assert not browser.find_element(
        By.CSS_SELECTOR, HPL.UPDATE_URL_STRING_WRAP
    ).is_displayed()


def test_update_url_string_press_enter_key(
    browser: WebDriver,
    create_test_utubs,
    runner: Tuple[Flask, FlaskCliRunner],
    provide_app: Flask,
):
    """
    Tests a user's ability to update the URL string of the selected URL.

    GIVEN a user has access to a URL
    WHEN the updateURL form is populated with a new URL and user presses enter key
    THEN ensure the URL is updated accordingly
    """

    _, cli_runner = runner
    app = provide_app
    random_url_to_add, random_url_to_change_to = random.sample(MOCK_URL_STRINGS, 2)
    add_mock_urls(
        cli_runner,
        [
            random_url_to_add,
        ],
    )

    user_id_for_test = 1
    login_user_select_utub_by_name_and_url_by_string(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1, random_url_to_add
    )

    url_row = get_selected_url(browser)

    update_url_string(browser, url_row, random_url_to_change_to)
    verify_update_url_state_is_shown(url_row)
    browser.switch_to.active_element.send_keys(Keys.ENTER)

    wait_until_hidden(browser, HPL.UPDATE_URL_STRING_WRAP)
    verify_update_url_state_is_hidden(url_row)

    url_row_string_elem = url_row.find_element(By.CSS_SELECTOR, HPL.URL_STRING_READ)

    # Extract URL string from updated URL row
    url_row_string_display = url_row_string_elem.text
    url_row_data_attrib = url_row_string_elem.get_attribute("data-url")

    assert url_row_data_attrib == url_row_string_display

    host_changed_to = urlsplit(random_url_to_change_to).hostname
    actual_host = urlsplit(url_row_data_attrib).hostname
    assert isinstance(host_changed_to, str)
    assert isinstance(actual_host, str)

    assert host_changed_to in actual_host or actual_host in host_changed_to

    with pytest.raises(NoSuchElementException):
        browser.find_element(By.CSS_SELECTOR, HPL.BUTTON_BIG_URL_STRING_CANCEL_UPDATE)

    assert not browser.find_element(
        By.CSS_SELECTOR, HPL.UPDATE_URL_STRING_WRAP
    ).is_displayed()


def test_update_url_string_big_cancel_btn(
    browser: WebDriver,
    create_test_utubs,
    runner: Tuple[Flask, FlaskCliRunner],
    provide_app: Flask,
):
    """
    Tests a user's ability to close the update URL input box by pressing cancel btn

    GIVEN a user has access to a URL
    WHEN the updateURL form is populated with a new URL but user presses cancel btn
    THEN ensure the URL is not updated and input is hidden
    """

    _, cli_runner = runner
    app = provide_app
    random_url_to_add = random.sample(MOCK_URL_STRINGS, 1)[0]
    add_mock_urls(
        cli_runner,
        [
            random_url_to_add,
        ],
    )

    user_id_for_test = 1
    login_user_select_utub_by_name_and_url_by_string(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1, random_url_to_add
    )

    url_row = get_selected_url(browser)
    url_row_string_elem = url_row.find_element(By.CSS_SELECTOR, HPL.URL_STRING_READ)

    init_url_row_data = url_row_string_elem.get_attribute("data-url")
    init_url_row_string_display = url_row_string_elem.text

    url_row.find_element(By.CSS_SELECTOR, HPL.BUTTON_URL_STRING_UPDATE).click()
    verify_update_url_state_is_shown(url_row)

    cancel_update_btn = wait_then_get_element(
        browser, HPL.BUTTON_BIG_URL_STRING_CANCEL_UPDATE
    )
    assert cancel_update_btn is not None
    cancel_update_btn.click()
    wait_until_hidden(browser, HPL.UPDATE_URL_STRING_WRAP)
    verify_update_url_state_is_hidden(url_row)

    url_row_string_elem = url_row.find_element(By.CSS_SELECTOR, HPL.URL_STRING_READ)

    # Extract URL string from updated URL row
    url_row_string_display = url_row_string_elem.text
    url_row_data_attrib = url_row_string_elem.get_attribute("data-url")

    assert url_row_data_attrib == init_url_row_data
    assert url_row_string_display == init_url_row_string_display

    with pytest.raises(NoSuchElementException):
        browser.find_element(By.CSS_SELECTOR, HPL.BUTTON_BIG_URL_STRING_CANCEL_UPDATE)

    assert not browser.find_element(
        By.CSS_SELECTOR, HPL.UPDATE_URL_STRING_WRAP
    ).is_displayed()


def test_update_url_string_cancel_btn(
    browser: WebDriver,
    create_test_utubs,
    runner: Tuple[Flask, FlaskCliRunner],
    provide_app: Flask,
):
    """
    Tests a user's ability to close the update URL input box by pressing cancel btn

    GIVEN a user has access to a URL
    WHEN the updateURL form is populated with a new URL but user presses cancel btn
    THEN ensure the URL is not updated and input is hidden
    """

    _, cli_runner = runner
    app = provide_app
    random_url_to_add = random.sample(MOCK_URL_STRINGS, 1)[0]
    add_mock_urls(
        cli_runner,
        [
            random_url_to_add,
        ],
    )

    user_id_for_test = 1
    login_user_select_utub_by_name_and_url_by_string(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1, random_url_to_add
    )

    url_row = get_selected_url(browser)
    url_row_string_elem = url_row.find_element(By.CSS_SELECTOR, HPL.URL_STRING_READ)

    init_url_row_data = url_row_string_elem.get_attribute("data-url")
    init_url_row_string_display = url_row_string_elem.text
    url_row.find_element(By.CSS_SELECTOR, HPL.BUTTON_URL_STRING_UPDATE).click()
    verify_update_url_state_is_shown(url_row)

    cancel_update_btn = wait_then_get_element(
        browser, HPL.BUTTON_URL_STRING_CANCEL_UPDATE
    )
    assert cancel_update_btn is not None
    cancel_update_btn.click()
    wait_until_hidden(browser, HPL.UPDATE_URL_STRING_WRAP)
    verify_update_url_state_is_hidden(url_row)

    url_row_string_elem = url_row.find_element(By.CSS_SELECTOR, HPL.URL_STRING_READ)

    # Extract URL string from updated URL row
    url_row_string_display = url_row_string_elem.text
    url_row_data_attrib = url_row_string_elem.get_attribute("data-url")

    assert url_row_data_attrib == init_url_row_data
    assert url_row_string_display == init_url_row_string_display

    with pytest.raises(NoSuchElementException):
        browser.find_element(By.CSS_SELECTOR, HPL.BUTTON_BIG_URL_STRING_CANCEL_UPDATE)

    assert not browser.find_element(
        By.CSS_SELECTOR, HPL.UPDATE_URL_STRING_WRAP
    ).is_displayed()


def test_update_url_string_escape_key(
    browser: WebDriver,
    create_test_utubs,
    runner: Tuple[Flask, FlaskCliRunner],
    provide_app: Flask,
):
    """
    Tests a user's ability to close the update URL input box by pressing escape key

    GIVEN a user has access to a URL
    WHEN the updateURL form is populated with a new URL but user presses cancel btn
    THEN ensure the URL is not updated and input is hidden
    """

    _, cli_runner = runner
    app = provide_app
    random_url_to_add = random.sample(MOCK_URL_STRINGS, 1)[0]
    add_mock_urls(
        cli_runner,
        [
            random_url_to_add,
        ],
    )

    user_id_for_test = 1
    login_user_select_utub_by_name_and_url_by_string(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1, random_url_to_add
    )

    url_row = get_selected_url(browser)
    url_row_string_elem = url_row.find_element(By.CSS_SELECTOR, HPL.URL_STRING_READ)

    init_url_row_data = url_row_string_elem.get_attribute("data-url")
    init_url_row_string_display = url_row_string_elem.text
    url_row.find_element(By.CSS_SELECTOR, HPL.BUTTON_URL_STRING_UPDATE).click()
    verify_update_url_state_is_shown(url_row)

    # Sleep required to allow the element to come into focus
    wait_until_in_focus(
        browser, f"{HPL.ROW_SELECTED_URL} {HPL.INPUT_URL_STRING_UPDATE}"
    )
    browser.switch_to.active_element.send_keys(Keys.ESCAPE)
    wait_until_hidden(browser, HPL.UPDATE_URL_STRING_WRAP)
    verify_update_url_state_is_hidden(url_row)

    url_row_string_elem = url_row.find_element(By.CSS_SELECTOR, HPL.URL_STRING_READ)

    # Extract URL string from updated URL row
    url_row_string_display = url_row_string_elem.text
    url_row_data_attrib = url_row_string_elem.get_attribute("data-url")

    assert url_row_data_attrib == init_url_row_data
    assert url_row_string_display == init_url_row_string_display

    with pytest.raises(NoSuchElementException):
        browser.find_element(By.CSS_SELECTOR, HPL.BUTTON_BIG_URL_STRING_CANCEL_UPDATE)

    assert not browser.find_element(
        By.CSS_SELECTOR, HPL.UPDATE_URL_STRING_WRAP
    ).is_displayed()


def test_update_url_title_submit_btn(
    browser: WebDriver,
    create_test_utubs,
    runner: Tuple[Flask, FlaskCliRunner],
    provide_app: Flask,
):
    """
    Tests a user's ability to update the URL title of a selected URL.

    GIVEN a user has access to a URL
    WHEN the updateURLTitle form is populated with a new URL Title
    THEN ensure the URL Title is updated accordingly
    """

    _, cli_runner = runner
    app = provide_app
    add_mock_urls(cli_runner, list([UTS.TEST_URL_STRING_CREATE]))

    user_id_for_test = 1
    login_user_select_utub_by_name_and_url_by_title(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1, UTS.TEST_URL_TITLE_1
    )

    url_row = get_selected_url(browser)
    url_title = UTS.TEST_URL_TITLE_UPDATE
    update_url_title(browser, url_row, url_title)
    assert not url_row.find_element(By.CSS_SELECTOR, HPL.URL_TITLE_READ).is_displayed()

    # Submit
    url_row.find_element(By.CSS_SELECTOR, HPL.BUTTON_URL_TITLE_SUBMIT_UPDATE).click()

    # Wait for POST request
    wait_until_hidden(browser, HPL.BUTTON_URL_TITLE_SUBMIT_UPDATE)
    assert url_row.find_element(By.CSS_SELECTOR, HPL.URL_TITLE_READ).is_displayed()

    # Extract URL string from updated URL row
    url_row_title = url_row.find_element(By.CSS_SELECTOR, HPL.URL_TITLE_READ).text

    assert url_title == url_row_title


def test_update_url_title_submit_enter_key(
    browser: WebDriver,
    create_test_utubs,
    runner: Tuple[Flask, FlaskCliRunner],
    provide_app: Flask,
):
    """
    Tests a user's ability to update the URL title of a selected URL.

    GIVEN a user has access to a URL
    WHEN the updateURLTitle form is submitted with enter key and populated with a new URL Title
    THEN ensure the URL Title is updated accordingly
    """

    _, cli_runner = runner
    app = provide_app
    add_mock_urls(cli_runner, list([UTS.TEST_URL_STRING_CREATE]))

    user_id_for_test = 1
    login_user_select_utub_by_name_and_url_by_title(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1, UTS.TEST_URL_TITLE_1
    )

    url_row = get_selected_url(browser)
    url_title = UTS.TEST_URL_TITLE_UPDATE
    update_url_title(browser, url_row, url_title)
    assert not url_row.find_element(By.CSS_SELECTOR, HPL.URL_TITLE_READ).is_displayed()

    # Submit
    browser.switch_to.active_element.send_keys(Keys.ENTER)

    # Wait for update to hide
    wait_until_hidden(browser, HPL.BUTTON_URL_TITLE_SUBMIT_UPDATE)
    assert url_row.find_element(By.CSS_SELECTOR, HPL.URL_TITLE_READ).is_displayed()

    # Extract URL string from updated URL row
    url_row_title = url_row.find_element(By.CSS_SELECTOR, HPL.URL_TITLE_READ).text

    assert url_title == url_row_title


def test_update_url_title_cancel_click_btn(
    browser: WebDriver,
    create_test_utubs,
    runner: Tuple[Flask, FlaskCliRunner],
    provide_app: Flask,
):
    """
    Tests a user's ability to update the URL title of a selected URL.

    GIVEN a user has access to a URL
    WHEN the updateURLTitle form is populated with a new URL Title, but the user cancels by pressing the X btn
    THEN ensure the URL Title is not updated, and the form is hidden
    """

    _, cli_runner = runner
    app = provide_app
    add_mock_urls(cli_runner, list([UTS.TEST_URL_STRING_CREATE]))

    user_id_for_test = 1
    login_user_select_utub_by_name_and_url_by_title(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1, UTS.TEST_URL_TITLE_1
    )

    url_row = get_selected_url(browser)

    # Extract URL string from updated URL row
    init_url_row_title = url_row.find_element(By.CSS_SELECTOR, HPL.URL_TITLE_READ).text

    url_title = UTS.TEST_URL_TITLE_UPDATE
    update_url_title(browser, url_row, url_title)
    assert not url_row.find_element(By.CSS_SELECTOR, HPL.URL_TITLE_READ).is_displayed()

    url_row.find_element(By.CSS_SELECTOR, HPL.BUTTON_URL_TITLE_CANCEL_UPDATE).click()

    wait_until_hidden(browser, HPL.BUTTON_URL_TITLE_CANCEL_UPDATE)
    assert url_row.find_element(By.CSS_SELECTOR, HPL.URL_TITLE_READ).is_displayed()

    # Extract URL string from updated URL row
    url_row_title = url_row.find_element(By.CSS_SELECTOR, HPL.URL_TITLE_READ).text

    assert init_url_row_title == url_row_title


def test_update_url_title_cancel_press_escape(
    browser: WebDriver,
    create_test_utubs,
    runner: Tuple[Flask, FlaskCliRunner],
    provide_app: Flask,
):
    """
    Tests a user's ability to update the URL title of a selected URL.

    GIVEN a user has access to a URL
    WHEN the updateURLTitle form is populated with a new URL Title, but the user cancels by pressing the escape key
    THEN ensure the URL Title is not updated, and the form is hidden
    """

    _, cli_runner = runner
    app = provide_app
    add_mock_urls(cli_runner, list([UTS.TEST_URL_STRING_CREATE]))

    user_id_for_test = 1
    login_user_select_utub_by_name_and_url_by_title(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1, UTS.TEST_URL_TITLE_1
    )

    url_row = get_selected_url(browser)

    # Extract URL string from updated URL row
    init_url_row_title = url_row.find_element(By.CSS_SELECTOR, HPL.URL_TITLE_READ).text

    url_title = UTS.TEST_URL_TITLE_UPDATE
    update_url_title(browser, url_row, url_title)
    assert not url_row.find_element(By.CSS_SELECTOR, HPL.URL_TITLE_READ).is_displayed()

    browser.switch_to.active_element.send_keys(Keys.ESCAPE)

    wait_until_hidden(browser, HPL.BUTTON_URL_TITLE_CANCEL_UPDATE)
    assert url_row.find_element(By.CSS_SELECTOR, HPL.URL_TITLE_READ).is_displayed()

    # Extract URL string from updated URL row
    url_row_title = url_row.find_element(By.CSS_SELECTOR, HPL.URL_TITLE_READ).text

    assert init_url_row_title == url_row_title


def test_update_url_title_length_exceeded(
    browser: WebDriver,
    create_test_urls,
    runner: Tuple[Flask, FlaskCliRunner],
    provide_app: Flask,
):
    """
    Tests the site error response to a user's attempt to update a URL with a title that exceeds the maximum character length limit.

    GIVEN a user and selected UTub
    WHEN the updateURL title form is populated and submitted with a title that exceeds character limits
    THEN ensure the appropriate error and prompt is shown to user.
    """

    _, cli_runner = runner
    app = provide_app
    add_mock_urls(cli_runner, list([UTS.TEST_URL_STRING_CREATE]))

    user_id_for_test = 1
    login_user_select_utub_by_name_and_url_by_title(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1, UTS.TEST_URL_TITLE_1
    )

    url_row = get_selected_url(browser)

    update_url_title(browser, url_row, "a" * (URL_CONSTANTS.MAX_URL_TITLE_LENGTH + 1))

    update_url_title_input = wait_then_get_element(
        browser, f"{HPL.ROW_SELECTED_URL} {HPL.INPUT_URL_TITLE_UPDATE}", time=3
    )

    assert update_url_title_input is not None
    new_url_title = update_url_title_input.get_attribute("value")
    assert new_url_title is not None
    assert len(new_url_title) == URL_CONSTANTS.MAX_URL_TITLE_LENGTH


def test_update_url_string_empty_field(
    browser: WebDriver, create_test_urls, provide_app
):
    """
    GIVEN a user and selected UTub
    WHEN the updateURL string form is submitted empty
    THEN ensure the appropriate error and prompt is shown to user.
    """
    app = provide_app
    user_id_for_test = 1
    login_user_select_utub_by_name_and_url_by_title(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1, UTS.TEST_URL_TITLE_1
    )

    url_row = get_selected_url(browser)
    update_url_string(browser, url_row, "")

    wait_then_click_element(
        browser, f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_STRING_SUBMIT_UPDATE}", time=3
    )

    invalid_url_string_error = wait_then_get_element(
        browser, HPL.INPUT_URL_STRING_UPDATE + HPL.INVALID_FIELD_SUFFIX, time=3
    )
    assert invalid_url_string_error is not None
    assert invalid_url_string_error.text == URL_FAILURE.FIELD_REQUIRED_STR


def test_update_url_title_empty_field(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    GIVEN a user and selected UTub
    WHEN the updateURL title form is submitted empty
    THEN ensure the appropriate error and prompt is shown to user.
    """
    app = provide_app
    user_id_for_test = 1
    login_user_select_utub_by_name_and_url_by_title(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1, UTS.TEST_URL_TITLE_1
    )

    url_row = get_selected_url(browser)
    update_url_title(browser, url_row, "")

    wait_then_click_element(
        browser, f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_TITLE_SUBMIT_UPDATE}", time=3
    )

    invalid_url_title_error = wait_then_get_element(
        browser, HPL.INPUT_URL_TITLE_UPDATE + HPL.INVALID_FIELD_SUFFIX, time=3
    )
    assert invalid_url_title_error is not None
    assert invalid_url_title_error.text == URL_FAILURE.FIELD_REQUIRED_STR


def test_update_url_string_duplicate_url(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    GIVEN a user and selected UTub
    WHEN the updateURL string form is submitted with a URL that is already in the UTub
    THEN ensure the appropriate error and prompt is shown to user.
    """
    app = provide_app
    user_id_for_test = 1
    with app.app_context():
        utub: Utubs = Utubs.query.filter(Utubs.utub_creator == user_id_for_test).first()
        utub_url: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub.id
        ).first()
        url_to_update_to: str = utub_url.standalone_url.url_string
        another_utub_url: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.url_title != utub_url.url_title
        ).first()

    login_user_select_utub_by_name_and_url_by_title(
        app, browser, user_id_for_test, utub.name, another_utub_url.url_title
    )

    url_row = get_selected_url(browser)
    update_url_string(browser, url_row, url_to_update_to)

    wait_then_click_element(
        browser, f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_STRING_SUBMIT_UPDATE}", time=3
    )

    error_css_selector = f"{HPL.ROW_SELECTED_URL} {HPL.INPUT_URL_STRING_UPDATE + HPL.INVALID_FIELD_SUFFIX}"
    wait_until_visible_css_selector(browser, error_css_selector, timeout=3)

    invalid_url_string_error = wait_then_get_element(
        browser, error_css_selector, time=3
    )
    assert invalid_url_string_error is not None
    assert invalid_url_string_error.text == URL_FAILURE.URL_IN_UTUB


@pytest.mark.skip(reason="Test cannot pass until JS is bundled")
def test_update_url_string_invalid_url(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    GIVEN a user and selected UTub
    WHEN the updateURL string form is submitted with an invalid URL
    THEN ensure the appropriate error and prompt is shown to user.
    """
    app = provide_app
    user_id_for_test = 1

    login_user_select_utub_by_name_and_url_by_title(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1, UTS.TEST_URL_TITLE_1
    )

    url_row = get_selected_url(browser)
    update_url_string(browser, url_row, "Test")

    add_invalid_url_header_for_ui_test(browser)
    wait_then_click_element(
        browser, f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_STRING_SUBMIT_UPDATE}", time=3
    )

    error_css_selector = f"{HPL.ROW_SELECTED_URL} {HPL.INPUT_URL_STRING_UPDATE + HPL.INVALID_FIELD_SUFFIX}"
    wait_until_visible_css_selector(browser, error_css_selector, timeout=3)

    invalid_url_string_error = wait_then_get_element(
        browser, error_css_selector, time=3
    )
    assert invalid_url_string_error is not None
    assert invalid_url_string_error.text == URL_FAILURE.UNABLE_TO_VALIDATE_THIS_URL


def test_update_url_sanitized_title(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    Tests the site error response to a user's attempt to update a URL with a title that
    contains improper or unsanitized inputs

    GIVEN a user and selected UTub
    WHEN the updateURL title form is submitted with an invalid URL title that is sanitized
    THEN ensure the appropriate error and prompt is shown to user.
    """
    app = provide_app
    user_id_for_test = 1

    login_user_select_utub_by_name_and_url_by_title(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1, UTS.TEST_URL_TITLE_1
    )

    url_row = get_selected_url(browser)

    update_url_title(browser, url_row, '<img src="evl.jpg">')
    wait_then_click_element(
        browser, f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_TITLE_SUBMIT_UPDATE}", time=3
    )

    error_css_selector = f"{HPL.ROW_SELECTED_URL} {HPL.INPUT_URL_TITLE_UPDATE + HPL.INVALID_FIELD_SUFFIX}"
    wait_until_visible_css_selector(browser, error_css_selector, timeout=3)

    invalid_url_title_error = wait_then_get_element(browser, error_css_selector, time=3)
    assert invalid_url_title_error is not None
    assert invalid_url_title_error.text == URL_FAILURE.INVALID_INPUT


def test_update_url_title_invalid_csrf_token(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    Tests the site error response to a user's attempt to update a URL with a title
    with an invalid CSRF token

    GIVEN a user and selected UTub
    WHEN the updateURL title form is submitted with an invalid CSRF token
    THEN ensure the appropriate error and prompt is shown to user.
    """
    app = provide_app
    user_id_for_test = 1
    with app.app_context():
        user: Users = Users.query.get(user_id_for_test)

    login_user_select_utub_by_name_and_url_by_title(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1, UTS.TEST_URL_TITLE_1
    )

    url_row = get_selected_url(browser)

    update_url_title(browser, url_row, "Testing")
    invalidate_csrf_token_on_page(browser)
    wait_then_click_element(
        browser, f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_TITLE_SUBMIT_UPDATE}", time=3
    )

    assert_visited_403_on_invalid_csrf_and_reload(browser)

    # Page reloads after user clicks button in CSRF 403 error page
    with pytest.raises(NoSuchElementException):
        browser.find_element(By.CSS_SELECTOR, HPL.ROW_SELECTED_URL)

    assert_login_with_username(browser, user.username)


def test_update_url_string_invalid_csrf_token(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    Tests the site error response to a user's attempt to update a URL with a url string
    with an invalid CSRF token

    GIVEN a user and selected UTub
    WHEN the updateURL string form is submitted with an invalid CSRF token
    THEN ensure the appropriate error and prompt is shown to user.
    """
    app = provide_app
    user_id_for_test = 1
    with app.app_context():
        user: Users = Users.query.get(user_id_for_test)

    login_user_select_utub_by_name_and_url_by_title(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1, UTS.TEST_URL_TITLE_1
    )

    url_row = get_selected_url(browser)

    update_url_string(browser, url_row, "Testing")
    invalidate_csrf_token_on_page(browser)
    wait_then_click_element(
        browser, f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_STRING_SUBMIT_UPDATE}", time=3
    )

    assert_visited_403_on_invalid_csrf_and_reload(browser)

    # Page reloads after user clicks button in CSRF 403 error page
    with pytest.raises(NoSuchElementException):
        browser.find_element(By.CSS_SELECTOR, HPL.ROW_SELECTED_URL)

    assert_login_with_username(browser, user.username)
