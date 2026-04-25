from flask import Flask
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

from backend import db
from backend.models.utub_members import Utub_Members
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from backend.utils.strings.utub_strs import UTUB_CREATE_MSG
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
    clear_then_send_keys,
    wait_for_selector_to_be_removed,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_hidden,
    wait_until_visible_css_selector,
)
from tests.functional.utubs_ui.selenium_utils import create_utub

pytestmark = pytest.mark.utubs_ui


def test_utub_search_with_no_match(
    browser: WebDriver, create_test_users, provide_app: Flask
):
    """
    GIVEN a fresh load of the U4i Home page, where user is in multiple UTubs
    WHEN user performs a search that matches no UTubs
    THEN ensure that all UTub selectors are hidden and the no-results message is shown
    """
    app = provide_app
    user_id_for_test = 1

    utub_names_and_ids = create_test_searchable_utubs(app, user_id_for_test)
    login_user_to_home_page(app, browser, user_id_for_test)

    input_elem = wait_then_get_element(browser, HPL.UTUB_SEARCH_INPUT)
    assert input_elem is not None

    input_elem.send_keys("Z")
    input_elem = wait_then_get_element(browser, HPL.UTUB_SEARCH_INPUT)
    assert input_elem is not None
    assert input_elem.get_attribute("value") == "Z"

    for utub_id in utub_names_and_ids.values():
        utub_selector = f"{HPL.SELECTORS_UTUB}[utubid='{utub_id}']"
        assert_not_visible_css_selector(browser, utub_selector, time=3)

    assert_visible_css_selector(browser, HPL.UTUB_SEARCH_NO_RESULTS, time=3)
    no_results_elem = browser.find_element(By.CSS_SELECTOR, HPL.UTUB_SEARCH_NO_RESULTS)
    assert no_results_elem.text == UTS.UTUB_SEARCH_NO_UTUBS


def test_utub_search_with_one_match(
    browser: WebDriver, create_test_users, provide_app: Flask
):
    """
    GIVEN a fresh load of the U4i Home page, where user is in multiple UTubs
    WHEN user performs a search that matches one UTub
    THEN ensure that only one UTub selector is visible
    """
    app = provide_app
    user_id_for_test = 1

    utub_names_and_ids = create_test_searchable_utubs(app, user_id_for_test)
    login_user_to_home_page(app, browser, user_id_for_test)

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
    GIVEN a fresh load of the U4i Home page, where user is in multiple UTubs
    WHEN user performs a search that matches all UTubs
    THEN ensure that all UTub selectors are visible
    """
    app = provide_app
    user_id_for_test = 1

    utub_names_and_ids = create_test_searchable_utubs(app, user_id_for_test)
    login_user_to_home_page(app, browser, user_id_for_test)

    input_elem = wait_then_get_element(browser, HPL.UTUB_SEARCH_INPUT)
    assert input_elem is not None

    input_elem.send_keys("1")
    input_elem = wait_then_get_element(browser, HPL.UTUB_SEARCH_INPUT)
    assert input_elem is not None
    assert input_elem.get_attribute("value") == "1"

    for utub_id in utub_names_and_ids.values():
        utub_selector = f"{HPL.SELECTORS_UTUB}[utubid='{utub_id}']"
        assert_visible_css_selector(browser, utub_selector, time=3)


def test_utub_search_resets_on_create_utub(
    browser: WebDriver, create_test_users, provide_app: Flask
):
    """
    GIVEN a fresh load of the U4i Home page, where user is in multiple UTubs
    WHEN user searches and then creates a new UTub
    THEN ensure that all UTub selectors are visible and filter is reset when the new UTub is made
    """
    app = provide_app
    user_id_for_test = 1
    utub_names_and_ids = create_test_searchable_utubs(app, user_id_for_test)
    login_user_to_home_page(app, browser, user_id_for_test)

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
    GIVEN a fresh load of the U4i Home page, where user is in multiple UTubs
    WHEN user searches and then deletes the current UTub
    THEN ensure that all remaining UTub selectors are visible and filter is reset
    """
    app = provide_app
    user_id_for_test = 1
    utub_names_and_ids = create_test_searchable_utubs(app, user_id_for_test)
    first_id = list(utub_names_and_ids.values())[0]
    login_user_and_select_utub_by_utubid(
        app, browser, utub_id=first_id, user_id=user_id_for_test
    )

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

    deleted_utub_selector = f'{HPL.SELECTORS_UTUB}[utubid="{first_id}"]'
    wait_then_click_element(browser, HPL.BUTTON_UTUB_DELETE, time=3)

    wait_then_click_element(browser, HPL.BUTTON_MODAL_SUBMIT, time=3)

    # Wait for DELETE request
    wait_until_hidden(browser, HPL.HOME_MODAL)

    wait_for_selector_to_be_removed(browser, deleted_utub_selector, timeout=10)

    for utub_id in utub_names_and_ids.values():
        if utub_id == first_id:
            continue
        utub_selector = f"{HPL.SELECTORS_UTUB}[utubid='{utub_id}']"
        assert_visible_css_selector(browser, utub_selector, time=3)


