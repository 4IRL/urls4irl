from flask import Flask
import pytest
from playwright.sync_api import Page, expect

from backend import db
from backend.models.users import Users
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utubs import Utubs
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from backend.utils.strings.utub_strs import (
    UTUB_CREATE_MSG,
    UTUB_DELETE_WARNING,
    UTUB_SELECT,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.locators import ModalLocators as ML
from tests.functional.playwright_assert_utils import (
    assert_active_utub,
    assert_login_with_username,
    assert_on_429_page,
    assert_visited_403_on_invalid_csrf_and_reload,
)
from tests.functional.db_utils import get_utub_this_user_created
from tests.functional.playwright_login_utils import login_user_and_select_utub_by_name
from tests.functional.playwright_utils import (
    add_forced_rate_limit_header,
    dismiss_modal_with_click_out,
    force_next_delete_ajax_failure_no_navigate,
    get_selected_utub_id,
    invalidate_csrf_token_on_page,
    wait_for_modal_ready,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_hidden,
    wait_until_visible_css_selector,
)
from tests.functional.utubs_ui.playwright_assert_utils import (
    assert_elems_hidden_after_utub_deleted,
)
from tests.functional.utubs_ui.playwright_utils import delete_utub_as_creator

pytestmark = pytest.mark.utubs_ui


def test_open_delete_utub_modal(page: Page, create_test_utubs, provide_app: Flask):
    """
    GIVEN a user on their Home page
    WHEN they select a UTub and click the Trash can icon
    THEN ensure the warning modal is shown
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=utub_user_created.name,
    )

    utub_delete_btn = wait_then_get_element(
        page=page, css_selector=HPL.BUTTON_UTUB_DELETE
    )
    assert utub_delete_btn is not None

    utub_delete_btn.click()

    warning_modal_body = wait_then_get_element(page=page, css_selector=HPL.BODY_MODAL)
    assert warning_modal_body is not None

    confirmation_modal_body_text = warning_modal_body.inner_text()

    # Assert warning modal appears with appropriate text
    assert confirmation_modal_body_text == UTUB_DELETE_WARNING


def test_dismiss_delete_utub_modal_x(page: Page, create_test_utubs, provide_app: Flask):
    """
    GIVEN a user on their Home page
    WHEN they select a UTub, click the Trash can icon, then clicks the 'x'
    THEN ensure the warning modal is hidden
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=utub_user_created.name,
    )

    expect(page.locator(HPL.HOME_MODAL).first).to_be_hidden()

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_DELETE)

    wait_for_modal_ready(page=page, modal_selector=HPL.HOME_MODAL)
    wait_then_click_element(page=page, css_selector=ML.BUTTON_X_MODAL_DISMISS)

    wait_until_hidden(page=page, css_selector=HPL.HOME_MODAL)


def test_dismiss_delete_utub_modal_btn(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a user on their Home page
    WHEN they select a UTub, click the Trash can icon, then clicks the 'Nevermind...' button
    THEN ensure the warning modal is hidden
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=utub_user_created.name,
    )

    expect(page.locator(HPL.HOME_MODAL).first).to_be_hidden()

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_DELETE)

    wait_then_click_element(page=page, css_selector=ML.BUTTON_MODAL_DISMISS)

    wait_until_hidden(page=page, css_selector=HPL.HOME_MODAL)


def test_dismiss_delete_utub_modal_key(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a user on their Home page
    WHEN they select a UTub, click the Trash can icon, then presses 'Esc'
    THEN ensure the warning modal is hidden
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=utub_user_created.name,
    )

    with app.app_context():
        utub: Utubs = Utubs.query.filter(Utubs.name == UTS.TEST_UTUB_NAME_1).first()
        assert utub.utub_creator == user_id_for_test

    expect(page.locator(HPL.HOME_MODAL).first).to_be_hidden()

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_DELETE)

    wait_for_modal_ready(page=page, modal_selector=HPL.HOME_MODAL)
    page.locator(HPL.HOME_MODAL).press("Escape")

    wait_until_hidden(page=page, css_selector=HPL.HOME_MODAL)


