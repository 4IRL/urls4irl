from flask import Flask
import pytest
from playwright.sync_api import Page

from backend.cli.mock_constants import MOCK_UTUB_DESCRIPTION
from backend.models.users import Users
from backend.utils.constants import CONSTANTS
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from backend.utils.strings.json_strs import FIELD_REQUIRED_STR
from backend.utils.strings.utub_strs import UTUB_CREATE_SAME_NAME, UTUB_FAILURE
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_assert_utils import (
    assert_active_utub,
    assert_login_with_username,
    assert_on_429_page,
    assert_visited_403_on_invalid_csrf_and_reload,
)
from tests.functional.playwright_utils import (
    add_forced_rate_limit_header,
    invalidate_csrf_token_on_page,
    login_user_to_home_page,
    wait_then_click_element,
    wait_then_get_element,
    wait_then_get_elements,
    wait_until_hidden,
    wait_until_in_focus,
)
from tests.functional.utubs_ui.playwright_utils import create_utub

pytestmark = pytest.mark.utubs_ui


def test_open_create_utub_input(page: Page, create_test_users, provide_app: Flask):
    """
    Tests a user's ability to open the createUTub input using the plus button.

    GIVEN a fresh load of the U4I Home page
    WHEN user clicks the UTub module plus button
    THEN ensure the createUTub input opens
    """
    app = provide_app
    USER_ID = 1
    login_user_to_home_page(app=app, page=page, user_id=USER_ID)

    # Click createUTub button to show input
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_CREATE)

    create_utub_name_input = wait_then_get_element(
        page=page, css_selector=HPL.INPUT_UTUB_NAME_CREATE
    )
    assert create_utub_name_input is not None

    create_utub_desc_input = wait_then_get_element(
        page=page, css_selector=HPL.INPUT_UTUB_DESCRIPTION_CREATE
    )
    assert create_utub_desc_input is not None

    wait_until_in_focus(page=page, css_selector=HPL.INPUT_UTUB_NAME_CREATE)

    create_utub_submit_btn = wait_then_get_element(
        page=page, css_selector=HPL.BUTTON_UTUB_SUBMIT_CREATE
    )
    assert create_utub_submit_btn is not None

    create_utub_cancel_btn = wait_then_get_element(
        page=page, css_selector=HPL.BUTTON_UTUB_CANCEL_CREATE
    )
    assert create_utub_cancel_btn is not None


def test_close_create_utub_input_btn(page: Page, create_test_users, provide_app: Flask):
    """
    Tests a user's ability to close the createUTub input by clicking the 'x' button

    GIVEN a fresh load of the U4I Home page
    WHEN user opens the createUTub input, then clicks the 'x'
    THEN ensure the createUTub input is closed
    """
    app = provide_app
    USER_ID = 1
    login_user_to_home_page(app=app, page=page, user_id=USER_ID)

    # Click createUTub button to show input
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_CREATE)

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_CANCEL_CREATE)

    wait_until_hidden(page=page, css_selector=HPL.INPUT_UTUB_NAME_CREATE)


def test_close_create_utub_input_key(page: Page, create_test_users, provide_app: Flask):
    """
    Tests a user's ability to close the createUTub input by pressing the Escape key

    GIVEN a fresh load of the U4I Home page
    WHEN user opens the createUTub input, then presses 'Esc'
    THEN ensure the createUTub input is closed
    """
    app = provide_app
    USER_ID = 1
    login_user_to_home_page(app=app, page=page, user_id=USER_ID)

    # Click createUTub button to show input
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_CREATE)

    wait_until_in_focus(page=page, css_selector=HPL.INPUT_UTUB_NAME_CREATE)
    page.keyboard.press("Escape")

    wait_until_hidden(page=page, css_selector=HPL.INPUT_UTUB_NAME_CREATE)


def test_create_utub_btn(page: Page, create_test_users, provide_app: Flask):
    """
    Tests a user's ability to create a UTub

    GIVEN a user attempting to make a UTub
    WHEN the createUTub form is populated and submitted by the 'check' button
    THEN ensure the new UTub is successfully added to the user's UTub Deck and is selected.
    """
    app = provide_app
    USER_ID = 1
    login_user_to_home_page(app=app, page=page, user_id=USER_ID)

    utub_name = UTS.TEST_UTUB_NAME_1

    create_utub(page=page, utub_name=utub_name, utub_description=MOCK_UTUB_DESCRIPTION)

    # Submits new UTub
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_SUBMIT_CREATE)

    # Wait for POST request
    wait_until_hidden(page=page, css_selector=HPL.INPUT_UTUB_NAME_CREATE)

    assert_active_utub(page=page, utub_name=utub_name)
    utub_selector_for_creator_icon = f"{HPL.SELECTORS_UTUB} {HPL.CREATOR_ICON}"

    icon = wait_then_get_element(page=page, css_selector=utub_selector_for_creator_icon)
    assert icon is not None


