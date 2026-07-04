from flask import Flask
import pytest
from playwright.sync_api import Page

from backend import db
from backend.models.utub_members import Utub_Members
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from backend.utils.strings.utub_strs import UTUB_CREATE_MSG
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_assert_utils import (
    assert_active_utub,
    assert_not_visible_css_selector,
    assert_visible_css_selector,
)
from tests.functional.db_utils import create_test_searchable_utubs
from tests.functional.playwright_login_utils import (
    login_user_and_select_utub_by_utubid,
)
from tests.functional.playwright_utils import (
    clear_then_send_keys,
    login_user_to_home_page,
    wait_for_selector_to_be_removed,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_hidden,
    wait_until_visible_css_selector,
)
from tests.functional.utubs_ui.playwright_utils import (
    create_utub,
    open_utub_name_filter,
)

pytestmark = pytest.mark.utubs_ui


def test_utub_search_with_no_match(page: Page, create_test_users, provide_app: Flask):
    """
    GIVEN a fresh load of the U4i Home page, where user is in multiple UTubs
    WHEN user performs a search that matches no UTubs
    THEN ensure that all UTub selectors are hidden and the no-results message is shown
    """
    app = provide_app
    user_id_for_test = 1

    utub_names_and_ids = create_test_searchable_utubs(app, user_id_for_test)
    login_user_to_home_page(app=app, page=page, user_id=user_id_for_test)

    input_elem = open_utub_name_filter(page=page)
    assert input_elem is not None

    input_elem.fill("Z")
    input_elem = wait_then_get_element(page=page, css_selector=HPL.UTUB_SEARCH_INPUT)
    assert input_elem is not None
    assert input_elem.input_value() == "Z"

    for utub_id in utub_names_and_ids.values():
        utub_selector = f"{HPL.SELECTORS_UTUB}[utubid='{utub_id}']"
        assert_not_visible_css_selector(page=page, css_selector=utub_selector)

    assert_visible_css_selector(page=page, css_selector=HPL.UTUB_SEARCH_NO_RESULTS)
    no_results_elem = page.locator(HPL.UTUB_SEARCH_NO_RESULTS)
    assert no_results_elem.inner_text() == UTS.UTUB_SEARCH_NO_UTUBS


def test_utub_search_with_one_match(page: Page, create_test_users, provide_app: Flask):
    """
    GIVEN a fresh load of the U4i Home page, where user is in multiple UTubs
    WHEN user performs a search that matches one UTub
    THEN ensure that only one UTub selector is visible
    """
    app = provide_app
    user_id_for_test = 1

    utub_names_and_ids = create_test_searchable_utubs(app, user_id_for_test)
    login_user_to_home_page(app=app, page=page, user_id=user_id_for_test)

    original_names_and_ids = utub_names_and_ids.copy()

    input_elem = open_utub_name_filter(page=page)
    assert input_elem is not None

    utub_name_to_show, utub_id_to_show = utub_names_and_ids.popitem()

    input_elem.fill(utub_name_to_show)
    input_elem = wait_then_get_element(page=page, css_selector=HPL.UTUB_SEARCH_INPUT)
    assert input_elem is not None
    assert input_elem.input_value() == utub_name_to_show

    for utub_id in original_names_and_ids.values():
        utub_selector = f"{HPL.SELECTORS_UTUB}[utubid='{utub_id}']"
        if utub_id == utub_id_to_show:
            assert_visible_css_selector(page=page, css_selector=utub_selector)
        else:
            assert_not_visible_css_selector(page=page, css_selector=utub_selector)


def test_utub_search_with_all_match(page: Page, create_test_users, provide_app: Flask):
    """
    GIVEN a fresh load of the U4i Home page, where user is in multiple UTubs
    WHEN user performs a search that matches all UTubs
    THEN ensure that all UTub selectors are visible
    """
    app = provide_app
    user_id_for_test = 1

    utub_names_and_ids = create_test_searchable_utubs(app, user_id_for_test)
    login_user_to_home_page(app=app, page=page, user_id=user_id_for_test)

    input_elem = open_utub_name_filter(page=page)
    assert input_elem is not None

    input_elem.fill("1")
    input_elem = wait_then_get_element(page=page, css_selector=HPL.UTUB_SEARCH_INPUT)
    assert input_elem is not None
    assert input_elem.input_value() == "1"

    for utub_id in utub_names_and_ids.values():
        utub_selector = f"{HPL.SELECTORS_UTUB}[utubid='{utub_id}']"
        assert_visible_css_selector(page=page, css_selector=utub_selector)


