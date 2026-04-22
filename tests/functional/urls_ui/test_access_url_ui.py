import random
from typing import Tuple
from flask import Flask
from flask.testing import FlaskCliRunner
import pytest
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By

from backend.cli.mock_constants import MOCK_TEST_URL_STRINGS
from backend.utils.constants import STRINGS
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.assert_utils import assert_tooltip_animates
from tests.functional.db_utils import (
    add_mock_urls,
    get_url_in_utub,
    get_utub_this_user_created,
    get_utub_url_id_by_url_string,
    get_utub_url_id_for_added_url_in_utub_as_member,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.login_utils import (
    login_user_and_select_utub_by_name,
    login_user_and_select_utub_by_utubid,
    login_user_select_utub_by_id_and_url_by_id,
    login_user_select_utub_by_name_and_url_by_string,
    login_user_select_utub_by_name_and_url_by_title,
)
from tests.functional.urls_ui.assert_utils import (
    assert_select_url_as_non_utub_owner_and_non_url_adder,
    assert_select_url_as_utub_owner_or_url_creator,
)
from tests.functional.selenium_utils import (
    get_all_url_ids_in_selected_utub,
    get_selected_utub_id,
    get_selected_url,
    get_url_row_by_id,
    wait_for_web_element_and_click,
    wait_then_get_element,
    wait_until_hidden,
    wait_until_visible_css_selector,
)

pytestmark = pytest.mark.urls_ui


def test_access_url_by_access_btn_while_selected_tooltip_animates(
    browser, create_test_access_urls, provide_app: Flask
):
    """
    Tests a member's ability to see the tooltip animate when hovering over the big access URL button.

    GIVEN a user in a UTub with URLs
    WHEN the user selects a URL, and hovers over the big access URL button
    THEN ensure the tooltip for the big access URL button is animated properly
    """
    app = provide_app
    user_id_for_test = 1
    utub = get_utub_this_user_created(app, user_id=user_id_for_test)
    utub_url = get_url_in_utub(app, utub_id=utub.id)

    login_user_select_utub_by_name_and_url_by_title(
        app, browser, user_id_for_test, utub.name, utub_url.url_title
    )

    assert_tooltip_animates(
        browser=browser,
        parent_css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_ACCESS}",
        tooltip_parent_class=HPL.BUTTON_URL_ACCESS,
        tooltip_text=STRINGS.ACCESS_URL_TOOLTIP,
    )


