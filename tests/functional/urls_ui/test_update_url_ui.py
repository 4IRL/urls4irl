# Standard library
import random
from time import sleep
from typing import Tuple
from urllib.parse import urlsplit

# External libraries
from flask import Flask
from flask.testing import FlaskCliRunner
import pytest
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver

# Internal libraries
from src.mocks.mock_constants import (
    MOCK_URL_STRINGS,
)
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.locators import MainPageLocators as MPL
from tests.functional.utils_for_test import (
    add_mock_urls,
    get_selected_url,
    login_user_select_utub_by_name_and_url_by_string,
    login_user_select_utub_by_name_and_url_by_title,
    login_utub_url,
    verify_update_url_state_is_hidden,
    verify_update_url_state_is_shown,
    wait_then_get_element,
    wait_until_hidden,
)
from tests.functional.urls_ui.utils_for_test_url_ui import (
    update_url_title,
    update_url_string,
)

pytestmark = pytest.mark.urls_ui


def test_update_url_string_submit_btn(
    browser: WebDriver,
    create_test_utubs,
    runner: Tuple[Flask, FlaskCliRunner],
    provide_app_for_session_generation: Flask,
):
    """
    Tests a user's ability to update the URL string of the selected URL.

    GIVEN a user has access to a URL
    WHEN the updateURL form is populated with a new URL and user presses submit
    THEN ensure the URL is updated accordingly
    """

    _, cli_runner = runner
    app = provide_app_for_session_generation
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

    update_url_string(url_row, random_url_to_change_to)
    verify_update_url_state_is_shown(url_row)
    url_row.find_element(By.CSS_SELECTOR, MPL.BUTTON_URL_STRING_SUBMIT_UPDATE).click()

    wait_until_hidden(browser, MPL.UPDATE_URL_STRING_WRAP)
    verify_update_url_state_is_hidden(url_row)

    url_row_string_elem = url_row.find_element(By.CSS_SELECTOR, MPL.URL_STRING_READ)

    # Extract URL string from updated URL row
    url_row_string_display = url_row_string_elem.get_attribute("innerText")
    url_row_data_attrib = url_row_string_elem.get_attribute("data-url")

    assert url_row_data_attrib == url_row_string_display

    host_changed_to = urlsplit(random_url_to_change_to).hostname
    actual_host = urlsplit(url_row_data_attrib).hostname
    assert isinstance(host_changed_to, str)
    assert isinstance(actual_host, str)

    assert host_changed_to in actual_host or actual_host in host_changed_to

    with pytest.raises(NoSuchElementException):
        browser.find_element(By.CSS_SELECTOR, MPL.BUTTON_BIG_URL_STRING_CANCEL_UPDATE)

    assert not browser.find_element(
        By.CSS_SELECTOR, MPL.UPDATE_URL_STRING_WRAP
    ).is_displayed()


def test_update_url_string_press_enter_key(
    browser: WebDriver,
    create_test_utubs,
    runner: Tuple[Flask, FlaskCliRunner],
    provide_app_for_session_generation: Flask,
):
    """
    Tests a user's ability to update the URL string of the selected URL.

    GIVEN a user has access to a URL
    WHEN the updateURL form is populated with a new URL and user presses enter key
    THEN ensure the URL is updated accordingly
    """

    _, cli_runner = runner
    app = provide_app_for_session_generation
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

    update_url_string(url_row, random_url_to_change_to)
    verify_update_url_state_is_shown(url_row)
    browser.switch_to.active_element.send_keys(Keys.ENTER)

    wait_until_hidden(browser, MPL.UPDATE_URL_STRING_WRAP)
    verify_update_url_state_is_hidden(url_row)

    url_row_string_elem = url_row.find_element(By.CSS_SELECTOR, MPL.URL_STRING_READ)

    # Extract URL string from updated URL row
    url_row_string_display = url_row_string_elem.get_attribute("innerText")
    url_row_data_attrib = url_row_string_elem.get_attribute("data-url")

    assert url_row_data_attrib == url_row_string_display

    host_changed_to = urlsplit(random_url_to_change_to).hostname
    actual_host = urlsplit(url_row_data_attrib).hostname
    assert isinstance(host_changed_to, str)
    assert isinstance(actual_host, str)

    assert host_changed_to in actual_host or actual_host in host_changed_to

    with pytest.raises(NoSuchElementException):
        browser.find_element(By.CSS_SELECTOR, MPL.BUTTON_BIG_URL_STRING_CANCEL_UPDATE)

    assert not browser.find_element(
        By.CSS_SELECTOR, MPL.UPDATE_URL_STRING_WRAP
    ).is_displayed()