def test_search_bar_visible_when_utubs_exist(
    browser: WebDriver, create_test_users, provide_app: Flask
):
    """
    GIVEN a user with one or more UTubs logs in
    WHEN they navigate to the home page
    THEN the search bar (#SearchUTubWrap, #UTubNameSearch) is visible and the
         "Create a UTub" subheader is hidden.
    """
    app = provide_app
    user_id_for_test = 1
    create_test_searchable_utubs(app, user_id_for_test)
    login_user_to_home_page(app, browser, user_id_for_test)

    assert_visible_css_selector(browser, HPL.UTUB_SEARCH_WRAP, time=3)
    assert_visible_css_selector(browser, HPL.UTUB_SEARCH_INPUT, time=3)
    assert_not_visible_css_selector(browser, HPL.SUBHEADER_UTUB_DECK, time=3)


def test_search_bar_hidden_when_no_utubs(
    browser: WebDriver, create_test_users, provide_app: Flask
):
    """
    GIVEN a user with zero UTubs logs in
    WHEN they navigate to the home page
    THEN the search bar (#SearchUTubWrap) is hidden, and the
         "Create a UTub" subheader is visible.
    """
    app = provide_app
    user_id_for_test = 1
    login_user_to_home_page(app, browser, user_id_for_test)

    assert_not_visible_css_selector(browser, HPL.UTUB_SEARCH_WRAP, time=3)
    assert_visible_css_selector(browser, HPL.SUBHEADER_UTUB_DECK, time=3)
    subheader_elem = browser.find_element(By.CSS_SELECTOR, HPL.SUBHEADER_UTUB_DECK)
    assert subheader_elem.text == UTUB_CREATE_MSG


def test_search_bar_appears_after_creating_first_utub(
    browser: WebDriver, create_test_users, provide_app: Flask
):
    """
    GIVEN a user with zero UTubs is on the home page (search bar hidden)
    WHEN they create their first UTub via the UI
    THEN the search bar becomes visible and the "Create a UTub" subheader is hidden.
    """
    app = provide_app
    user_id_for_test = 1
    login_user_to_home_page(app, browser, user_id_for_test)

    assert_not_visible_css_selector(browser, HPL.UTUB_SEARCH_WRAP, time=3)

    utub_name = UTS.TEST_UTUB_NAME_1
    create_utub(browser, utub_name=utub_name, utub_description="")
    wait_then_click_element(browser, HPL.BUTTON_UTUB_SUBMIT_CREATE)

    create_utub_name_input = wait_until_hidden(
        browser, HPL.INPUT_UTUB_NAME_CREATE, timeout=3
    )
    assert not create_utub_name_input.is_displayed()
    assert_active_utub(browser, utub_name)

    assert_visible_css_selector(browser, HPL.UTUB_SEARCH_WRAP, time=3)
    assert_visible_css_selector(browser, HPL.UTUB_SEARCH_INPUT, time=3)
    assert_not_visible_css_selector(browser, HPL.SUBHEADER_UTUB_DECK, time=3)


