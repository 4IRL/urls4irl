from flask import Flask
import pytest
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver

from src.cli.mock_constants import MOCK_UTUB_DESCRIPTION
from src.models.users import Users
from src.utils.constants import CONSTANTS
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from src.utils.strings.utub_strs import UTUB_FAILURE
from tests.functional.utils_for_test import (
    assert_login_with_username,
    assert_visited_403_on_invalid_csrf_and_reload,
    invalidate_csrf_token_on_page,
    login_user_to_home_page,
    wait_then_click_element,
    wait_then_get_element,
    wait_then_get_elements,
    wait_until_hidden,
)
from tests.functional.locators import HomePageLocators as HPL
from utils_for_test_utub_ui import assert_active_utub, create_utub

pytestmark = pytest.mark.utubs_ui


def test_open_create_utub_input(
    browser: WebDriver, create_test_users, provide_app: Flask
):
    """
    Tests a user's ability to open the createUTub input using the plus button.

    GIVEN a fresh load of the U4I Home page
    WHEN user clicks the UTub module plus button
    THEN ensure the createUTub input opens
    """
    app = provide_app
    USER_ID = 1
    login_user_to_home_page(app, browser, USER_ID)

    # Click createUTub button to show input
    wait_then_click_element(browser, HPL.BUTTON_UTUB_CREATE)

    create_utub_name_input = wait_then_get_element(browser, HPL.INPUT_UTUB_NAME_CREATE)
    assert create_utub_name_input is not None
    assert create_utub_name_input.is_displayed()

    create_utub_desc_input = wait_then_get_element(
        browser, HPL.INPUT_UTUB_DESCRIPTION_CREATE
    )
    assert create_utub_desc_input is not None
    assert create_utub_desc_input.is_displayed()

    assert create_utub_name_input == browser.switch_to.active_element

    create_utub_submit_btn = wait_then_get_element(
        browser, HPL.BUTTON_UTUB_SUBMIT_CREATE
    )
    assert create_utub_submit_btn is not None
    assert create_utub_submit_btn.is_displayed()

    create_utub_cancel_btn = wait_then_get_element(
        browser, HPL.BUTTON_UTUB_CANCEL_CREATE
    )
    assert create_utub_cancel_btn is not None
    assert create_utub_submit_btn.is_displayed()


def test_close_create_utub_input_btn(
    browser: WebDriver, create_test_users, provide_app: Flask
):
    """
    Tests a user's ability to close the createUTub input by clicking the 'x' button

    GIVEN a fresh load of the U4I Home page
    WHEN user opens the createUTub input, then clicks the 'x'
    THEN ensure the createUTub input is closed
    """
    app = provide_app
    USER_ID = 1
    login_user_to_home_page(app, browser, USER_ID)

    # Click createUTub button to show input
    wait_then_click_element(browser, HPL.BUTTON_UTUB_CREATE)

    wait_then_click_element(browser, HPL.BUTTON_UTUB_CANCEL_CREATE)

    create_utub_name_input = wait_until_hidden(
        browser, HPL.INPUT_UTUB_NAME_CREATE, timeout=3
    )

    assert not create_utub_name_input.is_displayed()


def test_close_create_utub_input_key(
    browser: WebDriver, create_test_users, provide_app: Flask
):
    """
    Tests a user's ability to close the createUTub input by pressing the Escape key

    GIVEN a fresh load of the U4I Home page
    WHEN user opens the createUTub input, then presses 'Esc'
    THEN ensure the createUTub input is closed
    """
    app = provide_app
    USER_ID = 1
    login_user_to_home_page(app, browser, USER_ID)

    # Click createUTub button to show input
    wait_then_click_element(browser, HPL.BUTTON_UTUB_CREATE)

    browser.switch_to.active_element.send_keys(Keys.ESCAPE)

    create_utub_name_input = wait_until_hidden(
        browser, HPL.INPUT_UTUB_NAME_CREATE, timeout=3
    )

    assert not create_utub_name_input.is_displayed()