def test_create_utub_key(page: Page, create_test_users, provide_app: Flask):
    """
    Tests a user's ability to create a UTub

    GIVEN a user attempting to make a UTub
    WHEN the createUTub form is populated and submitted by pressing the 'Enter' key
    THEN ensure the new UTub is successfully added to the user's UTub Deck and is selected.
    """
    app = provide_app
    USER_ID = 1
    login_user_to_home_page(app=app, page=page, user_id=USER_ID)

    utub_name = UTS.TEST_UTUB_NAME_1

    create_utub(page=page, utub_name=utub_name, utub_description=MOCK_UTUB_DESCRIPTION)

    wait_until_in_focus(page=page, css_selector=HPL.INPUT_UTUB_DESCRIPTION_CREATE)
    page.keyboard.press("Enter")

    # Wait for POST request
    wait_until_hidden(page=page, css_selector=HPL.INPUT_UTUB_NAME_CREATE)

    assert_active_utub(page=page, utub_name=utub_name)
    utub_selector_for_creator_icon = f"{HPL.SELECTORS_UTUB} {HPL.CREATOR_ICON}"

    icon = wait_then_get_element(page=page, css_selector=utub_selector_for_creator_icon)
    assert icon is not None


def test_create_utub_rate_limits(page: Page, create_test_users, provide_app: Flask):
    """
    Tests a user's ability to create a UTub when they are rate limited

    GIVEN a user attempting to make a UTub that is rate limited
    WHEN the createUTub form is populated and submitted by the 'check' button
    THEN ensure the 429 error page is shown
    """
    app = provide_app
    USER_ID = 1
    login_user_to_home_page(app=app, page=page, user_id=USER_ID)

    utub_name = UTS.TEST_UTUB_NAME_1

    create_utub(page=page, utub_name=utub_name, utub_description=MOCK_UTUB_DESCRIPTION)
    add_forced_rate_limit_header(page=page)

    # Submits new UTub
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_SUBMIT_CREATE)
    assert_on_429_page(page=page)


def test_create_utub_name_length_exceeded(
    page: Page, create_test_users, provide_app: Flask
):
    """
    Tests the site error response to a user's attempt to create a new UTub with a name that exceeds the maximum character length limit.

    GIVEN a user attempting to make a UTub
    WHEN the createUTub form is populated and submitted with a name that exceeds character limits
    THEN ensure the appropriate error and prompt is shown to user.
    """
    app = provide_app
    USER_ID = 1
    login_user_to_home_page(app=app, page=page, user_id=USER_ID)

    oversized_utub_name = "a" * CONSTANTS.UTUBS.MAX_NAME_LENGTH
    create_utub(
        page=page,
        utub_name=oversized_utub_name,
        utub_description=oversized_utub_name,
    )

    create_utub_name_input = wait_then_get_element(
        page=page, css_selector=HPL.INPUT_UTUB_NAME_CREATE
    )
    assert create_utub_name_input is not None
    current_input = create_utub_name_input.input_value()
    assert current_input is not None

    # HTML element has a maxlength on it, so check that the input is still the max length
    assert len(current_input) == CONSTANTS.UTUBS.MAX_NAME_LENGTH


def test_create_utub_name_similar(page: Page, create_test_utubs, provide_app: Flask):
    """
    Tests the site warning response to a user's attempt to create a new UTub with a name that is similar to one already in their UTub Deck.

    GIVEN a user
    WHEN the createUTub form is populated and submitted with a name that is similar to one already in their UTub Deck
    THEN ensure the appropriate warning and prompt for confirmation is shown to user.
    """
    app = provide_app
    USER_ID = 1
    login_user_to_home_page(app=app, page=page, user_id=USER_ID)

    # Extract name of a pre-existing UTub
    utub_selectors = wait_then_get_elements(page=page, css_selector=HPL.SELECTORS_UTUB)
    first_utub_selector = utub_selectors[0]
    utub_name = first_utub_selector.inner_text()

    # Attempt to add a new UTub with the same name
    create_utub(page=page, utub_name=utub_name, utub_description=MOCK_UTUB_DESCRIPTION)
    # Submits new UTub
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_SUBMIT_CREATE)

    # Extract modal body element
    confirmation_modal_body = wait_then_get_element(
        page=page, css_selector=HPL.BODY_MODAL
    )
    assert confirmation_modal_body is not None
    confirmation_modal_body_text = confirmation_modal_body.inner_text()
    utub_same_name_check_text = UTUB_CREATE_SAME_NAME

    # Assert modal prompts user to consider duplicate UTub naming
    assert confirmation_modal_body_text == utub_same_name_check_text