def test_dismiss_delete_utub_modal_click(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a user on their Home page
    WHEN they select a UTub, click the Trash can icon, then clicks anywhere outside of the modal
    THEN ensure the warning modal is hidden
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=utub_user_created.name,
    )

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_DELETE)

    wait_for_modal_ready(page=page, modal_selector=HPL.HOME_MODAL)
    dismiss_modal_with_click_out(page=page, modal_selector=HPL.HOME_MODAL)

    wait_until_hidden(page=page, css_selector=HPL.HOME_MODAL)


def test_delete_utub_btn(page: Page, create_test_utubs, provide_app: Flask):
    """
    GIVEN a user trying to delete one of the UTubs they created
    WHEN they try to delete the UTub
    THEN ensure the UTub selector is removed, and all relevant buttons are hidden
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=utub_user_created.name,
    )

    utub_id = get_selected_utub_id(page=page)
    css_selector = f'{HPL.SELECTORS_UTUB}[utubid="{utub_id}"]'

    expect(page.locator(css_selector)).to_be_attached()

    delete_utub_as_creator(page=page, utub_to_delete=utub_user_created)

    # Assert UTub selector no longer exists
    css_selector = f'{HPL.SELECTORS_UTUB}[utubid="{utub_id}"]'
    assert page.locator(css_selector).count() == 0

    # Assert that the no utub selected UI is shown
    assert_elems_hidden_after_utub_deleted(page=page)


def test_member_buttons_hidden_after_deleting_utub_with_others_remaining(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN an owner deletes a UTub they created while other UTubs remain (so the
        deck updates rather than resetting to the empty state)
    WHEN the delete completes and no UTub is selected
    THEN the member action buttons (add-member and leave) must both be hidden
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=utub_user_created.name,
    )

    # Before-state: add-member button visible while the owner's UTub is selected
    add_member_btn = wait_then_get_element(
        page=page, css_selector=HPL.BUTTON_MEMBER_CREATE
    )
    assert add_member_btn is not None

    delete_utub_as_creator(page=page, utub_to_delete=utub_user_created)

    # Other UTubs remain, so the UTub deck updates but no UTub is selected — the
    # member action buttons must stay hidden.
    expect(page.locator(HPL.BUTTON_MEMBER_CREATE).first).to_be_hidden()
    expect(page.locator(HPL.BUTTON_UTUB_LEAVE).first).to_be_hidden()


def test_delete_utub_rate_limits(page: Page, create_test_utubs, provide_app: Flask):
    """
    GIVEN a user trying to delete one of the UTubs they created but they're rate limited
    WHEN they try to delete the UTub
    THEN ensure the rate limited page is shown
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=utub_user_created.name,
    )

    utub_id = get_selected_utub_id(page=page)
    css_selector = f'{HPL.SELECTORS_UTUB}[utubid="{utub_id}"]'

    expect(page.locator(css_selector)).to_be_attached()

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_DELETE)

    add_forced_rate_limit_header(page=page)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)

    assert_on_429_page(page=page)


def test_delete_last_utub_no_urls_no_tags_no_members(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a user has one UTub with no URLs, tags, or member
    WHEN they delete the UTub
    THEN ensure the main page shows appropriate prompts to create a new UTub
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=utub_user_created.name,
    )

    delete_utub_as_creator(page=page, utub_to_delete=utub_user_created)

    # Make sure all relevant buttons and subheaders are hidden when no UTub selected
    assert_elems_hidden_after_utub_deleted(page=page)

    assert page.locator(HPL.SUBHEADER_URL_DECK).inner_text() == UTUB_SELECT
    assert page.locator(HPL.SUBHEADER_UTUB_DECK).inner_text() == UTUB_CREATE_MSG
    expect(page.locator(HPL.UTUB_SEARCH_WRAP).first).to_be_hidden()


