# Standard library
import random
from urllib.parse import urlsplit

# External libraries
from typing import Tuple
from flask import Flask
from flask.testing import FlaskCliRunner
import pytest
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By

# Internal libraries
from src.cli.mock_constants import MOCK_URL_STRINGS
from src.utils.constants import URL_CONSTANTS
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.urls_ui.utils_for_test_url_ui import (
    get_selected_utub_id,
    get_utub_url_id_for_added_url_in_utub_as_member,
    verify_select_url_as_non_utub_owner_and_non_url_adder,
    verify_select_url_as_utub_owner_or_url_creator,
)
from tests.functional.utils_for_test import (
    add_mock_urls,
    dismiss_modal_with_click_out,
    get_current_user_id,
    get_num_url_rows,
    get_selected_url,
    login_user_and_select_utub_by_name,
    login_user_select_utub_by_name_and_url_by_title,
    wait_for_web_element_and_click,
    wait_then_get_element,
    wait_then_get_elements,
    wait_until_hidden,
)

pytestmark = pytest.mark.urls_ui


def test_access_url_by_access_btn_while_selected(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    Tests a user's ability to navigate to a URL using the URLOptions button.

    GIVEN access to UTubs and URLs
    WHEN a user selects a URL and clicks 'Access URL' button
    THEN ensure the URL opens in a new tab
    """
    app = provide_app
    user_id_for_test = 1
    login_user_select_utub_by_name_and_url_by_title(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1, UTS.TEST_URL_TITLE_1
    )

    url_row = get_selected_url(browser)

    init_num_of_tabs = len(browser.window_handles)
    init_tab = browser.current_window_handle

    url_row.find_element(By.CSS_SELECTOR, HPL.BUTTON_URL_ACCESS).click()

    curr_tabs = browser.window_handles

    assert init_num_of_tabs + 1 == len(curr_tabs)

    for handle in curr_tabs:
        if handle != init_tab:
            browser.switch_to.window(handle)
            assert browser.current_url in MOCK_URL_STRINGS


def test_access_url_by_goto_btn_while_selected(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    Tests a user's ability to navigate to a URL using the URLOptions button.

    GIVEN access to UTubs and URLs
    WHEN a user selects a URL and clicks the URL Go-To button
    THEN ensure the URL opens in a new tab
    """
    app = provide_app
    user_id_for_test = 1
    login_user_select_utub_by_name_and_url_by_title(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1, UTS.TEST_URL_TITLE_1
    )

    url_row = get_selected_url(browser)

    init_num_of_tabs = len(browser.window_handles)
    init_tab = browser.current_window_handle

    url_row.find_element(By.CSS_SELECTOR, HPL.GO_TO_URL_ICON).click()

    curr_tabs = browser.window_handles

    assert init_num_of_tabs + 1 == len(curr_tabs)

    for handle in curr_tabs:
        if handle != init_tab:
            browser.switch_to.window(handle)
            assert browser.current_url in MOCK_URL_STRINGS


def test_access_url_by_goto_btn_while_hover(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    Tests a user's ability to navigate to a URL using the URLOptions button.

    GIVEN access to UTubs and URLs
    WHEN a user hovers over a URL and clicks the URL Go-To button
    THEN ensure the URL opens in a new tab
    """
    app = provide_app
    user_id_for_test = 1
    login_user_and_select_utub_by_name(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1
    )

    init_num_of_tabs = len(browser.window_handles)
    init_tab = browser.current_window_handle

    url_row = wait_then_get_elements(browser, HPL.ROWS_URLS)
    assert url_row is not None
    url_row = url_row[0]

    actions = ActionChains(browser)
    actions.move_to_element(url_row).perform()

    url_row.find_element(By.CSS_SELECTOR, HPL.GO_TO_URL_ICON).click()
    curr_tabs = browser.window_handles

    assert init_num_of_tabs + 1 == len(curr_tabs)

    for handle in curr_tabs:
        if handle != init_tab:
            browser.switch_to.window(handle)
            assert browser.current_url in MOCK_URL_STRINGS


def test_access_url_by_clicking_url_string(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    Tests a user's ability to navigate to a URL using the displayed URL string.

    GIVEN access to UTubs and URLs
    WHEN a user clicks the URL text
    THEN ensure the URL opens in a new tab
    """

    app = provide_app
    user_id_for_test = 1
    login_user_select_utub_by_name_and_url_by_title(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1, UTS.TEST_URL_TITLE_1
    )

    init_num_of_tabs = len(browser.window_handles)
    init_tab = browser.current_window_handle

    url_row = get_selected_url(browser)

    init_num_of_tabs = len(browser.window_handles)
    init_tab = browser.current_window_handle

    url_row.find_element(By.CSS_SELECTOR, HPL.URL_STRING_READ).click()

    curr_tabs = browser.window_handles

    assert init_num_of_tabs + 1 == len(curr_tabs)

    for handle in curr_tabs:
        if handle != init_tab:
            browser.switch_to.window(handle)
            assert browser.current_url in MOCK_URL_STRINGS


def test_access_all_urls_at_limit(
    browser: WebDriver,
    runner: Tuple[Flask, FlaskCliRunner],
    create_test_utubs,
    provide_app: Flask,
):
    """
    Tests a user's ability to access all URLs via access all URLs button, but accessing when at the maximum number of URLs before a warning is shown

    GIVEN access to UTubs and URLs, and number of URLs is at the max number of URLs before warning modal is shown
    WHEN a user clicks access URL button
    THEN ensure the URLs open in new tabs
    """
    _, cli_runner = runner
    num_of_urls_to_add = URL_CONSTANTS.MAX_NUM_OF_URLS_TO_ACCESS - 1

    # Randomize URLs chosen to prevent any chance of looking like a bot
    urls_to_add = random.sample(MOCK_URL_STRINGS, num_of_urls_to_add)
    add_mock_urls(cli_runner, list(urls_to_add))

    app = provide_app
    user_id_for_test = 1

    login_user_and_select_utub_by_name(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1
    )

    assert get_num_url_rows(browser) == num_of_urls_to_add

    init_num_of_tabs = len(browser.window_handles)
    init_tab = browser.current_window_handle

    browser.find_element(By.CSS_SELECTOR, HPL.BUTTON_ACCESS_ALL_URLS).click()

    # Ensure modal is not shown to user since URLs below value
    with pytest.raises(NoSuchElementException):
        browser.find_element(By.CSS_SELECTOR, HPL.ACCESS_ALL_URL_MODAL)

    curr_tabs = browser.window_handles

    assert init_num_of_tabs + num_of_urls_to_add == len(curr_tabs)

    for handle in curr_tabs:
        if handle != init_tab:
            browser.switch_to.window(handle)
            browser_url_hostname = urlsplit(browser.current_url).hostname
            assert browser_url_hostname is not None
            assert any([browser_url_hostname in url for url in MOCK_URL_STRINGS])


def test_access_all_urls_above_limit(
    browser: WebDriver,
    runner: Tuple[Flask, FlaskCliRunner],
    create_test_utubs,
    provide_app: Flask,
):
    """
    Tests a user's ability to access all URLs via access all URLs button, but accessing when above the maximum number of URLs before a warning is shown

    GIVEN access to UTubs and URLs, and number of URLs is above than max number of URLs before warning modal is shown
    WHEN a user clicks access URLs btn, the modal shows and user clicks on submit btn
    THEN ensure the URLs open in new tabs and the modal is closed
    """
    _, cli_runner = runner
    num_of_urls_to_add = URL_CONSTANTS.MAX_NUM_OF_URLS_TO_ACCESS + 1

    # Randomize URLs chosen to prevent any chance of looking like a bot
    urls_to_add = random.sample(MOCK_URL_STRINGS, num_of_urls_to_add)
    add_mock_urls(cli_runner, list(urls_to_add))

    app = provide_app
    user_id_for_test = 1

    login_user_and_select_utub_by_name(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1
    )

    assert get_num_url_rows(browser) == num_of_urls_to_add

    init_num_of_tabs = len(browser.window_handles)
    init_tab = browser.current_window_handle

    browser.find_element(By.CSS_SELECTOR, HPL.BUTTON_ACCESS_ALL_URLS).click()

    # Modal will now show since number of URLs is equal to max number of URLs
    access_modal = wait_then_get_element(browser, HPL.ACCESS_ALL_URL_MODAL)
    assert access_modal is not None
    assert access_modal.is_displayed()
    access_modal.find_element(By.CSS_SELECTOR, HPL.BUTTON_MODAL_SUBMIT).click()

    curr_tabs = browser.window_handles

    assert init_num_of_tabs + num_of_urls_to_add == len(curr_tabs)

    for handle in curr_tabs:
        if handle != init_tab:
            browser.switch_to.window(handle)
            browser_url_hostname = urlsplit(browser.current_url).hostname
            assert browser_url_hostname is not None
            assert any([browser_url_hostname in url for url in MOCK_URL_STRINGS])

    browser.switch_to.window(init_tab)

    with pytest.raises(NoSuchElementException):
        browser.find_element(By.CSS_SELECTOR, HPL.ACCESS_ALL_URL_MODAL)


def test_access_all_urls_above_limit_cancel_modal_dismiss_btn(
    browser: WebDriver,
    runner: Tuple[Flask, FlaskCliRunner],
    create_test_utubs,
    provide_app: Flask,
):
    """
    Tests a user's ability to access all URLs via access all URLs button, but access all modal warning shows, and user decides to cancel by pressing the dismiss button

    GIVEN access to UTubs and URLs, and number of URLs is less than max number of URLs before warning modal is shown
    WHEN a user clicks access URL button, the warning modal is shown, and user clicks the dismiss button
    THEN ensure no new URLs are opened and the modal is hidden
    """
    _, cli_runner = runner
    num_of_urls_to_add = URL_CONSTANTS.MAX_NUM_OF_URLS_TO_ACCESS + 1

    # Randomize URLs chosen to prevent any chance of looking like a bot
    urls_to_add = random.sample(MOCK_URL_STRINGS, num_of_urls_to_add)
    add_mock_urls(cli_runner, list(urls_to_add))

    app = provide_app
    user_id_for_test = 1

    login_user_and_select_utub_by_name(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1
    )

    assert get_num_url_rows(browser) == num_of_urls_to_add

    init_num_of_tabs = len(browser.window_handles)

    browser.find_element(By.CSS_SELECTOR, HPL.BUTTON_ACCESS_ALL_URLS).click()

    # Modal will now show since number of URLs is equal to max number of URLs
    access_modal = wait_then_get_element(browser, HPL.ACCESS_ALL_URL_MODAL)
    assert access_modal is not None
    assert access_modal.is_displayed()
    access_modal.find_element(By.CSS_SELECTOR, HPL.BUTTON_MODAL_DISMISS).click()

    curr_tabs = browser.window_handles

    assert init_num_of_tabs == len(curr_tabs)

    wait_until_hidden(browser, HPL.ACCESS_ALL_URL_MODAL)
    assert not access_modal.is_displayed()


def test_access_all_urls_above_limit_cancel_modal_x_btn(
    browser: WebDriver,
    runner: Tuple[Flask, FlaskCliRunner],
    create_test_utubs,
    provide_app: Flask,
):
    """
    Tests a user's ability to access all URLs via access all URLs button, but access all modal warning shows, and user decides to cancel by pressing the dismiss button

    GIVEN access to UTubs and URLs, and number of URLs is less than max number of URLs before warning modal is shown
    WHEN a user clicks access URL button, the warning modal is shown, and user clicks the x corner button for the modal
    THEN ensure no new URLs are opened and the modal is hidden
    """
    _, cli_runner = runner
    num_of_urls_to_add = URL_CONSTANTS.MAX_NUM_OF_URLS_TO_ACCESS + 1

    # Randomize URLs chosen to prevent any chance of looking like a bot
    urls_to_add = random.sample(MOCK_URL_STRINGS, num_of_urls_to_add)
    add_mock_urls(cli_runner, list(urls_to_add))

    app = provide_app
    user_id_for_test = 1

    login_user_and_select_utub_by_name(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1
    )

    assert get_num_url_rows(browser) == num_of_urls_to_add

    init_num_of_tabs = len(browser.window_handles)

    browser.find_element(By.CSS_SELECTOR, HPL.BUTTON_ACCESS_ALL_URLS).click()

    # Modal will now show since number of URLs is equal to max number of URLs
    access_modal = wait_then_get_element(browser, HPL.ACCESS_ALL_URL_MODAL)
    assert access_modal is not None
    assert access_modal.is_displayed()
    access_modal.find_element(By.CSS_SELECTOR, HPL.BUTTON_X_CLOSE).click()

    curr_tabs = browser.window_handles

    assert init_num_of_tabs == len(curr_tabs)

    wait_until_hidden(browser, HPL.ACCESS_ALL_URL_MODAL)
    assert not access_modal.is_displayed()


def test_access_all_urls_above_limit_cancel_modal_by_clicking_outside_modal(
    browser: WebDriver,
    runner: Tuple[Flask, FlaskCliRunner],
    create_test_utubs,
    provide_app: Flask,
):
    """
    Tests a user's ability to access all URLs via access all URLs button, but access all modal warning shows, and user decides to cancel by pressing the dismiss button

    GIVEN access to UTubs and URLs, and number of URLs is less than max number of URLs before warning modal is shown
    WHEN a user clicks access URL button, the warning modal is shown, and user clicks outside the modal
    THEN ensure no new URLs are opened and the modal is hidden
    """
    _, cli_runner = runner
    num_of_urls_to_add = URL_CONSTANTS.MAX_NUM_OF_URLS_TO_ACCESS + 1

    # Randomize URLs chosen to prevent any chance of looking like a bot
    urls_to_add = random.sample(MOCK_URL_STRINGS, num_of_urls_to_add)
    add_mock_urls(cli_runner, list(urls_to_add))

    app = provide_app
    user_id_for_test = 1

    login_user_and_select_utub_by_name(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1
    )

    assert get_num_url_rows(browser) == num_of_urls_to_add

    init_num_of_tabs = len(browser.window_handles)

    browser.find_element(By.CSS_SELECTOR, HPL.BUTTON_ACCESS_ALL_URLS).click()

    # Modal will now show since number of URLs is equal to max number of URLs
    access_modal = wait_then_get_element(browser, HPL.ACCESS_ALL_URL_MODAL)
    assert access_modal is not None
    assert access_modal.is_displayed()
    dismiss_modal_with_click_out(browser)

    curr_tabs = browser.window_handles

    assert init_num_of_tabs == len(curr_tabs)

    wait_until_hidden(browser, HPL.ACCESS_ALL_URL_MODAL)
    assert not access_modal.is_displayed()


def test_access_to_urls_as_utub_owner(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    Tests a UTub owner's ability to have all capabilities available when selecting a URL

    GIVEN access to UTubs and URLs as a UTub owner
    WHEN the UTub owner selects any URL
    THEN verify that all capabilities are available, including:
        Edit URL
        Add Tag
        Access URL
        Delete URL
        Edit URL Title
    """

    app = provide_app
    user_id_for_test = 1

    login_user_and_select_utub_by_name(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1
    )

    url_rows = wait_then_get_elements(browser, HPL.ROWS_URLS)
    assert url_rows is not None

    for url_row in url_rows:
        wait_for_web_element_and_click(browser, url_row)
        assert get_selected_url(browser) == url_row
        verify_select_url_as_utub_owner_or_url_creator(browser, url_row)


def test_access_to_non_added_urls_as_utub_member(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    Tests a UTub member's ability to have limited capability when selecting a URL they did not make

    GIVEN access to UTubs and URLs as a UTub owner
    WHEN the UTub member selects any URL that they didn't add
    THEN:
     Verify that not all capabilities are available for URLs they did not add, including:
        Edit URL
        Delete URL
        Edit URL Title
     Verify that only the following capabilities are available for URLs they did not add:
        Add Tag
        Access URL
    """

    app = provide_app
    user_id_for_test = 1

    login_user_and_select_utub_by_name(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_2
    )

    utub_id = get_selected_utub_id(browser)
    user_id = get_current_user_id(browser)
    utub_url_id_user_added = get_utub_url_id_for_added_url_in_utub_as_member(
        app, utub_id, user_id
    )

    url_rows = wait_then_get_elements(browser, HPL.ROWS_URLS)
    assert url_rows is not None

    for url_row in url_rows:
        wait_for_web_element_and_click(browser, url_row)
        assert get_selected_url(browser) == url_row

        current_utub_url_id = url_row.get_attribute("urlid")
        if int(current_utub_url_id) != utub_url_id_user_added:
            verify_select_url_as_non_utub_owner_and_non_url_adder(browser, url_row)


def test_access_to_urls_as_url_creator_and_utub_member(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    Tests a UTub member's ability to have limited capability when selecting a URL they did not make

    GIVEN access to UTubs and URLs as a UTub owner
    WHEN the UTub member selects any URL that they didn't add
    THEN:
     Verify that the following capabilities are available when they added the URL:
        Edit URL
        Delete URL
        Edit URL Title
        Add Tag
        Access URL
    """

    app = provide_app
    user_id_for_test = 1

    login_user_and_select_utub_by_name(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_2
    )

    utub_id = get_selected_utub_id(browser)
    user_id = get_current_user_id(browser)
    utub_url_id_user_added = get_utub_url_id_for_added_url_in_utub_as_member(
        app, utub_id, user_id
    )

    url_rows = wait_then_get_elements(browser, HPL.ROWS_URLS)
    assert url_rows is not None

    for url_row in url_rows:
        wait_for_web_element_and_click(browser, url_row)
        assert get_selected_url(browser) == url_row

        current_utub_url_id = url_row.get_attribute("urlid")
        if int(current_utub_url_id) == utub_url_id_user_added:
            verify_select_url_as_utub_owner_or_url_creator(browser, url_row)