def test_update_url_string_big_cancel_btn(
    browser: WebDriver,
    create_test_utubs,
    runner: Tuple[Flask, FlaskCliRunner],
    provide_app_for_session_generation: Flask,
):
    """
    Tests a user's ability to close the update URL input box by pressing cancel btn

    GIVEN a user has access to a URL
    WHEN the updateURL form is populated with a new URL but user presses cancel btn
    THEN ensure the URL is not updated and input is hidden
    """

    _, cli_runner = runner
    app = provide_app_for_session_generation
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
    url_row_string_elem = url_row.find_element(By.CSS_SELECTOR, MPL.URL_STRING_READ)

    init_url_row_data = url_row_string_elem.get_attribute("data-url")
    init_url_row_string_display = url_row_string_elem.get_attribute("innerText")

    url_row.find_element(By.CSS_SELECTOR, MPL.BUTTON_URL_STRING_UPDATE).click()
    verify_update_url_state_is_shown(url_row)

    cancel_update_btn = wait_then_get_element(
        browser, MPL.BUTTON_BIG_URL_STRING_CANCEL_UPDATE
    )
    assert cancel_update_btn is not None
    cancel_update_btn.click()
    wait_until_hidden(browser, MPL.UPDATE_URL_STRING_WRAP)
    verify_update_url_state_is_hidden(url_row)

    url_row_string_elem = url_row.find_element(By.CSS_SELECTOR, MPL.URL_STRING_READ)

    # Extract URL string from updated URL row
    url_row_string_display = url_row_string_elem.get_attribute("innerText")
    url_row_data_attrib = url_row_string_elem.get_attribute("data-url")

    assert url_row_data_attrib == init_url_row_data
    assert url_row_string_display == init_url_row_string_display

    with pytest.raises(NoSuchElementException):
        browser.find_element(By.CSS_SELECTOR, MPL.BUTTON_BIG_URL_STRING_CANCEL_UPDATE)

    assert not browser.find_element(
        By.CSS_SELECTOR, MPL.UPDATE_URL_STRING_WRAP
    ).is_displayed()


def test_update_url_string_cancel_btn(
    browser: WebDriver,
    create_test_utubs,
    runner: Tuple[Flask, FlaskCliRunner],
    provide_app_for_session_generation: Flask,
):
    """
    Tests a user's ability to close the update URL input box by pressing cancel btn

    GIVEN a user has access to a URL
    WHEN the updateURL form is populated with a new URL but user presses cancel btn
    THEN ensure the URL is not updated and input is hidden
    """

    _, cli_runner = runner
    app = provide_app_for_session_generation
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
    url_row_string_elem = url_row.find_element(By.CSS_SELECTOR, MPL.URL_STRING_READ)

    init_url_row_data = url_row_string_elem.get_attribute("data-url")
    init_url_row_string_display = url_row_string_elem.get_attribute("innerText")
    url_row.find_element(By.CSS_SELECTOR, MPL.BUTTON_URL_STRING_UPDATE).click()
    verify_update_url_state_is_shown(url_row)

    cancel_update_btn = wait_then_get_element(
        browser, MPL.BUTTON_URL_STRING_CANCEL_UPDATE
    )
    assert cancel_update_btn is not None
    cancel_update_btn.click()
    wait_until_hidden(browser, MPL.UPDATE_URL_STRING_WRAP)
    verify_update_url_state_is_hidden(url_row)

    url_row_string_elem = url_row.find_element(By.CSS_SELECTOR, MPL.URL_STRING_READ)

    # Extract URL string from updated URL row
    url_row_string_display = url_row_string_elem.get_attribute("innerText")
    url_row_data_attrib = url_row_string_elem.get_attribute("data-url")

    assert url_row_data_attrib == init_url_row_data
    assert url_row_string_display == init_url_row_string_display

    with pytest.raises(NoSuchElementException):
        browser.find_element(By.CSS_SELECTOR, MPL.BUTTON_BIG_URL_STRING_CANCEL_UPDATE)

    assert not browser.find_element(
        By.CSS_SELECTOR, MPL.UPDATE_URL_STRING_WRAP
    ).is_displayed()


