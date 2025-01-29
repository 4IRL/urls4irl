from flask import Flask
import pytest
from selenium.common.exceptions import ElementNotInteractableException
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver

from locators import HomePageLocators as HPL
from src.cli.mock_constants import MOCK_UTUB_NAME_BASE
from src.models.users import Users
from src.models.utubs import Utubs
from src.utils.constants import CONSTANTS
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from src.utils.strings.utub_strs import UTUB_FAILURE
from tests.functional.utils_for_test import (
    assert_login_with_username,
    assert_not_visible_css_selector,
    assert_visited_403_on_invalid_csrf_and_reload,
    create_user_session_and_provide_session_id,
    get_all_url_ids_in_selected_utub,
    get_all_utub_selector_names,
    get_selected_utub_name,
    invalidate_csrf_token_on_page,
    login_user_and_select_utub_by_name,
    login_user_and_select_utub_by_utubid,
    login_user_with_cookie_from_session,
    select_utub_by_name,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_hidden,
    wait_until_update_btn_has_hidden_class,
    wait_until_utub_name_appears,
)
from tests.functional.utubs_ui.utils_for_test_utub_ui import (
    assert_active_utub,
    get_utub_this_user_created,
    open_update_utub_name_input,
    update_utub_name,
)

pytestmark = pytest.mark.utubs_ui


def test_select_utub(browser: WebDriver, create_test_urls, provide_app: Flask):
    """
    Tests a user's ability to select a specific UTub and observe the changes in display.

    GIVEN a fresh load of the U4I Home page
    WHEN user selects a UTub, then selects another UTub
    THEN ensure the URL deck header changes and TODO: displayed URLs change
    """
    app = provide_app
    user_id = 1
    session_id = create_user_session_and_provide_session_id(app, user_id)
    login_user_with_cookie_from_session(browser, session_id)

    utub_selector_names = get_all_utub_selector_names(browser)
    current_utub_name = utub_selector_names[0]

    select_utub_by_name(browser, current_utub_name)
    assert_active_utub(browser, current_utub_name)
    current_utub_url_ids = get_all_url_ids_in_selected_utub(browser)

    next_utub_name = utub_selector_names[1]

    select_utub_by_name(browser, next_utub_name)
    assert_active_utub(browser, next_utub_name)
    next_utub_url_ids = get_all_url_ids_in_selected_utub(browser)

    assert not any([url_id in next_utub_url_ids for url_id in current_utub_url_ids])


def test_open_update_utub_name_input_creator(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    Tests a user's ability to open the updateUTubName input using the pencil button.

    GIVEN a fresh load of the U4I Home page
    WHEN user selects a UTub they created, then clicks the edit UTub name button
    THEN ensure the updateUTubName input opens
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)

    utub_name_elem = wait_then_get_element(browser, HPL.HEADER_URL_DECK)
    assert utub_name_elem is not None
    utub_name = utub_name_elem.text

    open_update_utub_name_input(browser)

    utub_name_update_input = wait_then_get_element(browser, HPL.INPUT_UTUB_NAME_UPDATE)
    assert utub_name_update_input is not None

    assert utub_name_update_input.is_displayed()

    assert utub_name == utub_name_update_input.get_attribute("value")


def test_open_update_utub_name_input_member(
    browser: WebDriver, create_test_utubmembers, provide_app: Flask
):
    """
    Tests a user's ability to open the updateUTubName input using the pencil button.

    GIVEN a fresh load of the U4I Home page
    WHEN user selects a UTub they created, then clicks the edit UTub name button
    THEN ensure the updateUTubName input does not open
    """
    app = provide_app
    user_id = 1
    with app.app_context():
        utub: Utubs = Utubs.query.filter(Utubs.utub_creator != user_id).first()

    login_user_and_select_utub_by_utubid(app, browser, user_id, utub.id)
    wait_until_utub_name_appears(browser, utub.name)
    wait_until_update_btn_has_hidden_class(browser, HPL.BUTTON_UTUB_NAME_UPDATE)

    # ElementNotInteractableException is raised when selenium tries to hover over the UTub Name,
    # and then click on the edit UTub name button - but as a member, the button doesn't
    # show on hover
    with pytest.raises(ElementNotInteractableException):
        open_update_utub_name_input(browser)

    assert_not_visible_css_selector(browser, HPL.BUTTON_UTUB_NAME_UPDATE)


