from flask import Flask
import pytest
from playwright.sync_api import Page

from backend.cli.mock_constants import MOCK_UTUB_NAME_BASE
from backend.models.users import Users
from backend.models.utubs import Utubs
from backend.utils.constants import CONSTANTS
from backend.utils.strings.json_strs import FIELD_REQUIRED_STR
from backend.utils.strings.utub_strs import UTUB_FAILURE, UTUB_UPDATE_SAME_NAME
from tests.functional.db_utils import get_utub_this_user_created
from tests.functional.login_utils import create_user_session_and_provide_session_id
from tests.functional.playwright_assert_utils import (
    assert_login_with_username,
    assert_not_visible_css_selector,
    assert_on_429_page,
    assert_visited_403_on_invalid_csrf_and_reload,
)
from tests.functional.playwright_login_utils import (
    login_user_and_select_utub_by_name,
    login_user_and_select_utub_by_utubid,
)
from tests.functional.playwright_utils import (
    add_forced_rate_limit_header,
    current_base_url,
    get_all_url_ids_in_selected_utub,
    get_all_utub_selector_names,
    get_selected_utub_name,
    invalidate_csrf_token_on_page,
    login_user_with_cookie_from_session,
    select_utub_by_name,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_hidden,
    wait_until_in_focus,
    wait_until_utub_name_appears,
)
from tests.functional.utubs_ui.playwright_utils import (
    open_update_utub_name_input,
    update_utub_name,
)
from tests.functional.locators import HomePageLocators as HPL

pytestmark = pytest.mark.utubs_ui


def test_select_utub_changes_utub_name(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    Tests a user's ability to select a specific UTub and observe the changes in display.

    GIVEN a fresh load of the U4I Home page
    WHEN user selects a UTub, then selects another UTub
    THEN ensure the URL deck header changes and displayed URLs change
    """
    app = provide_app
    user_id = 1
    session_id = create_user_session_and_provide_session_id(app, user_id)
    base_url = current_base_url(page=page)
    login_user_with_cookie_from_session(
        context=page.context, session_id=session_id, base_url=base_url
    )
    page.goto(f"{base_url}/home")

    utub_selector_names = get_all_utub_selector_names(page=page)
    current_utub_name = utub_selector_names[0]

    select_utub_by_name(page=page, utub_name=current_utub_name)
    current_utub_url_ids = get_all_url_ids_in_selected_utub(page=page)

    next_utub_name = utub_selector_names[1]

    select_utub_by_name(page=page, utub_name=next_utub_name)
    next_utub_url_ids = get_all_url_ids_in_selected_utub(page=page)

    assert not any([url_id in next_utub_url_ids for url_id in current_utub_url_ids])


def test_open_update_utub_name_input_creator(
    page: Page, create_test_utubs, provide_app: Flask
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

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    utub_name_elem = wait_then_get_element(page=page, css_selector=HPL.HEADER_URL_DECK)
    assert utub_name_elem is not None
    utub_name = utub_name_elem.inner_text()

    open_update_utub_name_input(page=page)

    utub_name_update_input = wait_then_get_element(
        page=page, css_selector=HPL.INPUT_UTUB_NAME_UPDATE
    )
    assert utub_name_update_input is not None

    assert utub_name == utub_name_update_input.input_value()


def test_open_update_utub_name_input_member(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a fresh load of the U4I Home page
    WHEN a non-owner member selects a UTub
    THEN the UTub title does not have the editable class and clicking it does not open the edit input
    """
    app = provide_app
    user_id = 1
    with app.app_context():
        utub: Utubs = Utubs.query.filter(Utubs.utub_creator != user_id).first()

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id, utub_id=utub.id
    )
    wait_until_utub_name_appears(page=page, utub_name=utub.name)

    utub_title = wait_then_get_element(page=page, css_selector=HPL.HEADER_URL_DECK)
    assert HPL.EDITABLE_CLASS not in (utub_title.get_attribute("class") or "")

    utub_title.click()
    assert_not_visible_css_selector(page=page, css_selector=HPL.INPUT_UTUB_NAME_UPDATE)