def test_create_utub_btn(browser: WebDriver, create_test_users, provide_app: Flask):
    """
    Tests a user's ability to create a UTub

    GIVEN a user attempting to make a UTub
    WHEN the createUTub form is populated and submitted by the 'check' button
    THEN ensure the new UTub is successfully added to the user's UTub Deck and is selected.
    """
    app = provide_app
    USER_ID = 1
    login_user_to_home_page(app, browser, USER_ID)

    utub_name = UTS.TEST_UTUB_NAME_1

    create_utub(browser, utub_name, MOCK_UTUB_DESCRIPTION)

    # Submits new UTub
    wait_then_click_element(browser, HPL.BUTTON_UTUB_SUBMIT_CREATE)

    # Wait for POST request
    create_utub_name_input = wait_until_hidden(
        browser, HPL.INPUT_UTUB_NAME_CREATE, timeout=3
    )

    assert not create_utub_name_input.is_displayed()
    assert_active_utub(browser, utub_name)
    utub_selector_for_creator_icon = f"{HPL.SELECTORS_UTUB} {HPL.CREATOR_ICON}"

    icon = wait_then_get_element(browser, utub_selector_for_creator_icon, time=3)
    assert icon is not None
    assert icon.is_displayed()


def test_create_utub_key(browser: WebDriver, create_test_users, provide_app: Flask):
    """
    Tests a user's ability to create a UTub

    GIVEN a user attempting to make a UTub
    WHEN the createUTub form is populated and submitted by pressing the 'Enter' key
    THEN ensure the new UTub is successfully added to the user's UTub Deck and is selected.
    """
    app = provide_app
    USER_ID = 1
    login_user_to_home_page(app, browser, USER_ID)

    utub_name = UTS.TEST_UTUB_NAME_1

    create_utub(browser, utub_name, MOCK_UTUB_DESCRIPTION)

    browser.switch_to.active_element.send_keys(Keys.ENTER)

    # Wait for POST request
    create_utub_name_input = wait_until_hidden(
        browser, HPL.INPUT_UTUB_NAME_CREATE, timeout=3
    )

    assert not create_utub_name_input.is_displayed()
    assert_active_utub(browser, utub_name)
    utub_selector_for_creator_icon = f"{HPL.SELECTORS_UTUB} {HPL.CREATOR_ICON}"

    icon = wait_then_get_element(browser, utub_selector_for_creator_icon, time=3)
    assert icon is not None
    assert icon.is_displayed()


def test_create_utub_name_length_exceeded(
    browser: WebDriver, create_test_users, provide_app: Flask
):
    """
    Tests the site error response to a user's attempt to create a new UTub with a name that exceeds the maximum character length limit.

    GIVEN a user attempting to make a UTub
    WHEN the createUTub form is populated and submitted with a name that exceeds character limits
    THEN ensure the appropriate error and prompt is shown to user.
    """

    app = provide_app
    USER_ID = 1
    login_user_to_home_page(app, browser, USER_ID)

    oversized_utub_name = "a" * CONSTANTS.UTUBS.MAX_NAME_LENGTH
    create_utub(
        browser, utub_name=oversized_utub_name, utub_description=oversized_utub_name
    )

    create_utub_name_input = wait_then_get_element(browser, HPL.INPUT_UTUB_NAME_CREATE)
    assert create_utub_name_input is not None
    current_input = create_utub_name_input.get_attribute("value")
    assert current_input is not None

    # HTML element has a maxlength on it, so check that the input is still the max length
    assert len(current_input) == CONSTANTS.UTUBS.MAX_NAME_LENGTH