def test_update_url_string_escape_key(
    browser: WebDriver,
    create_test_utubs,
    runner: Tuple[Flask, FlaskCliRunner],
    provide_app_for_session_generation: Flask,
):
    """
    Tests a user's ability to close the update URL input box by pressing escape key

    GIVEN a user has access to a URL
    WHEN the updateURL form is populated with a new URL but user presses cancel btn
    THEN ensure the URL is not updated and input is hidden
    """

    _, cli_runner = runner
    app = provide_app_for_session_generation
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
    url_row_string_elem = url_row.find_element(By.CSS_SELECTOR, MPL.URL_STRING_READ)

    init_url_row_data = url_row_string_elem.get_attribute("data-url")
    init_url_row_string_display = url_row_string_elem.get_attribute("innerText")
    url_row.find_element(By.CSS_SELECTOR, MPL.BUTTON_URL_STRING_UPDATE).click()
    verify_update_url_state_is_shown(url_row)

    # Sleep required to allow the element to come into focus
    sleep(2)
    browser.switch_to.active_element.send_keys(Keys.ESCAPE)
    wait_until_hidden(browser, MPL.UPDATE_URL_STRING_WRAP)
    verify_update_url_state_is_hidden(url_row)

    url_row_string_elem = url_row.find_element(By.CSS_SELECTOR, MPL.URL_STRING_READ)

    # Extract URL string from updated URL row
    url_row_string_display = url_row_string_elem.get_attribute("innerText")
    url_row_data_attrib = url_row_string_elem.get_attribute("data-url")

    assert url_row_data_attrib == init_url_row_data
    assert url_row_string_display == init_url_row_string_display

    with pytest.raises(NoSuchElementException):
        browser.find_element(By.CSS_SELECTOR, MPL.BUTTON_BIG_URL_STRING_CANCEL_UPDATE)

    assert not browser.find_element(
        By.CSS_SELECTOR, MPL.UPDATE_URL_STRING_WRAP
    ).is_displayed()


def test_update_url_title_submit(
    browser: WebDriver,
    create_test_utubs,
    runner: Tuple[Flask, FlaskCliRunner],
    provide_app_for_session_generation: Flask,
):
    """
    Tests a user's ability to update the URL title of a selected URL.

    GIVEN a user has access to a URL
    WHEN the updateURLTitle form is populated with a new URL Title
    THEN ensure the URL Title is updated accordingly
    """

    _, cli_runner = runner
    app = provide_app_for_session_generation
    add_mock_urls(cli_runner, list([UTS.TEST_URL_STRING_CREATE]))

    user_id_for_test = 1
    login_user_select_utub_by_name_and_url_by_title(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1, UTS.TEST_URL_TITLE_1
    )

    url_row = get_selected_url(browser)
    url_title = UTS.TEST_URL_TITLE_UPDATE
    update_url_title(browser, url_row, url_title)
    assert not url_row.find_element(By.CSS_SELECTOR, MPL.URL_TITLE_READ).is_displayed()

    # Submit
    url_row.find_element(By.CSS_SELECTOR, MPL.BUTTON_URL_TITLE_SUBMIT_UPDATE).click()

    # Wait for POST request
    wait_until_hidden(browser, MPL.BUTTON_URL_TITLE_SUBMIT_UPDATE)
    assert url_row.find_element(By.CSS_SELECTOR, MPL.URL_TITLE_READ).is_displayed()

    # Extract URL string from updated URL row
    url_row_title = url_row.find_element(
        By.CSS_SELECTOR, MPL.URL_TITLE_READ
    ).get_attribute("innerText")

    assert url_title == url_row_title


def test_update_url_title_submit_enter_key(
    browser: WebDriver,
    create_test_utubs,
    runner: Tuple[Flask, FlaskCliRunner],
    provide_app_for_session_generation: Flask,
):
    """
    Tests a user's ability to update the URL title of a selected URL.

    GIVEN a user has access to a URL
    WHEN the updateURLTitle form is submitted with enter key and populated with a new URL Title
    THEN ensure the URL Title is updated accordingly
    """

    _, cli_runner = runner
    app = provide_app_for_session_generation
    add_mock_urls(cli_runner, list([UTS.TEST_URL_STRING_CREATE]))

    user_id_for_test = 1
    login_user_select_utub_by_name_and_url_by_title(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1, UTS.TEST_URL_TITLE_1
    )

    url_row = get_selected_url(browser)
    url_title = UTS.TEST_URL_TITLE_UPDATE
    update_url_title(browser, url_row, url_title)
    assert not url_row.find_element(By.CSS_SELECTOR, MPL.URL_TITLE_READ).is_displayed()

    # Submit
    browser.switch_to.active_element.send_keys(Keys.ENTER)

    # Wait for update to hide
    wait_until_hidden(browser, MPL.BUTTON_URL_TITLE_SUBMIT_UPDATE)
    assert url_row.find_element(By.CSS_SELECTOR, MPL.URL_TITLE_READ).is_displayed()

    # Extract URL string from updated URL row
    url_row_title = url_row.find_element(
        By.CSS_SELECTOR, MPL.URL_TITLE_READ
    ).get_attribute("innerText")

    assert url_title == url_row_title


