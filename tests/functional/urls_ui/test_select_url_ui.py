from flask import Flask
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver

from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.db_utils import get_utub_url_id_for_added_url_in_utub_as_member
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.login_utils import login_user_and_select_utub_by_name
from tests.functional.urls_ui.assert_utils import (
    assert_keyed_url_is_selected,
    assert_select_url_as_non_utub_owner_and_non_url_adder,
    assert_select_url_as_utub_owner_or_url_creator,
)
from tests.functional.selenium_utils import (
    get_all_url_ids_in_selected_utub,
    get_selected_url,
    get_selected_utub_id,
    wait_for_animation_to_end,
    wait_for_web_element_and_click,
    wait_then_get_elements,
    wait_until_visible_css_selector,
)

pytestmark = pytest.mark.urls_ui


def test_select_urls_as_utub_owner(
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

    url_utub_ids = get_all_url_ids_in_selected_utub(browser)

    for url_utub_id in url_utub_ids:
        url_selector = f"{HPL.ROWS_URLS}[utuburlid='{url_utub_id}']"
        wait_until_visible_css_selector(browser, url_selector)

        url_row = browser.find_element(By.CSS_SELECTOR, url_selector)
        wait_for_web_element_and_click(browser, url_row)

        url_row = browser.find_element(By.CSS_SELECTOR, url_selector)
        assert get_selected_url(browser) == url_row
        assert_select_url_as_utub_owner_or_url_creator(browser, url_selector)


def test_select_non_added_urls_as_utub_member(
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
    utub_url_id_user_added = get_utub_url_id_for_added_url_in_utub_as_member(
        app, utub_id, user_id_for_test
    )

    url_utub_ids = get_all_url_ids_in_selected_utub(browser)

    for url_utub_id in url_utub_ids:
        url_selector = f"{HPL.ROWS_URLS}[utuburlid='{url_utub_id}']"
        wait_until_visible_css_selector(browser, url_selector)

        url_row = browser.find_element(By.CSS_SELECTOR, url_selector)
        wait_for_web_element_and_click(browser, url_row)

        url_row = browser.find_element(By.CSS_SELECTOR, url_selector)
        assert get_selected_url(browser) == url_row

        url_row = browser.find_element(By.CSS_SELECTOR, url_selector)
        current_utub_url_id = url_row.get_attribute("utuburlid")
        assert current_utub_url_id and current_utub_url_id.isnumeric()
        if url_utub_id != utub_url_id_user_added:
            assert_select_url_as_non_utub_owner_and_non_url_adder(browser, url_selector)


def test_select_urls_as_url_creator_and_utub_member(
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
    utub_url_id_user_added = get_utub_url_id_for_added_url_in_utub_as_member(
        app, utub_id, user_id_for_test
    )

    url_utub_ids = get_all_url_ids_in_selected_utub(browser)

    for url_utub_id in url_utub_ids:
        url_selector = f"{HPL.ROWS_URLS}[utuburlid='{url_utub_id}']"
        wait_until_visible_css_selector(browser, url_selector)

        url_row = browser.find_element(By.CSS_SELECTOR, url_selector)
        wait_for_web_element_and_click(browser, url_row)

        selected_url_id = get_selected_url(browser).get_attribute("utuburlid")
        assert selected_url_id is not None and selected_url_id.isnumeric()
        assert int(selected_url_id) == url_utub_id

        url_row = browser.find_element(By.CSS_SELECTOR, url_selector)
        current_utub_url_id = url_row.get_attribute("utuburlid")
        assert current_utub_url_id and current_utub_url_id.isnumeric()
        if url_utub_id != utub_url_id_user_added:
            assert_select_url_as_non_utub_owner_and_non_url_adder(browser, url_selector)


def test_select_urls_using_down_key(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    Tests ability to scroll downwards through the URLs using the down key when a URL is selected

    GIVEN access to URLs in a UTub
    WHEN the user selects a URL and then presses the down key
    THEN verify that the URLs are scrolled through
    """

    app = provide_app
    user_id_for_test = 1

    login_user_and_select_utub_by_name(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_2
    )

    url_rows = wait_then_get_elements(browser, HPL.ROWS_URLS)
    if not url_rows:
        assert False
    num_of_urls = len(url_rows)

    # Select first URL
    wait_for_web_element_and_click(browser, url_rows[0])
    first_url_string = (
        url_rows[0].find_element(By.CSS_SELECTOR, HPL.URL_STRING_READ).text
    )
    wait_for_animation_to_end(
        browser, f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_ACCESS}"
    )
    selected_url = get_selected_url(browser)
    assert (
        selected_url.find_element(By.CSS_SELECTOR, HPL.URL_STRING_READ).text
        == first_url_string
    )
    assert_keyed_url_is_selected(browser, url_rows[0])

    for idx in range(1, num_of_urls + 1):
        next_url_idx = idx % num_of_urls
        next_url_string = (
            url_rows[next_url_idx]
            .find_element(By.CSS_SELECTOR, HPL.URL_STRING_READ)
            .text
        )
        browser.switch_to.active_element.send_keys(Keys.DOWN)
        selected_url = get_selected_url(browser)
        assert (
            selected_url.find_element(By.CSS_SELECTOR, HPL.URL_STRING_READ).text
            == next_url_string
        )
        assert_keyed_url_is_selected(browser, url_rows[next_url_idx])


def test_select_urls_using_up_key(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    Tests ability to scroll upwards through the URLs using the up key when a URL is selected

    GIVEN access to URLs in a UTub
    WHEN the user selects a URL and then presses the up key
    THEN verify that the URLs are scrolled through
    """

    app = provide_app
    user_id_for_test = 1

    login_user_and_select_utub_by_name(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_2
    )

    url_rows = wait_then_get_elements(browser, HPL.ROWS_URLS)
    if not url_rows:
        assert False
    num_of_urls = len(url_rows)

    # Select first URL
    wait_for_web_element_and_click(browser, url_rows[0])
    first_url_string = (
        url_rows[0].find_element(By.CSS_SELECTOR, HPL.URL_STRING_READ).text
    )
    wait_for_animation_to_end(
        browser, f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_ACCESS}"
    )
    selected_url = get_selected_url(browser)
    assert (
        selected_url.find_element(By.CSS_SELECTOR, HPL.URL_STRING_READ).text
        == first_url_string
    )
    assert_keyed_url_is_selected(browser, url_rows[0])

    for idx in range(num_of_urls - 1, -1, -1):
        next_url_string = (
            url_rows[idx].find_element(By.CSS_SELECTOR, HPL.URL_STRING_READ).text
        )
        browser.switch_to.active_element.send_keys(Keys.UP)
        selected_url = get_selected_url(browser)
        assert (
            selected_url.find_element(By.CSS_SELECTOR, HPL.URL_STRING_READ).text
            == next_url_string
        )
        assert_keyed_url_is_selected(browser, url_rows[idx])