def test_switch_from_owned_to_non_owned_utub_removes_name_editable(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a user who owns one UTub and is a member of another
    WHEN the user selects their owned UTub, then switches to a non-owned UTub
    THEN the UTub title should lose the editable class and clicking it should not open the edit input
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    with app.app_context():
        utub_not_owned: Utubs = Utubs.query.filter(
            Utubs.utub_creator != user_id
        ).first()

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    utub_title = wait_then_get_element(page=page, css_selector=HPL.HEADER_URL_DECK)
    assert HPL.EDITABLE_CLASS in (utub_title.get_attribute("class") or "")

    select_utub_by_name(page=page, utub_name=utub_not_owned.name)
    wait_until_utub_name_appears(page=page, utub_name=utub_not_owned.name)

    utub_title = wait_then_get_element(page=page, css_selector=HPL.HEADER_URL_DECK)
    assert HPL.EDITABLE_CLASS not in (utub_title.get_attribute("class") or "")

    utub_title.click()
    assert_not_visible_css_selector(page=page, css_selector=HPL.INPUT_UTUB_NAME_UPDATE)


def test_close_update_utub_name_input_btn(
    page: Page, create_test_utubs, provide_app: Flask
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

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    open_update_utub_name_input(page=page)

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_NAME_CANCEL_UPDATE)

    wait_until_hidden(page=page, css_selector=HPL.INPUT_UTUB_NAME_UPDATE)


def test_close_update_utub_name_input_key(
    page: Page, create_test_utubs, provide_app: Flask
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

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    open_update_utub_name_input(page=page)

    wait_until_in_focus(page=page, css_selector=HPL.INPUT_UTUB_NAME_UPDATE)
    page.keyboard.press("Escape")

    wait_until_hidden(page=page, css_selector=HPL.INPUT_UTUB_NAME_UPDATE)


def test_update_utub_name_btn(page: Page, create_test_utubs, provide_app: Flask):
    """
    Tests a UTub owner's ability to update a selected UTub's name.

    GIVEN a user owns a UTub
    WHEN they submit the editUTub form
    THEN ensure the form is hidden, the UTub selector name and URL deck header are updated.
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    new_utub_name = MOCK_UTUB_NAME_BASE + "2"

    update_utub_name(page=page, utub_name=new_utub_name)

    # Submits new UTub name
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_NAME_SUBMIT_UPDATE)

    # Wait for POST request
    wait_until_hidden(page=page, css_selector=HPL.BUTTON_UTUB_NAME_SUBMIT_UPDATE)

    url_deck_header = get_selected_utub_name(page=page)

    # Assert new UTub name is updated in URL Deck
    assert new_utub_name == url_deck_header

    utub_selector_names = get_all_utub_selector_names(page=page)

    # Assert new UTub name is updated in UTub Deck
    assert new_utub_name in utub_selector_names


def test_update_utub_name_key(page: Page, create_test_utubs, provide_app: Flask):
    """
    Tests a UTub owner's ability to update a selected UTub's name.

    GIVEN a user owns a UTub
    WHEN they submit the editUTub form
    THEN ensure the form is hidden, the UTub selector name and URL deck header are updated.
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    new_utub_name = MOCK_UTUB_NAME_BASE + "2"

    update_utub_name(page=page, utub_name=new_utub_name)

    # Submits new UTub name
    wait_until_in_focus(page=page, css_selector=HPL.INPUT_UTUB_NAME_UPDATE)
    page.keyboard.press("Enter")

    # Wait for POST request
    wait_until_hidden(page=page, css_selector=HPL.BUTTON_UTUB_NAME_SUBMIT_UPDATE)

    url_deck_header = get_selected_utub_name(page=page)

    # Assert new UTub name is updated in URL Deck
    assert new_utub_name == url_deck_header

    utub_selector_names = get_all_utub_selector_names(page=page)

    # Assert new UTub name is updated in UTub Deck
    assert new_utub_name in utub_selector_names


def test_update_utub_name_rate_limits(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    Tests a UTub owner's ability to update a selected UTub's name, but they are rate limited.

    GIVEN a user owns a UTub but they are rate limited
    WHEN they submit the editUTub form
    THEN ensure the 429 error page is shown
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    new_utub_name = MOCK_UTUB_NAME_BASE + "2"

    update_utub_name(page=page, utub_name=new_utub_name)

    # Submits new UTub name
    add_forced_rate_limit_header(page=page)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_NAME_SUBMIT_UPDATE)

    assert_on_429_page(page=page)


def test_update_utub_name_length_exceeded(
    page: Page, create_test_utubs, provide_app: Flask
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

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    new_utub_name = "a" * (CONSTANTS.UTUBS.MAX_NAME_LENGTH + 1)

    update_utub_name(page=page, utub_name=new_utub_name)

    update_utub_name_input = wait_then_get_element(
        page=page, css_selector=HPL.INPUT_UTUB_NAME_UPDATE
    )
    assert update_utub_name_input is not None
    actual_utub_name = update_utub_name_input.input_value()
    assert actual_utub_name is not None

    assert len(actual_utub_name) == CONSTANTS.UTUBS.MAX_NAME_LENGTH


def test_update_utub_name_empty_field(
    page: Page, create_test_utubs, provide_app: Flask
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

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    update_utub_name(page=page, utub_name="")

    # Submits new UTub name
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_NAME_SUBMIT_UPDATE)

    # Wait for POST request
    invalid_utub_name_field = wait_then_get_element(
        page=page,
        css_selector=HPL.INPUT_UTUB_NAME_UPDATE + HPL.INVALID_FIELD_SUFFIX,
    )
    assert invalid_utub_name_field is not None
    assert invalid_utub_name_field.inner_text() == FIELD_REQUIRED_STR


def test_update_utub_name_sanitized(page: Page, create_test_utubs, provide_app: Flask):
    """
    Tests a UTub owner's ability to update a selected UTub's name.

    GIVEN a user owns a UTub
    WHEN they attempt to enter an UTub name that is sanitized by the backend
    THEN ensure the proper error response is shown.
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    update_utub_name(page=page, utub_name='<img src="evl.jpg">')

    # Submits new UTub name
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_NAME_SUBMIT_UPDATE)

    # Wait for POST request
    invalid_utub_name_field = wait_then_get_element(
        page=page,
        css_selector=HPL.INPUT_UTUB_NAME_UPDATE + HPL.INVALID_FIELD_SUFFIX,
    )
    assert invalid_utub_name_field is not None
    assert invalid_utub_name_field.inner_text() == UTUB_FAILURE.INVALID_INPUT


def test_update_utub_name_similar(
    page: Page,
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

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    utub_selector_names = get_all_utub_selector_names(page=page)

    new_utub_name = utub_selector_names[1]

    update_utub_name(page=page, utub_name=new_utub_name)

    # Submits new UTub name
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_NAME_SUBMIT_UPDATE)

    warning_modal_body = wait_then_get_element(page=page, css_selector=HPL.BODY_MODAL)
    assert warning_modal_body is not None
    confirmation_modal_body_text = warning_modal_body.inner_text()

    # Assert warning modal appears with appropriate text
    assert confirmation_modal_body_text == UTUB_UPDATE_SAME_NAME

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)

    # Wait for POST request
    wait_until_hidden(page=page, css_selector=HPL.BODY_MODAL)

    url_deck_header = get_selected_utub_name(page=page)

    # Assert new UTub name is updated in URL Deck
    assert new_utub_name == url_deck_header

    # Assert new UTub name is updated in UTub Deck
    assert new_utub_name in utub_selector_names


def test_update_utub_name_invalid_csrf_token(
    page: Page, create_test_utubs, provide_app: Flask
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

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    new_utub_name = MOCK_UTUB_NAME_BASE + "2"

    update_utub_name(page=page, utub_name=new_utub_name)

    invalidate_csrf_token_on_page(page=page)

    # Submits new UTub name
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_NAME_SUBMIT_UPDATE)

    assert_visited_403_on_invalid_csrf_and_reload(page=page)

    # Page reloads after user clicks button in CSRF 403 error page
    wait_until_hidden(page=page, css_selector=HPL.INPUT_UTUB_NAME_UPDATE)
    assert_login_with_username(page=page, username=username)