def test_close_update_utub_name_input_btn(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    Tests a user's ability to close the createUTub input by clicking the 'x' button

    GIVEN a fresh load of the U4I Home page
    WHEN user opens the createUTub input, then clicks the 'x'
    THEN ensure the createUTub input is closed
    """

    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)

    open_update_utub_name_input(browser)

    wait_then_click_element(browser, HPL.BUTTON_UTUB_NAME_CANCEL_UPDATE)

    update_utub_name_input = wait_until_hidden(browser, HPL.INPUT_UTUB_NAME_UPDATE, 5)

    assert not update_utub_name_input.is_displayed()


def test_close_update_utub_name_input_key(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    Tests a user's ability to close the createUTub input by pressing the Escape key

    GIVEN a fresh load of the U4I Home page
    WHEN user opens the createUTub input, then presses 'Esc'
    THEN ensure the createUTub input is closed
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)

    open_update_utub_name_input(browser)

    browser.switch_to.active_element.send_keys(Keys.ESCAPE)

    update_utub_name_input = wait_until_hidden(browser, HPL.INPUT_UTUB_NAME_UPDATE, 5)

    assert not update_utub_name_input.is_displayed()


def test_update_utub_name_btn(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    Tests a UTub owner's ability to update a selected UTub's name.

    GIVEN a user owns a UTub
    WHEN they submit the editUTub form
    THEN ensure the form is hidden, the UTub selector name and URL deck header are updated.
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)

    new_utub_name = MOCK_UTUB_NAME_BASE + "2"

    update_utub_name(browser, new_utub_name)

    # Submits new UTub name
    wait_then_click_element(browser, HPL.BUTTON_UTUB_NAME_SUBMIT_UPDATE)

    # Wait for POST request
    wait_until_hidden(browser, HPL.BUTTON_UTUB_NAME_SUBMIT_UPDATE)

    url_deck_header = get_selected_utub_name(browser)

    # Assert new UTub name is updated in URL Deck
    assert new_utub_name == url_deck_header

    utub_selector_names = get_all_utub_selector_names(browser)

    # Assert new UTub name is updated in UTub Deck
    assert new_utub_name in utub_selector_names


def test_update_utub_name_key(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    Tests a UTub owner's ability to update a selected UTub's name.

    GIVEN a user owns a UTub
    WHEN they submit the editUTub form
    THEN ensure the form is hidden, the UTub selector name and URL deck header are updated.
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)

    new_utub_name = MOCK_UTUB_NAME_BASE + "2"

    update_utub_name(browser, new_utub_name)

    # Submits new UTub name
    browser.switch_to.active_element.send_keys(Keys.ENTER)

    # Wait for POST request
    wait_until_hidden(browser, HPL.BUTTON_UTUB_NAME_SUBMIT_UPDATE)

    url_deck_header = get_selected_utub_name(browser)

    # Assert new UTub name is updated in URL Deck
    assert new_utub_name == url_deck_header

    utub_selector_names = get_all_utub_selector_names(browser)

    # Assert new UTub name is updated in UTub Deck
    assert new_utub_name in utub_selector_names


def test_update_utub_name_length_exceeded(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    Tests a UTub owner's ability to update a selected UTub's name.

    GIVEN a user owns a UTub
    WHEN they attempt to enter a UTub name that is too long
    THEN ensure the input field retains the max number of characters allowed.
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)

    new_utub_name = "a" * (CONSTANTS.UTUBS.MAX_NAME_LENGTH + 1)

    update_utub_name(browser, new_utub_name)

    update_utub_name_input = wait_then_get_element(browser, HPL.INPUT_UTUB_NAME_UPDATE)
    assert update_utub_name_input is not None
    new_utub_name = update_utub_name_input.get_attribute("value")
    assert new_utub_name is not None

    assert len(new_utub_name) == CONSTANTS.UTUBS.MAX_NAME_LENGTH


def test_update_utub_name_empty_field(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    Tests a UTub owner's ability to update a selected UTub's name.

    GIVEN a user owns a UTub
    WHEN they attempt to enter an empty UTub name to update
    THEN ensure the proper error response is shown.
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)

    update_utub_name(browser, utub_name="")

    # Submits new UTub name
    wait_then_click_element(browser, HPL.BUTTON_UTUB_NAME_SUBMIT_UPDATE)

    # Wait for POST request
    invalid_utub_name_field = wait_then_get_element(
        browser, HPL.INPUT_UTUB_NAME_UPDATE + HPL.INVALID_FIELD_SUFFIX
    )
    assert invalid_utub_name_field is not None
    assert invalid_utub_name_field.text == UTUB_FAILURE.FIELD_REQUIRED_STR


def test_update_utub_name_sanitized(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    Tests a UTub owner's ability to update a selected UTub's name.

    GIVEN a user owns a UTub
    WHEN they attempt to enter an UTub name that is sanitized by the backend
    THEN ensure the proper error response is shown.
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)

    update_utub_name(browser, utub_name='<img src="evl.jpg">')

    # Submits new UTub name
    wait_then_click_element(browser, HPL.BUTTON_UTUB_NAME_SUBMIT_UPDATE)

    # Wait for POST request
    invalid_utub_name_field = wait_then_get_element(
        browser, HPL.INPUT_UTUB_NAME_UPDATE + HPL.INVALID_FIELD_SUFFIX
    )
    assert invalid_utub_name_field is not None
    assert invalid_utub_name_field.text == UTUB_FAILURE.INVALID_INPUT


def test_update_utub_name_similar(
    browser: WebDriver,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    Tests a UTub owner's ability to update a selected UTub's name to a name similar to another UTub in their collection.

    GIVEN a user owns a UTub
    WHEN user submits the editUTub form
    THEN ensure a modal is presented.
    WHEN user submits
    THEN the form is hidden, the UTub selector name and URL deck header are updated.
    """

    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)

    utub_selector_names = get_all_utub_selector_names(browser)

    new_utub_name = utub_selector_names[1]

    update_utub_name(browser, new_utub_name)

    # Submits new UTub name
    wait_then_click_element(browser, HPL.BUTTON_UTUB_NAME_SUBMIT_UPDATE)

    warning_modal_body = wait_then_get_element(browser, HPL.BODY_MODAL, time=5)
    assert warning_modal_body is not None
    confirmation_modal_body_text = warning_modal_body.get_attribute("innerText")

    utub_name_update_check_text = UTS.BODY_MODAL_UTUB_UPDATE_SAME_NAME

    # Assert warning modal appears with appropriate text
    assert confirmation_modal_body_text == utub_name_update_check_text

    wait_then_click_element(browser, HPL.BUTTON_MODAL_SUBMIT)

    # Wait for POST request
    wait_until_hidden(browser, HPL.BODY_MODAL, timeout=5)

    url_deck_header = get_selected_utub_name(browser)

    # Assert new UTub name is updated in URL Deck
    assert new_utub_name == url_deck_header

    # Assert new UTub name is updated in UTub Deck
    assert new_utub_name in utub_selector_names


def test_update_utub_name_invalid_csrf_token(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    Tests a UTub owner's ability to attempt to update a selected UTub's name with an invalid CSRF token

    GIVEN a user owns a UTub
    WHEN they submit the editUTub form with an invalid CSRF token
    THEN ensure U4I responds with a proper error message
    """
    app = provide_app
    user_id = 1
    with app.app_context():
        user: Users = Users.query.get(user_id)
        username = user.username
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)

    new_utub_name = MOCK_UTUB_NAME_BASE + "2"

    update_utub_name(browser, new_utub_name)

    invalidate_csrf_token_on_page(browser)

    # Submits new UTub name
    wait_then_click_element(browser, HPL.BUTTON_UTUB_NAME_SUBMIT_UPDATE)

    assert_visited_403_on_invalid_csrf_and_reload(browser)

    # Page reloads after user clicks button in CSRF 403 error page
    update_utub_name_input = wait_until_hidden(
        browser, HPL.INPUT_UTUB_NAME_UPDATE, timeout=3
    )
    assert not update_utub_name_input.is_displayed()
    assert_login_with_username(browser, username)