def test_create_utub_empty_utub_name(page: Page, create_test_users, provide_app: Flask):
    """
    Tests a user's ability to create a UTub

    GIVEN a user attempting to make a UTub
    WHEN the createUTub form is sent with the UTub Name field being empty
    THEN ensure U4I responds with a proper error message
    """
    app = provide_app
    USER_ID = 1
    login_user_to_home_page(app=app, page=page, user_id=USER_ID)

    create_utub(page=page, utub_name="", utub_description="")

    # Submits new UTub
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_SUBMIT_CREATE)

    # Wait for POST request to fail
    invalid_utub_name_error = wait_then_get_element(
        page=page,
        css_selector=HPL.INPUT_UTUB_NAME_CREATE + HPL.INVALID_FIELD_SUFFIX,
    )
    assert invalid_utub_name_error is not None
    assert invalid_utub_name_error.inner_text() == FIELD_REQUIRED_STR


def test_create_utub_sanitized_name(page: Page, create_test_users, provide_app: Flask):
    """
    Tests a user's ability to create a UTub

    GIVEN a user attempting to make a UTub
    WHEN the createUTub form is sent with the UTub Name that is sanitized by the backend
    THEN ensure U4I responds with a proper error message
    """
    app = provide_app
    USER_ID = 1
    login_user_to_home_page(app=app, page=page, user_id=USER_ID)

    create_utub(page=page, utub_name='<img src="evl.jpg">', utub_description="")

    # Submits new UTub
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_SUBMIT_CREATE)

    # Wait for POST request to fail
    invalid_utub_name_error = wait_then_get_element(
        page=page,
        css_selector=HPL.INPUT_UTUB_NAME_CREATE + HPL.INVALID_FIELD_SUFFIX,
    )
    assert invalid_utub_name_error is not None
    assert invalid_utub_name_error.inner_text() == UTUB_FAILURE.INVALID_INPUT


def test_create_utub_sanitized_description(
    page: Page, create_test_users, provide_app: Flask
):
    """
    Tests a user's ability to create a UTub

    GIVEN a user attempting to make a UTub
    WHEN the createUTub form is sent with the UTub description that is sanitized by the backend
    THEN ensure U4I responds with a proper error message
    """
    app = provide_app
    USER_ID = 1
    login_user_to_home_page(app=app, page=page, user_id=USER_ID)

    create_utub(
        page=page,
        utub_name=UTS.TEST_UTUB_NAME_1,
        utub_description='<img src="evl.jpg">',
    )

    # Submits new UTub
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_SUBMIT_CREATE)

    # Wait for POST request to fail
    invalid_utub_name_error = wait_then_get_element(
        page=page,
        css_selector=HPL.INPUT_UTUB_DESCRIPTION_CREATE + HPL.INVALID_FIELD_SUFFIX,
    )
    assert invalid_utub_name_error is not None
    assert invalid_utub_name_error.inner_text() == UTUB_FAILURE.INVALID_INPUT


def test_create_utub_invalid_csrf_token(
    page: Page, create_test_users, provide_app: Flask
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
    login_user_to_home_page(app=app, page=page, user_id=USER_ID)

    create_utub(
        page=page,
        utub_name=UTS.TEST_UTUB_NAME_1,
        utub_description=UTS.TEST_UTUB_NAME_1,
    )

    invalidate_csrf_token_on_page(page=page)

    # Submits new UTub
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_SUBMIT_CREATE)

    assert_visited_403_on_invalid_csrf_and_reload(page=page)

    # Page reloads after user clicks button in CSRF 403 error page
    wait_until_hidden(page=page, css_selector=HPL.INPUT_UTUB_NAME_CREATE)
    assert_login_with_username(page=page, username=username)