def test_create_utub_name_similar(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    Tests the site warning response to a user's attempt to create a new UTub with a name that is similar to one already in their UTub Deck.

    GIVEN a user
    WHEN the createUTub form is populated and submitted with a name that is similar to one already in their UTub Deck
    THEN ensure the appropriate warning and prompt for confirmation is shown to user.
    """
    app = provide_app
    USER_ID = 1
    login_user_to_home_page(app, browser, USER_ID)

    # Extract name of a pre-existing UTub
    utub_selectors = wait_then_get_elements(browser, HPL.SELECTORS_UTUB)
    first_utub_selector = utub_selectors[0]
    utub_name = first_utub_selector.text

    # Attempt to add a new UTub with the same name
    create_utub(browser, utub_name, MOCK_UTUB_DESCRIPTION)
    # Submits new UTub
    wait_then_click_element(browser, HPL.BUTTON_UTUB_SUBMIT_CREATE)

    # Extract modal body element
    confirmation_modal_body = wait_then_get_element(browser, HPL.BODY_MODAL)
    assert confirmation_modal_body is not None
    confirmation_modal_body_text = confirmation_modal_body.get_attribute("innerText")
    utub_same_name_check_text = UTS.BODY_MODAL_UTUB_CREATE_SAME_NAME

    # Assert modal prompts user to consider duplicate UTub naming
    assert confirmation_modal_body_text == utub_same_name_check_text


def test_create_utub_empty_utub_name(
    browser: WebDriver, create_test_users, provide_app: Flask
):
    """
    Tests a user's ability to create a UTub

    GIVEN a user attempting to make a UTub
    WHEN the createUTub form is sent with the UTub Name field being empty
    THEN ensure U4I responds with a proper error message
    """
    app = provide_app
    USER_ID = 1
    login_user_to_home_page(app, browser, USER_ID)

    create_utub(browser, utub_name="", utub_description="")

    # Submits new UTub
    wait_then_click_element(browser, HPL.BUTTON_UTUB_SUBMIT_CREATE)

    # Wait for POST request to fail
    invalid_utub_name_error = wait_then_get_element(
        browser, HPL.INPUT_UTUB_NAME_CREATE + HPL.INVALID_FIELD_SUFFIX, time=3
    )
    assert invalid_utub_name_error is not None
    assert invalid_utub_name_error.text == UTUB_FAILURE.FIELD_REQUIRED_STR


def test_create_utub_sanitized_name(
    browser: WebDriver, create_test_users, provide_app: Flask
):
    """
    Tests a user's ability to create a UTub

    GIVEN a user attempting to make a UTub
    WHEN the createUTub form is sent with the UTub Name that is sanitized by the backend
    THEN ensure U4I responds with a proper error message
    """
    app = provide_app
    USER_ID = 1
    login_user_to_home_page(app, browser, USER_ID)

    create_utub(browser, utub_name='<img src="evl.jpg">', utub_description="")

    # Submits new UTub
    wait_then_click_element(browser, HPL.BUTTON_UTUB_SUBMIT_CREATE)

    # Wait for POST request to fail
    invalid_utub_name_error = wait_then_get_element(
        browser, HPL.INPUT_UTUB_NAME_CREATE + HPL.INVALID_FIELD_SUFFIX, time=3
    )
    assert invalid_utub_name_error is not None
    assert invalid_utub_name_error.text == UTUB_FAILURE.INVALID_INPUT


def test_create_utub_sanitized_description(
    browser: WebDriver, create_test_users, provide_app: Flask
):
    """
    Tests a user's ability to create a UTub

    GIVEN a user attempting to make a UTub
    WHEN the createUTub form is sent with the UTub description that is sanitized by the backend
    THEN ensure U4I responds with a proper error message
    """
    app = provide_app
    USER_ID = 1
    login_user_to_home_page(app, browser, USER_ID)

    create_utub(
        browser, utub_name=UTS.TEST_UTUB_NAME_1, utub_description='<img src="evl.jpg">'
    )

    # Submits new UTub
    wait_then_click_element(browser, HPL.BUTTON_UTUB_SUBMIT_CREATE)

    # Wait for POST request to fail
    invalid_utub_name_error = wait_then_get_element(
        browser, HPL.INPUT_UTUB_DESCRIPTION_CREATE + HPL.INVALID_FIELD_SUFFIX, time=3
    )
    assert invalid_utub_name_error is not None
    assert invalid_utub_name_error.text == UTUB_FAILURE.INVALID_INPUT


def test_create_utub_invalid_csrf_token(
    browser: WebDriver, create_test_users, provide_app: Flask
):
    """
    Tests a user's ability to attempt to create a new UTub with an invalid CSRF token

    GIVEN a user attempting to make a UTub
    WHEN the createUTub form is sent with an invalid CSRF token
    THEN ensure U4I responds with a proper error message
    """
    app = provide_app
    USER_ID = 1
    with app.app_context():
        user: Users = Users.query.get(USER_ID)
        username = user.username
    login_user_to_home_page(app, browser, USER_ID)

    create_utub(
        browser, utub_name=UTS.TEST_UTUB_NAME_1, utub_description=UTS.TEST_UTUB_NAME_1
    )

    invalidate_csrf_token_on_page(browser)

    # Submits new UTub
    wait_then_click_element(browser, HPL.BUTTON_UTUB_SUBMIT_CREATE)

    assert_visited_403_on_invalid_csrf_and_reload(browser)

    # Page reloads after user clicks button in CSRF 403 error page
    create_utub_name_input = wait_until_hidden(
        browser, HPL.INPUT_UTUB_NAME_CREATE, timeout=3
    )
    assert not create_utub_name_input.is_displayed()
    assert_login_with_username(browser, username)