def test_search_bar_disappears_after_deleting_last_utub(
    browser: WebDriver, create_test_users, provide_app: Flask
):
    """
    GIVEN a user with exactly one UTub (search bar visible)
    WHEN they delete that last UTub
    THEN the search bar becomes hidden and the "Create a UTub" subheader is shown.
    """
    app = provide_app
    user_id_for_test = 1
    utub_names_and_ids = create_test_searchable_utubs(app, user_id_for_test)
    # Leave only one UTub in the user's membership list by removing the others.
    utub_ids = list(utub_names_and_ids.values())
    keep_id = utub_ids[0]
    with app.app_context():
        Utub_Members.query.filter(
            Utub_Members.user_id == user_id_for_test,
            Utub_Members.utub_id != keep_id,
        ).delete()
        db.session.commit()

    login_user_and_select_utub_by_utubid(
        app, browser, utub_id=keep_id, user_id=user_id_for_test
    )

    assert_visible_css_selector(browser, HPL.UTUB_SEARCH_WRAP, time=3)

    deleted_utub_selector = f'{HPL.SELECTORS_UTUB}[utubid="{keep_id}"]'
    wait_then_click_element(browser, HPL.BUTTON_UTUB_DELETE, time=3)
    wait_then_click_element(browser, HPL.BUTTON_MODAL_SUBMIT, time=3)
    wait_until_hidden(browser, HPL.HOME_MODAL)
    wait_for_selector_to_be_removed(browser, deleted_utub_selector, timeout=10)

    assert_not_visible_css_selector(browser, HPL.UTUB_SEARCH_WRAP, time=3)
    assert_visible_css_selector(browser, HPL.SUBHEADER_UTUB_DECK, time=3)
    subheader_elem = browser.find_element(By.CSS_SELECTOR, HPL.SUBHEADER_UTUB_DECK)
    assert subheader_elem.text == UTUB_CREATE_MSG


def test_no_results_message_shown_when_search_matches_nothing(
    browser: WebDriver, create_test_users, provide_app: Flask
):
    """
    GIVEN a user with multiple UTubs is on the home page
    WHEN they search for a non-existent UTub name
    THEN the no-results message (#UTubSearchNoResults) becomes visible with the
         expected text from UTS.UTUB_SEARCH_NO_UTUBS.
    """
    app = provide_app
    user_id_for_test = 1
    create_test_searchable_utubs(app, user_id_for_test)
    login_user_to_home_page(app, browser, user_id_for_test)

    input_elem = wait_then_get_element(browser, HPL.UTUB_SEARCH_INPUT)
    assert input_elem is not None
    input_elem.send_keys("ZZZZZZ")

    assert_visible_css_selector(browser, HPL.UTUB_SEARCH_NO_RESULTS, time=3)
    no_results_elem = browser.find_element(By.CSS_SELECTOR, HPL.UTUB_SEARCH_NO_RESULTS)
    assert no_results_elem.text == UTS.UTUB_SEARCH_NO_UTUBS


def test_no_results_message_hidden_when_search_has_matches(
    browser: WebDriver, create_test_users, provide_app: Flask
):
    """
    GIVEN a user with multiple UTubs whose initial search shows no results
    WHEN they clear the search and type a matching term
    THEN the no-results message becomes hidden.
    """
    app = provide_app
    user_id_for_test = 1
    create_test_searchable_utubs(app, user_id_for_test)
    login_user_to_home_page(app, browser, user_id_for_test)

    input_elem = wait_then_get_element(browser, HPL.UTUB_SEARCH_INPUT)
    assert input_elem is not None

    input_elem.send_keys("ZZZZZZ")
    assert_visible_css_selector(browser, HPL.UTUB_SEARCH_NO_RESULTS, time=3)

    clear_then_send_keys(input_elem, "1")
    wait_until_visible_css_selector(browser, HPL.SELECTORS_UTUB, timeout=3)
    assert_not_visible_css_selector(browser, HPL.UTUB_SEARCH_NO_RESULTS, time=3)