def test_delete_last_utub_with_urls_tags_members(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN a user has one UTub with no URLs, tags, or member
    WHEN they delete the UTub
    THEN ensure the main page shows appropriate prompts to create a new UTub
    """
    app = provide_app
    user_id_for_test = 1

    utub_user_created = get_utub_this_user_created(app, user_id_for_test)

    with app.app_context():
        Utub_Members.query.filter(
            Utub_Members.user_id == user_id_for_test,
            Utub_Members.utub_id != utub_user_created.id,
        ).delete()
        db.session.commit()

    login_user_and_select_utub_by_name(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=utub_user_created.name,
    )

    delete_utub_as_creator(page=page, utub_to_delete=utub_user_created)

    # Make sure all relevant buttons and subheaders are hidden when no UTub selected
    assert_elems_hidden_after_utub_deleted(page=page)

    assert page.locator(HPL.SUBHEADER_URL_DECK).inner_text() == UTUB_SELECT
    assert page.locator(HPL.SUBHEADER_UTUB_DECK).inner_text() == UTUB_CREATE_MSG
    expect(page.locator(HPL.UTUB_SEARCH_WRAP).first).to_be_hidden()

    assert page.locator(HPL.SELECTORS_UTUB).count() == 0
    assert page.locator(HPL.BADGES_MEMBERS).count() == 0
    assert page.locator(HPL.TAG_FILTERS).count() == 0
    assert page.locator(HPL.ROWS_URLS).count() == 0


def test_delete_utub_invalid_csrf_token(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a user trying to delete one of the UTubs they created with an invalid CSRF token
    WHEN they try to delete the UTub with an invalid CSRF token
    THEN ensure U4I responds with a proper error message
    """
    app = provide_app
    user_id_for_test = 1
    with app.app_context():
        user: Users = Users.query.get(user_id_for_test)
        username = user.username
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=utub_user_created.name,
    )

    utub_id = get_selected_utub_id(page=page)
    css_selector = f'{HPL.SELECTORS_UTUB}[utubid="{utub_id}"]'

    expect(page.locator(css_selector)).to_be_attached()
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_DELETE)

    invalidate_csrf_token_on_page(page=page)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)

    assert_visited_403_on_invalid_csrf_and_reload(page=page)

    # Page reloads after user clicks button in CSRF 403 error page
    assert_login_with_username(page=page, username=username)

    # Reload will bring user back to the UTub they were in before
    assert_active_utub(page=page, utub_name=utub_user_created.name)

    wait_until_hidden(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)


def test_delete_utub_submit_button_reenables_on_server_error(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    Tests that the submit button re-enables after a server error so the user can retry.

    GIVEN a user who owns a UTub and the delete UTub confirmation modal is open
    WHEN the DELETE request fails with a 500 server error
    THEN ensure the #modalSubmit button is re-enabled (not disabled)
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=utub_user_created.name,
    )

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_DELETE)

    # Force the next DELETE ajax call to fail (with early return to prevent navigation)
    force_next_delete_ajax_failure_no_navigate(page=page)

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)

    # Poll until the async failure handler re-enables the submit button
    expect(page.locator(HPL.BUTTON_MODAL_SUBMIT)).to_be_enabled()


def test_delete_utub_submit_button_enabled_on_second_modal_open(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    Tests that the submit button is enabled when opening the delete modal for a
    second UTub after successfully deleting the first.

    GIVEN a user who owns at least 2 UTubs
    WHEN they successfully delete UTub A and then open the delete modal for UTub B
    THEN ensure the #modalSubmit button is NOT disabled
    """
    app = provide_app
    user_id_for_test = 1
    first_utub_created = get_utub_this_user_created(app, user_id_for_test)

    # Create a second UTub for user 1 directly in the database
    with app.app_context():
        second_utub = Utubs(
            name="MockUTub_second",
            utub_creator=user_id_for_test,
            utub_description="Second UTub for delete test",
        )
        db.session.add(second_utub)
        db.session.flush()
        second_utub_member = Utub_Members()
        second_utub_member.member_role = Member_Role.CREATOR
        second_utub_member.user_id = user_id_for_test
        second_utub_member.to_utub = second_utub
        db.session.add(second_utub_member)
        db.session.commit()
        second_utub_id = second_utub.id

    login_user_and_select_utub_by_name(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=first_utub_created.name,
    )

    # Delete the first UTub
    delete_utub_as_creator(page=page, utub_to_delete=first_utub_created)

    # Select the second UTub and open its delete modal
    second_utub_css_selector = f'{HPL.SELECTORS_UTUB}[utubid="{second_utub_id}"]'
    wait_then_click_element(page=page, css_selector=second_utub_css_selector)
    wait_until_visible_css_selector(page=page, css_selector=HPL.BUTTON_UTUB_DELETE)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_DELETE)
    wait_until_visible_css_selector(page=page, css_selector=HPL.HOME_MODAL)

    # Assert the submit button is NOT disabled when the modal opens for the second UTub
    expect(page.locator(HPL.BUTTON_MODAL_SUBMIT)).to_be_enabled()