def test_access_url_by_access_btn_while_selected(
    browser: WebDriver, create_test_access_urls, provide_app: Flask
):
    """
    Tests a user's ability to navigate to a URL using the URLOptions button.

    GIVEN access to UTubs and URLs
    WHEN a user selects a URL and clicks 'Access URL' button
    THEN ensure the URL opens in a new tab
    """
    app = provide_app
    user_id_for_test = 1

    url_to_select = random.sample(MOCK_TEST_URL_STRINGS, 1)[0]
    utub = get_utub_this_user_created(app, user_id_for_test)
    utub_url_id = get_utub_url_id_by_url_string(app, utub.id, url_to_select)

    login_user_select_utub_by_id_and_url_by_id(
        app, browser, user_id_for_test, utub.id, utub_url_id
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
            assert browser.current_url in MOCK_TEST_URL_STRINGS


def test_access_url_by_goto_btn_while_selected(
    browser: WebDriver, create_test_access_urls, provide_app: Flask
):
    """
    Tests a user's ability to navigate to a URL using the URLOptions button.

    GIVEN access to UTubs and URLs
    WHEN a user selects a URL and clicks the URL Go-To button
    THEN ensure the URL opens in a new tab
    """
    app = provide_app
    user_id_for_test = 1

    url_to_select = random.sample(MOCK_TEST_URL_STRINGS, 1)[0]
    utub = get_utub_this_user_created(app, user_id_for_test)
    utub_url_id = get_utub_url_id_by_url_string(app, utub.id, url_to_select)
    login_user_select_utub_by_id_and_url_by_id(
        app, browser, user_id_for_test, utub.id, utub_url_id
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
            assert browser.current_url in MOCK_TEST_URL_STRINGS


def test_access_url_by_goto_btn_while_hover(
    browser: WebDriver, create_test_access_urls, provide_app: Flask
):
    """
    Tests a user's ability to navigate to a URL using the URLOptions button.

    GIVEN access to UTubs and URLs
    WHEN a user hovers over a URL and clicks the URL Go-To button
    THEN ensure the URL opens in a new tab
    """
    app = provide_app
    user_id_for_test = 1

    url_to_add = random.sample(MOCK_TEST_URL_STRINGS, 1)[0]
    utub = get_utub_this_user_created(app, user_id_for_test)
    utub_url_id = get_utub_url_id_by_url_string(app, utub.id, url_to_add)

    login_user_and_select_utub_by_utubid(
        app, browser, user_id_for_test, utub_id=utub.id
    )

    init_num_of_tabs = len(browser.window_handles)
    init_tab = browser.current_window_handle

    url_row = get_url_row_by_id(browser, utub_url_id)
    assert url_row is not None

    actions = ActionChains(browser)
    actions.move_to_element(url_row).perform()

    url_row.find_element(By.CSS_SELECTOR, HPL.GO_TO_URL_ICON).click()
    curr_tabs = browser.window_handles

    assert init_num_of_tabs + 1 == len(curr_tabs)

    for handle in curr_tabs:
        if handle != init_tab:
            browser.switch_to.window(handle)
            assert browser.current_url in MOCK_TEST_URL_STRINGS


def test_access_url_by_clicking_url_string(
    browser: WebDriver, create_test_access_urls, provide_app: Flask
):
    """
    Tests a user's ability to navigate to a URL using the displayed URL string.

    GIVEN access to UTubs and URLs
    WHEN a user clicks the URL text
    THEN ensure the URL opens in a new tab
    """

    app = provide_app
    user_id_for_test = 1

    url_to_click = random.sample(MOCK_TEST_URL_STRINGS, 1)
    login_user_select_utub_by_name_and_url_by_string(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1, url_to_click[0]
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
        if handle == init_tab:
            continue

        browser.switch_to.window(handle)
        assert browser.current_url in MOCK_TEST_URL_STRINGS


def test_access_non_http_url_by_clicking_url_string_submit(
    browser: WebDriver,
    runner: Tuple[Flask, FlaskCliRunner],
    create_test_access_urls,
    provide_app: Flask,
):
    """
    Tests a user's ability to navigate to a URL using the displayed URL string.

    GIVEN access to UTubs and URLs
    WHEN a user clicks the URL text
    THEN ensure the URL opens in a new tab
    """

    app = provide_app
    user_id_for_test = 1

    _, cli_runner = runner
    mailto_url = "mailto:fakeemail@fake.email"
    utub = get_utub_this_user_created(app, user_id_for_test)
    add_mock_urls(
        cli_runner,
        [
            mailto_url,
        ],
    )
    url_in_utub_id = get_utub_url_id_by_url_string(app, utub.id, mailto_url)

    login_user_select_utub_by_id_and_url_by_id(
        app, browser, user_id_for_test, utub_id=utub.id, utub_url_id=url_in_utub_id
    )

    url_row = get_selected_url(browser)

    init_num_of_tabs = len(browser.window_handles)
    url_row.find_element(By.CSS_SELECTOR, HPL.URL_STRING_READ).click()

    access_modal = wait_then_get_element(browser, HPL.ACCESS_EXTERNAL_URL_MODAL)
    assert access_modal is not None
    assert access_modal.is_displayed()
    access_modal.find_element(By.CSS_SELECTOR, HPL.BUTTON_MODAL_SUBMIT).click()

    curr_tabs = browser.window_handles

    assert init_num_of_tabs + 1 == len(curr_tabs)


def test_access_non_http_url_by_clicking_url_string_cancel(
    browser: WebDriver,
    runner: Tuple[Flask, FlaskCliRunner],
    create_test_access_urls,
    provide_app: Flask,
):
    """
    Tests a user's ability to navigate to a URL using the displayed URL string.

    GIVEN access to UTubs and URLs
    WHEN a user clicks the URL text
    THEN ensure the URL opens in a new tab
    """

    app = provide_app
    user_id_for_test = 1

    _, cli_runner = runner
    mailto_url = "mailto:fakeemail@fake.email"
    add_mock_urls(
        cli_runner,
        [
            mailto_url,
        ],
    )
    utub = get_utub_this_user_created(app, user_id_for_test)
    url_in_utub_id = get_utub_url_id_by_url_string(app, utub.id, mailto_url)

    login_user_select_utub_by_id_and_url_by_id(
        app, browser, user_id_for_test, utub_id=utub.id, utub_url_id=url_in_utub_id
    )

    url_row = get_selected_url(browser)
    init_num_of_tabs = len(browser.window_handles)

    url_row.find_element(By.CSS_SELECTOR, HPL.URL_STRING_READ).click()

    access_modal = wait_then_get_element(browser, HPL.ACCESS_EXTERNAL_URL_MODAL)
    assert access_modal is not None
    assert access_modal.is_displayed()
    access_modal.find_element(By.CSS_SELECTOR, HPL.BUTTON_MODAL_DISMISS).click()

    curr_tabs = browser.window_handles
    assert init_num_of_tabs == len(curr_tabs)

    wait_until_hidden(browser, HPL.HOME_MODAL)
    assert not access_modal.is_displayed()


def test_access_to_urls_as_utub_owner(
    browser: WebDriver, create_test_access_urls, provide_app: Flask
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
        wait_until_visible_css_selector(browser, url_selector, timeout=3)

        url_row = browser.find_element(By.CSS_SELECTOR, url_selector)
        wait_for_web_element_and_click(browser, url_row)

        # Now wait for access link button to show up, which is accessible to all users
        wait_until_visible_css_selector(
            browser,
            HPL.ROW_SELECTED_URL
            + f"[utuburlid='{url_utub_id}'] {HPL.BUTTON_URL_ACCESS}",
        )

        selected_url = get_selected_url(browser)
        selected_urlid = selected_url.get_attribute("utuburlid")
        assert selected_urlid and selected_urlid.isdigit()
        assert url_utub_id == int(selected_urlid)

        assert_select_url_as_utub_owner_or_url_creator(browser, url_selector)


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
    utub_url_id_user_added = get_utub_url_id_for_added_url_in_utub_as_member(
        app, utub_id, user_id_for_test
    )

    url_utub_ids = get_all_url_ids_in_selected_utub(browser)

    for url_utub_id in url_utub_ids:
        url_selector = f"{HPL.ROWS_URLS}[utuburlid='{url_utub_id}']"
        wait_until_visible_css_selector(browser, url_selector, timeout=3)

        url_row = browser.find_element(By.CSS_SELECTOR, url_selector)
        wait_for_web_element_and_click(browser, url_row)
        # Now wait for access link button to show up, which is accessible to all users
        wait_until_visible_css_selector(
            browser,
            HPL.ROW_SELECTED_URL
            + f"[utuburlid='{url_utub_id}'] {HPL.BUTTON_URL_ACCESS}",
        )

        selected_url = get_selected_url(browser)
        selected_urlid = selected_url.get_attribute("utuburlid")
        assert selected_urlid and selected_urlid.isdigit()
        assert url_utub_id == int(selected_urlid)

        if url_utub_id != utub_url_id_user_added:
            assert_select_url_as_non_utub_owner_and_non_url_adder(browser, url_selector)


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
    utub_url_id_user_added = get_utub_url_id_for_added_url_in_utub_as_member(
        app, utub_id, user_id_for_test
    )

    url_utub_ids = get_all_url_ids_in_selected_utub(browser)

    for url_utub_id in url_utub_ids:
        url_selector = f"{HPL.ROWS_URLS}[utuburlid='{url_utub_id}']"
        wait_until_visible_css_selector(browser, url_selector, timeout=3)

        url_row = browser.find_element(By.CSS_SELECTOR, url_selector)
        wait_for_web_element_and_click(browser, url_row)
        # Now wait for access link button to show up, which is accessible to all users
        wait_until_visible_css_selector(
            browser,
            HPL.ROW_SELECTED_URL
            + f"[utuburlid='{url_utub_id}'] {HPL.BUTTON_URL_ACCESS}",
        )

        selected_url = get_selected_url(browser)
        selected_urlid = selected_url.get_attribute("utuburlid")
        assert selected_urlid and selected_urlid.isdigit()
        assert url_utub_id == int(selected_urlid)

        if url_utub_id == utub_url_id_user_added:
            assert_select_url_as_utub_owner_or_url_creator(browser, url_selector)
