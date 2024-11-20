# External libraries
from flask import Flask
import pytest
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver

# Internal libraries
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.locators import MainPageLocators as MPL
from tests.functional.urls_ui.utils_for_test_url_ui import (
    get_selected_utub_id,
    get_utub_url_id_for_added_url_in_utub_as_member,
    verify_keyed_url_is_selected,
    verify_select_url_as_non_utub_owner_and_non_url_adder,
    verify_select_url_as_utub_owner_or_url_creator,
)
from tests.functional.utils_for_test import (
    get_current_user_id,
    get_selected_url,
    login_user_and_select_utub_by_name,
    wait_for_web_element_and_click,
    wait_then_get_elements,
)

pytestmark = pytest.mark.urls_ui


def test_select_urls_as_utub_owner(
    browser: WebDriver, create_test_urls, provide_app_for_session_generation: Flask
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

    app = provide_app_for_session_generation
    user_id_for_test = 1

    login_user_and_select_utub_by_name(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1
    )

    url_rows = wait_then_get_elements(browser, MPL.ROWS_URLS)
    assert url_rows is not None

    for url_row in url_rows:
        wait_for_web_element_and_click(browser, url_row)
        assert get_selected_url(browser) == url_row
        verify_select_url_as_utub_owner_or_url_creator(browser, url_row)


def test_select_non_added_urls_as_utub_member(
    browser: WebDriver, create_test_urls, provide_app_for_session_generation: Flask
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

    app = provide_app_for_session_generation
    user_id_for_test = 1

    login_user_and_select_utub_by_name(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_2
    )

    utub_id = get_selected_utub_id(browser)
    user_id = get_current_user_id(browser)
    utub_url_id_user_added = get_utub_url_id_for_added_url_in_utub_as_member(
        app, utub_id, user_id
    )

    url_rows = wait_then_get_elements(browser, MPL.ROWS_URLS)
    assert url_rows is not None

    for url_row in url_rows:
        wait_for_web_element_and_click(browser, url_row)
        assert get_selected_url(browser) == url_row

        current_utub_url_id = url_row.get_attribute("urlid")
        if int(current_utub_url_id) != utub_url_id_user_added:
            verify_select_url_as_non_utub_owner_and_non_url_adder(browser, url_row)


def test_select_urls_as_url_creator_and_utub_member(
    browser: WebDriver, create_test_urls, provide_app_for_session_generation: Flask
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

    app = provide_app_for_session_generation
    user_id_for_test = 1

    login_user_and_select_utub_by_name(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_2
    )

    utub_id = get_selected_utub_id(browser)
    user_id = get_current_user_id(browser)
    utub_url_id_user_added = get_utub_url_id_for_added_url_in_utub_as_member(
        app, utub_id, user_id
    )

    url_rows = wait_then_get_elements(browser, MPL.ROWS_URLS)
    assert url_rows is not None

    for url_row in url_rows:
        wait_for_web_element_and_click(browser, url_row)
        assert get_selected_url(browser) == url_row

        current_utub_url_id = url_row.get_attribute("urlid")
        if int(current_utub_url_id) == utub_url_id_user_added:
            verify_select_url_as_utub_owner_or_url_creator(browser, url_row)


def test_select_urls_using_down_key(
    browser: WebDriver, create_test_urls, provide_app_for_session_generation: Flask
):
    """
    Tests ability to scroll downwards through the URLs using the down key when a URL is selected

    GIVEN access to URLs in a UTub
    WHEN the user selects a URL and then presses the down key
    THEN verify that the URLs are scrolled through
    """

    app = provide_app_for_session_generation
    user_id_for_test = 1

    login_user_and_select_utub_by_name(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_2
    )

    url_rows = wait_then_get_elements(browser, MPL.ROWS_URLS)
    if not url_rows:
        assert False
    num_of_urls = len(url_rows)

    # Select first URL
    wait_for_web_element_and_click(browser, url_rows[0])
    verify_keyed_url_is_selected(browser, url_rows[0])

    for idx in range(1, num_of_urls + 1):
        next_url_idx = idx % num_of_urls
        browser.switch_to.active_element.send_keys(Keys.DOWN)
        verify_keyed_url_is_selected(browser, url_rows[next_url_idx])


def test_select_urls_using_up_key(
    browser: WebDriver, create_test_urls, provide_app_for_session_generation: Flask
):
    """
    Tests ability to scroll upwards through the URLs using the up key when a URL is selected

    GIVEN access to URLs in a UTub
    WHEN the user selects a URL and then presses the up key
    THEN verify that the URLs are scrolled through
    """

    app = provide_app_for_session_generation
    user_id_for_test = 1

    login_user_and_select_utub_by_name(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_2
    )

    url_rows = wait_then_get_elements(browser, MPL.ROWS_URLS)
    if not url_rows:
        assert False
    num_of_urls = len(url_rows)

    # Select first URL
    wait_for_web_element_and_click(browser, url_rows[0])
    verify_keyed_url_is_selected(browser, url_rows[0])

    for idx in range(num_of_urls - 1, -1, -1):
        browser.switch_to.active_element.send_keys(Keys.UP)
        verify_keyed_url_is_selected(browser, url_rows[idx])