def test_utub_search_resets_on_create_utub(
    page: Page, create_test_users, provide_app: Flask
):
    """
    GIVEN a fresh load of the U4i Home page, where user is in multiple UTubs
    WHEN user searches and then creates a new UTub
    THEN ensure that all UTub selectors are visible and filter is reset when the new UTub is made
    """
    app = provide_app
    user_id_for_test = 1
    utub_names_and_ids = create_test_searchable_utubs(app, user_id_for_test)
    login_user_to_home_page(app=app, page=page, user_id=user_id_for_test)

    input_elem = open_utub_name_filter(page=page)
    assert input_elem is not None

    # All UTubs missing 'Z'
    input_elem.fill("Z")
    input_elem = wait_then_get_element(page=page, css_selector=HPL.UTUB_SEARCH_INPUT)
    assert input_elem is not None
    assert input_elem.input_value() == "Z"

    for utub_id in utub_names_and_ids.values():
        utub_selector = f"{HPL.SELECTORS_UTUB}[utubid='{utub_id}']"
        assert_not_visible_css_selector(page=page, css_selector=utub_selector)

    create_utub(page=page, utub_name="ABC", utub_description="")

    # Submits new UTub
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_SUBMIT_CREATE)

    # Wait for POST request
    wait_until_hidden(page=page, css_selector=HPL.INPUT_UTUB_NAME_CREATE)

    assert_active_utub(page=page, utub_name="ABC")

    for utub_id in utub_names_and_ids.values():
        utub_selector = f"{HPL.SELECTORS_UTUB}[utubid='{utub_id}']"
        assert_visible_css_selector(page=page, css_selector=utub_selector)


def test_utub_search_resets_on_delete_utub(
    page: Page, create_test_users, provide_app: Flask
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
        app=app, page=page, utub_id=first_id, user_id=user_id_for_test
    )

    input_elem = open_utub_name_filter(page=page)
    assert input_elem is not None

    # All UTubs missing 'Z'
    input_elem.fill("Z")
    input_elem = wait_then_get_element(page=page, css_selector=HPL.UTUB_SEARCH_INPUT)
    assert input_elem is not None
    assert input_elem.input_value() == "Z"

    for utub_id in utub_names_and_ids.values():
        utub_selector = f"{HPL.SELECTORS_UTUB}[utubid='{utub_id}']"
        assert_not_visible_css_selector(page=page, css_selector=utub_selector)

    deleted_utub_selector = f'{HPL.SELECTORS_UTUB}[utubid="{first_id}"]'
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_DELETE)

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)

    # Wait for DELETE request
    wait_until_hidden(page=page, css_selector=HPL.HOME_MODAL)

    wait_for_selector_to_be_removed(page=page, css_selector=deleted_utub_selector)

    for utub_id in utub_names_and_ids.values():
        if utub_id == first_id:
            continue
        utub_selector = f"{HPL.SELECTORS_UTUB}[utubid='{utub_id}']"
        assert_visible_css_selector(page=page, css_selector=utub_selector)


def test_search_bar_visible_when_utubs_exist(
    page: Page, create_test_users, provide_app: Flask
):
    """
    GIVEN a user with one or more UTubs logs in
    WHEN they navigate to the home page (desktop)
    THEN the funnel toggle (#utubNameFilterBtn) is visible, the search input
         stays hidden until the funnel is opened, and the "Create a UTub"
         subheader is hidden. Opening the funnel reveals the search input.
    """
    app = provide_app
    user_id_for_test = 1
    create_test_searchable_utubs(app, user_id_for_test)
    login_user_to_home_page(app=app, page=page, user_id=user_id_for_test)

    # Desktop: the search hides behind the funnel toggle until opened.
    assert_visible_css_selector(page=page, css_selector=HPL.BUTTON_UTUB_NAME_FILTER)
    assert_not_visible_css_selector(page=page, css_selector=HPL.UTUB_SEARCH_WRAP)
    assert_not_visible_css_selector(page=page, css_selector=HPL.SUBHEADER_UTUB_DECK)

    # Opening the funnel reveals the search input.
    open_utub_name_filter(page=page)
    assert_visible_css_selector(page=page, css_selector=HPL.UTUB_SEARCH_WRAP)
    assert_visible_css_selector(page=page, css_selector=HPL.UTUB_SEARCH_INPUT)


def test_search_bar_hidden_when_no_utubs(
    page: Page, create_test_users, provide_app: Flask
):
    """
    GIVEN a user with zero UTubs logs in
    WHEN they navigate to the home page
    THEN the search bar (#SearchUTubWrap) is hidden, and the
         "Create a UTub" subheader is visible.
    """
    app = provide_app
    user_id_for_test = 1
    login_user_to_home_page(app=app, page=page, user_id=user_id_for_test)

    assert_not_visible_css_selector(page=page, css_selector=HPL.UTUB_SEARCH_WRAP)
    assert_visible_css_selector(page=page, css_selector=HPL.SUBHEADER_UTUB_DECK)
    subheader_elem = page.locator(HPL.SUBHEADER_UTUB_DECK)
    assert subheader_elem.inner_text() == UTUB_CREATE_MSG


