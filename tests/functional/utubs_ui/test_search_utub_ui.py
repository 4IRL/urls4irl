from flask import Flask
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

from tests.functional.assert_utils import (
    assert_not_visible_css_selector,
    assert_visible_css_selector,
    assert_active_utub,
)
from tests.functional.db_utils import create_test_searchable_utubs
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.login_utils import (
    login_user_and_select_utub_by_utubid,
    login_user_to_home_page,
)
from tests.functional.selenium_utils import (
    wait_for_element_to_be_removed,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_hidden,
    wait_until_visible_css_selector,
)
from tests.functional.utubs_ui.selenium_utils import (
    create_utub,
    open_utub_search_box,
)

pytestmark = pytest.mark.utubs_ui


def test_utub_search_box_opens_on_click_and_focused(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    GIVEN a fresh load of the U4i Home page, where user is in multiple UTubs
    WHEN user clicks on the UTub search icon
    THEN ensure the all appropriate elements are visible and ready and input is focused
    """
    app = provide_app
    user_id_for_test = 1

    login_user_to_home_page(app, browser, user_id_for_test)
    open_utub_search_box(browser)
    assert_not_visible_css_selector(browser, HPL.UTUB_OPEN_SEARCH_ICON)
    assert_visible_css_selector(browser, HPL.UTUB_CLOSE_SEARCH_ICON)
    assert_visible_css_selector(browser, HPL.UTUB_SEARCH_INPUT)


def test_utub_search_box_closes_on_click(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    GIVEN a fresh load of the U4i Home page, where user is in multiple UTubs, and user has UTub search open
    WHEN user clicks on the close UTub search icon
    THEN ensure the all appropriate elements are not visible
    """
    app = provide_app
    user_id_for_test = 1

    login_user_to_home_page(app, browser, user_id_for_test)
    open_utub_search_box(browser)
    wait_then_click_element(browser, HPL.UTUB_CLOSE_SEARCH_ICON, time=3)

    wait_until_hidden(browser, HPL.UTUB_CLOSE_SEARCH_ICON, timeout=3)
    wait_until_hidden(browser, HPL.UTUB_SEARCH_INPUT, timeout=3)
    wait_until_visible_css_selector(browser, HPL.UTUB_OPEN_SEARCH_ICON, timeout=3)

    assert_visible_css_selector(browser, HPL.UTUB_OPEN_SEARCH_ICON)
    assert_not_visible_css_selector(browser, HPL.UTUB_CLOSE_SEARCH_ICON)
    assert_not_visible_css_selector(browser, HPL.UTUB_SEARCH_INPUT)


def test_utub_search_with_no_match(
    browser: WebDriver, create_test_users, provide_app: Flask
):
    """
    GIVEN a fresh load of the U4i Home page, where user is in multiple UTubs, and user has UTub search open
    WHEN user performs search that matches no UTubs
    THEN ensure that all UTub selectors are not visible
    """
    app = provide_app
    user_id_for_test = 1

    utub_names_and_ids = create_test_searchable_utubs(app, user_id_for_test)
    login_user_to_home_page(app, browser, user_id_for_test)
    open_utub_search_box(browser)

    input_elem = wait_then_get_element(browser, HPL.UTUB_SEARCH_INPUT)
    assert input_elem is not None

    input_elem.send_keys("Z")
    input_elem = wait_then_get_element(browser, HPL.UTUB_SEARCH_INPUT)
    assert input_elem is not None
    assert input_elem.get_attribute("value") == "Z"

    for utub_id in utub_names_and_ids.values():
        utub_selector = f"{HPL.SELECTORS_UTUB}[utubid='{utub_id}']"
        assert_not_visible_css_selector(browser, utub_selector, time=3)


def test_utub_search_with_one_match(
    browser: WebDriver, create_test_users, provide_app: Flask
):
    """
    GIVEN a fresh load of the U4i Home page, where user is in multiple UTubs, and user has UTub search open
    WHEN user performs search that matches one UTub
    THEN ensure that only one UTub selector is visible
    """
    app = provide_app
    user_id_for_test = 1

    utub_names_and_ids = create_test_searchable_utubs(app, user_id_for_test)
    login_user_to_home_page(app, browser, user_id_for_test)
    open_utub_search_box(browser)

    original_names_and_ids = utub_names_and_ids.copy()

    input_elem = wait_then_get_element(browser, HPL.UTUB_SEARCH_INPUT)
    assert input_elem is not None

    utub_name_to_show, utub_id_to_show = utub_names_and_ids.popitem()

    input_elem.send_keys(utub_name_to_show)
    input_elem = wait_then_get_element(browser, HPL.UTUB_SEARCH_INPUT)
    assert input_elem is not None
    assert input_elem.get_attribute("value") == utub_name_to_show

    for utub_id in original_names_and_ids.values():
        utub_selector = f"{HPL.SELECTORS_UTUB}[utubid='{utub_id}']"
        if utub_id == utub_id_to_show:
            assert_visible_css_selector(browser, utub_selector, time=3)
        else:
            assert_not_visible_css_selector(browser, utub_selector, time=3)


def test_utub_search_with_all_match(
    browser: WebDriver, create_test_users, provide_app: Flask
):
    """
    GIVEN a fresh load of the U4i Home page, where user is in multiple UTubs, and user has UTub search open
    WHEN user performs search that matches all UTub
    THEN ensure that all UTub selectors are visible
    """
    app = provide_app
    user_id_for_test = 1

    utub_names_and_ids = create_test_searchable_utubs(app, user_id_for_test)
    login_user_to_home_page(app, browser, user_id_for_test)
    open_utub_search_box(browser)

    input_elem = wait_then_get_element(browser, HPL.UTUB_SEARCH_INPUT)
    assert input_elem is not None

    input_elem.send_keys("1")
    input_elem = wait_then_get_element(browser, HPL.UTUB_SEARCH_INPUT)
    assert input_elem is not None
    assert input_elem.get_attribute("value") == "1"

    for utub_id in utub_names_and_ids.values():
        utub_selector = f"{HPL.SELECTORS_UTUB}[utubid='{utub_id}']"
        assert_visible_css_selector(browser, utub_selector, time=3)


def test_utub_search_resets_selectors_when_closed(
    browser: WebDriver, create_test_users, provide_app: Flask
):
    """
    GIVEN a fresh load of the U4i Home page, where user is in multiple UTubs, and user has UTub search open
    WHEN user performs search that matches no UTubs, but then closes the search
    THEN ensure that all UTub selectors are again visible
    """
    app = provide_app
    user_id_for_test = 1

    utub_names_and_ids = create_test_searchable_utubs(app, user_id_for_test)
    login_user_to_home_page(app, browser, user_id_for_test)
    open_utub_search_box(browser)

    input_elem = wait_then_get_element(browser, HPL.UTUB_SEARCH_INPUT)
    assert input_elem is not None

    input_elem.send_keys("Z")
    input_elem = wait_then_get_element(browser, HPL.UTUB_SEARCH_INPUT)
    assert input_elem is not None
    assert input_elem.get_attribute("value") == "Z"

    for utub_id in utub_names_and_ids.values():
        utub_selector = f"{HPL.SELECTORS_UTUB}[utubid='{utub_id}']"
        assert_not_visible_css_selector(browser, utub_selector, time=3)

    wait_then_click_element(browser, HPL.UTUB_CLOSE_SEARCH_ICON, time=3)
    assert_not_visible_css_selector(browser, HPL.UTUB_CLOSE_SEARCH_ICON, time=3)

    for utub_id in utub_names_and_ids.values():
        utub_selector = f"{HPL.SELECTORS_UTUB}[utubid='{utub_id}']"
        assert_visible_css_selector(browser, utub_selector, time=3)


def test_utub_search_resets_on_create_utub(
    browser: WebDriver, create_test_users, provide_app: Flask
):
    """
    GIVEN a fresh load of the U4i Home page, where user is in multiple UTubs, and user has UTub search open
    WHEN user searches and then creates a new UTub
    THEN ensure that all UTub selectors are again visible and filter reset when the new UTub is made
    """
    app = provide_app
    user_id_for_test = 1
    utub_names_and_ids = create_test_searchable_utubs(app, user_id_for_test)
    login_user_to_home_page(app, browser, user_id_for_test)
    open_utub_search_box(browser)

    input_elem = wait_then_get_element(browser, HPL.UTUB_SEARCH_INPUT)
    assert input_elem is not None

    # All UTubs missing 'Z'
    input_elem.send_keys("Z")
    input_elem = wait_then_get_element(browser, HPL.UTUB_SEARCH_INPUT)
    assert input_elem is not None
    assert input_elem.get_attribute("value") == "Z"

    for utub_id in utub_names_and_ids.values():
        utub_selector = f"{HPL.SELECTORS_UTUB}[utubid='{utub_id}']"
        assert_not_visible_css_selector(browser, utub_selector, time=3)

    create_utub(browser, utub_name="ABC", utub_description="")

    # Submits new UTub
    wait_then_click_element(browser, HPL.BUTTON_UTUB_SUBMIT_CREATE)

    # Wait for POST request
    create_utub_name_input = wait_until_hidden(
        browser, HPL.INPUT_UTUB_NAME_CREATE, timeout=3
    )

    assert not create_utub_name_input.is_displayed()
    assert_active_utub(browser, "ABC")

    for utub_id in utub_names_and_ids.values():
        utub_selector = f"{HPL.SELECTORS_UTUB}[utubid='{utub_id}']"
        assert_visible_css_selector(browser, utub_selector, time=3)


def test_utub_search_resets_on_delete_utub(
    browser: WebDriver, create_test_users, provide_app: Flask
):
    """
    GIVEN a fresh load of the U4i Home page, where user is in multiple UTubs, and user has UTub search open
    WHEN user searches and then deletes the current UTub
    THEN ensure that all UTub selectors are again visible and filter reset when the new UTub is made
    """
    app = provide_app
    user_id_for_test = 1
    utub_names_and_ids = create_test_searchable_utubs(app, user_id_for_test)
    first_id = list(utub_names_and_ids.values())[0]
    login_user_and_select_utub_by_utubid(
        app, browser, utub_id=first_id, user_id=user_id_for_test
    )
    open_utub_search_box(browser)

    input_elem = wait_then_get_element(browser, HPL.UTUB_SEARCH_INPUT)
    assert input_elem is not None

    # All UTubs missing 'Z'
    input_elem.send_keys("Z")
    input_elem = wait_then_get_element(browser, HPL.UTUB_SEARCH_INPUT)
    assert input_elem is not None
    assert input_elem.get_attribute("value") == "Z"

    for utub_id in utub_names_and_ids.values():
        utub_selector = f"{HPL.SELECTORS_UTUB}[utubid='{utub_id}']"
        assert_not_visible_css_selector(browser, utub_selector, time=3)

    css_selector = f'{HPL.SELECTORS_UTUB}[utubid="{first_id}"]'
    assert browser.find_element(By.CSS_SELECTOR, css_selector)
    wait_then_click_element(browser, HPL.BUTTON_UTUB_DELETE, time=3)

    wait_then_click_element(browser, HPL.BUTTON_MODAL_SUBMIT, time=3)

    # Wait for DELETE request
    wait_until_hidden(browser, HPL.BUTTON_MODAL_SUBMIT, timeout=3)
    utub_selector = browser.find_element(By.CSS_SELECTOR, css_selector)

    wait_for_element_to_be_removed(browser, utub_selector, timeout=10)

    for utub_id in utub_names_and_ids.values():
        if utub_id == first_id:
            continue
        utub_selector = f"{HPL.SELECTORS_UTUB}[utubid='{utub_id}']"
        assert_visible_css_selector(browser, utub_selector, time=3)