def test_update_url_title_cancel_click_btn(
    browser: WebDriver,
    create_test_utubs,
    runner: Tuple[Flask, FlaskCliRunner],
    provide_app_for_session_generation: Flask,
):
    """
    Tests a user's ability to update the URL title of a selected URL.

    GIVEN a user has access to a URL
    WHEN the updateURLTitle form is populated with a new URL Title, but the user cancels by pressing the X btn
    THEN ensure the URL Title is not updated, and the form is hidden
    """

    _, cli_runner = runner
    app = provide_app_for_session_generation
    add_mock_urls(cli_runner, list([UTS.TEST_URL_STRING_CREATE]))

    user_id_for_test = 1
    login_user_select_utub_by_name_and_url_by_title(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1, UTS.TEST_URL_TITLE_1
    )

    url_row = get_selected_url(browser)

    # Extract URL string from updated URL row
    init_url_row_title = url_row.find_element(
        By.CSS_SELECTOR, MPL.URL_TITLE_READ
    ).get_attribute("innerText")

    url_title = UTS.TEST_URL_TITLE_UPDATE
    update_url_title(browser, url_row, url_title)
    assert not url_row.find_element(By.CSS_SELECTOR, MPL.URL_TITLE_READ).is_displayed()

    url_row.find_element(By.CSS_SELECTOR, MPL.BUTTON_URL_TITLE_CANCEL_UPDATE).click()

    wait_until_hidden(browser, MPL.BUTTON_URL_TITLE_CANCEL_UPDATE)
    assert url_row.find_element(By.CSS_SELECTOR, MPL.URL_TITLE_READ).is_displayed()

    # Extract URL string from updated URL row
    url_row_title = url_row.find_element(
        By.CSS_SELECTOR, MPL.URL_TITLE_READ
    ).get_attribute("innerText")

    assert init_url_row_title == url_row_title


def test_update_url_title_cancel_press_escape(
    browser: WebDriver,
    create_test_utubs,
    runner: Tuple[Flask, FlaskCliRunner],
    provide_app_for_session_generation: Flask,
):
    """
    Tests a user's ability to update the URL title of a selected URL.

    GIVEN a user has access to a URL
    WHEN the updateURLTitle form is populated with a new URL Title, but the user cancels by pressing the escape key
    THEN ensure the URL Title is not updated, and the form is hidden
    """

    _, cli_runner = runner
    app = provide_app_for_session_generation
    add_mock_urls(cli_runner, list([UTS.TEST_URL_STRING_CREATE]))

    user_id_for_test = 1
    login_user_select_utub_by_name_and_url_by_title(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1, UTS.TEST_URL_TITLE_1
    )

    url_row = get_selected_url(browser)

    # Extract URL string from updated URL row
    init_url_row_title = url_row.find_element(
        By.CSS_SELECTOR, MPL.URL_TITLE_READ
    ).get_attribute("innerText")

    url_title = UTS.TEST_URL_TITLE_UPDATE
    update_url_title(browser, url_row, url_title)
    assert not url_row.find_element(By.CSS_SELECTOR, MPL.URL_TITLE_READ).is_displayed()

    browser.switch_to.active_element.send_keys(Keys.ESCAPE)

    wait_until_hidden(browser, MPL.BUTTON_URL_TITLE_CANCEL_UPDATE)
    assert url_row.find_element(By.CSS_SELECTOR, MPL.URL_TITLE_READ).is_displayed()

    # Extract URL string from updated URL row
    url_row_title = url_row.find_element(
        By.CSS_SELECTOR, MPL.URL_TITLE_READ
    ).get_attribute("innerText")

    assert init_url_row_title == url_row_title


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
    assert warning_modal_body is not None

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
    assert warning_modal_body is not None

    # Assert new UTub is now active and displayed to user
    assert warning_modal_body.text == "Try shortening your UTub name"
