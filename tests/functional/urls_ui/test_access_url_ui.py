# Standard library

# External libraries
from flask import Flask
import pytest
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By

# Internal libraries
from src.mocks.mock_constants import MOCK_URL_STRINGS
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.locators import MainPageLocators as MPL
from tests.functional.utils_for_test import (
    get_selected_url,
    login_user_and_select_utub_by_name,
    login_user_select_utub_by_name_and_url_by_title,
    login_utub_url,
    wait_then_get_elements,
)


def test_access_url_by_access_btn_while_selected(
    browser: WebDriver, create_test_urls, provide_app_for_session_generation: Flask
):
    """
    Tests a user's ability to navigate to a URL using the URLOptions button.

    GIVEN access to UTubs and URLs
    WHEN a user selects a URL and clicks 'Access URL' button
    THEN ensure the URL opens in a new tab
    """
    app = provide_app_for_session_generation
    user_id_for_test = 1
    login_user_select_utub_by_name_and_url_by_title(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1, UTS.TEST_URL_TITLE_1
    )

    url_row = get_selected_url(browser)

    init_num_of_tabs = len(browser.window_handles)
    init_tab = browser.current_window_handle

    url_row.find_element(By.CSS_SELECTOR, MPL.BUTTON_URL_ACCESS).click()

    curr_tabs = browser.window_handles

    assert init_num_of_tabs + 1 == len(curr_tabs)

    for handle in curr_tabs:
        if handle != init_tab:
            browser.switch_to.window(handle)
            assert browser.current_url in MOCK_URL_STRINGS


def test_access_url_by_goto_btn_while_selected(
    browser: WebDriver, create_test_urls, provide_app_for_session_generation: Flask
):
    """
    Tests a user's ability to navigate to a URL using the URLOptions button.

    GIVEN access to UTubs and URLs
    WHEN a user selects a URL and clicks the URL Go-To button
    THEN ensure the URL opens in a new tab
    """
    app = provide_app_for_session_generation
    user_id_for_test = 1
    login_user_select_utub_by_name_and_url_by_title(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1, UTS.TEST_URL_TITLE_1
    )

    url_row = get_selected_url(browser)

    init_num_of_tabs = len(browser.window_handles)
    init_tab = browser.current_window_handle

    url_row.find_element(By.CSS_SELECTOR, MPL.GO_TO_URL_ICON).click()

    curr_tabs = browser.window_handles

    assert init_num_of_tabs + 1 == len(curr_tabs)

    for handle in curr_tabs:
        if handle != init_tab:
            browser.switch_to.window(handle)
            assert browser.current_url in MOCK_URL_STRINGS


def test_access_url_by_goto_btn_while_hover(
    browser: WebDriver, create_test_urls, provide_app_for_session_generation: Flask
):
    """
    Tests a user's ability to navigate to a URL using the URLOptions button.

    GIVEN access to UTubs and URLs
    WHEN a user hovers over a URL and clicks the URL Go-To button
    THEN ensure the URL opens in a new tab
    """
    app = provide_app_for_session_generation
    user_id_for_test = 1
    login_user_and_select_utub_by_name(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1
    )

    init_num_of_tabs = len(browser.window_handles)
    init_tab = browser.current_window_handle

    url_row = wait_then_get_elements(browser, MPL.ROWS_URLS)
    assert url_row is not None
    url_row = url_row[0]

    actions = ActionChains(browser)
    actions.move_to_element(url_row).perform()

    url_row.find_element(By.CSS_SELECTOR, MPL.GO_TO_URL_ICON).click()
    curr_tabs = browser.window_handles

    assert init_num_of_tabs + 1 == len(curr_tabs)

    for handle in curr_tabs:
        if handle != init_tab:
            browser.switch_to.window(handle)
            assert browser.current_url in MOCK_URL_STRINGS


@pytest.mark.skip(reason="Test not yet implemented")
def test_access_url_by_text(browser: WebDriver, create_test_urls):
    """
    Tests a user's ability to navigate to a URL using the displayed URL string.

    GIVEN access to UTubs and URLs
    WHEN a user clicks the URL text
    THEN ensure the URL opens in a new tab
    """

    login_utub_url(browser)

    url_row = get_selected_url(browser)

    url_row.find_element(By.CSS_SELECTOR, MPL.BUTTON_URL_ACCESS).click()

    # Assert new tab is opened and navigated to url string