def test_search_bar_appears_after_creating_first_utub(
    page: Page, create_test_users, provide_app: Flask
):
    """
    GIVEN a user with zero UTubs is on the home page (no funnel, no search bar)
    WHEN they create their first UTub via the UI
    THEN the funnel toggle appears, the "Create a UTub" subheader is hidden, and
         opening the funnel reveals the search input.
    """
    app = provide_app
    user_id_for_test = 1
    login_user_to_home_page(app=app, page=page, user_id=user_id_for_test)

    # Zero UTubs: neither the search nor its funnel toggle is shown.
    assert_not_visible_css_selector(page=page, css_selector=HPL.BUTTON_UTUB_NAME_FILTER)
    assert_not_visible_css_selector(page=page, css_selector=HPL.UTUB_SEARCH_WRAP)

    utub_name = UTS.TEST_UTUB_NAME_1
    create_utub(page=page, utub_name=utub_name, utub_description="")
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_SUBMIT_CREATE)

    wait_until_hidden(page=page, css_selector=HPL.INPUT_UTUB_NAME_CREATE)
    assert_active_utub(page=page, utub_name=utub_name)

    # First UTub created: the funnel toggle appears and reveals the search.
    assert_visible_css_selector(page=page, css_selector=HPL.BUTTON_UTUB_NAME_FILTER)
    assert_not_visible_css_selector(page=page, css_selector=HPL.SUBHEADER_UTUB_DECK)
    open_utub_name_filter(page=page)
    assert_visible_css_selector(page=page, css_selector=HPL.UTUB_SEARCH_WRAP)
    assert_visible_css_selector(page=page, css_selector=HPL.UTUB_SEARCH_INPUT)


def test_search_bar_disappears_after_deleting_last_utub(
    page: Page, create_test_users, provide_app: Flask
):
    """
    GIVEN a user with exactly one UTub (funnel toggle visible)
    WHEN they delete that last UTub
    THEN the funnel toggle and search bar become hidden and the "Create a UTub"
         subheader is shown.
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
        app=app, page=page, utub_id=keep_id, user_id=user_id_for_test
    )

    # One UTub: the funnel toggle is available (search hidden until opened).
    assert_visible_css_selector(page=page, css_selector=HPL.BUTTON_UTUB_NAME_FILTER)

    deleted_utub_selector = f'{HPL.SELECTORS_UTUB}[utubid="{keep_id}"]'
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_DELETE)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)
    wait_until_hidden(page=page, css_selector=HPL.HOME_MODAL)
    wait_for_selector_to_be_removed(page=page, css_selector=deleted_utub_selector)

    # Last UTub deleted: the funnel toggle and search disappear.
    assert_not_visible_css_selector(page=page, css_selector=HPL.BUTTON_UTUB_NAME_FILTER)
    assert_not_visible_css_selector(page=page, css_selector=HPL.UTUB_SEARCH_WRAP)
    assert_visible_css_selector(page=page, css_selector=HPL.SUBHEADER_UTUB_DECK)
    subheader_elem = page.locator(HPL.SUBHEADER_UTUB_DECK)
    assert subheader_elem.inner_text() == UTUB_CREATE_MSG


def test_no_results_message_shown_when_search_matches_nothing(
    page: Page, create_test_users, provide_app: Flask
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
    login_user_to_home_page(app=app, page=page, user_id=user_id_for_test)

    input_elem = open_utub_name_filter(page=page)
    assert input_elem is not None
    input_elem.fill("ZZZZZZ")

    assert_visible_css_selector(page=page, css_selector=HPL.UTUB_SEARCH_NO_RESULTS)
    no_results_elem = page.locator(HPL.UTUB_SEARCH_NO_RESULTS)
    assert no_results_elem.inner_text() == UTS.UTUB_SEARCH_NO_UTUBS


def test_no_results_message_hidden_when_search_has_matches(
    page: Page, create_test_users, provide_app: Flask
):
    """
    GIVEN a user with multiple UTubs whose initial search shows no results
    WHEN they clear the search and type a matching term
    THEN the no-results message becomes hidden.
    """
    app = provide_app
    user_id_for_test = 1
    create_test_searchable_utubs(app, user_id_for_test)
    login_user_to_home_page(app=app, page=page, user_id=user_id_for_test)

    input_elem = open_utub_name_filter(page=page)
    assert input_elem is not None

    input_elem.fill("ZZZZZZ")
    assert_visible_css_selector(page=page, css_selector=HPL.UTUB_SEARCH_NO_RESULTS)

    clear_then_send_keys(locator=input_elem, input_text="1")
    wait_until_visible_css_selector(page=page, css_selector=HPL.SELECTORS_UTUB)
    assert_not_visible_css_selector(page=page, css_selector=HPL.UTUB_SEARCH_NO_RESULTS)
