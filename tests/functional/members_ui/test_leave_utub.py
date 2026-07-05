from flask import Flask
import pytest
from playwright.sync_api import Page, expect

from tests.functional.locators import HomePageLocators as HPL
from backend.models.users import Users
from backend.models.utub_members import Utub_Members
from backend.models.utubs import Utubs
from backend.utils.strings.user_strs import MEMBER_LEAVE_WARNING
from tests.functional.db_utils import (
    get_utub_this_user_created,
    get_utub_this_user_did_not_create,
)
from tests.functional.members_ui.playwright_utils import leave_utub_as_member
from tests.functional.playwright_assert_utils import (
    assert_login_with_username,
    assert_on_429_page,
    assert_visited_403_on_invalid_csrf_and_reload,
)
from tests.functional.playwright_login_utils import login_user_and_select_utub_by_name
from tests.functional.playwright_utils import (
    add_forced_rate_limit_header,
    dismiss_modal_with_click_out,
    force_next_delete_ajax_failure_no_navigate,
    get_num_utubs,
    invalidate_csrf_token_on_page,
    wait_for_modal_ready,
    wait_for_selector_to_be_removed,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_hidden,
    wait_until_in_focus,
    wait_until_utub_name_appears,
    wait_until_visible_css_selector,
)

pytestmark = pytest.mark.members_ui


def test_open_leave_utub_modal(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    Tests a UTub user's ability to open the leave UTub modal

    GIVEN a user is a UTub member
    WHEN the memberSelfBtnDelete button is clicked
    THEN ensure the user is shown the modal confirming if they want to leave the UTub
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_member_of = get_utub_this_user_did_not_create(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=utub_user_member_of.name,
    )

    leave_utub_btn = wait_then_get_element(
        page=page, css_selector=HPL.BUTTON_UTUB_LEAVE
    )
    expect(leave_utub_btn).to_be_visible()
    leave_utub_btn.click()

    warning_modal_body = wait_then_get_element(page=page, css_selector=HPL.BODY_MODAL)
    expect(warning_modal_body).to_be_visible()
    expect(warning_modal_body).to_have_text(MEMBER_LEAVE_WARNING)


def test_dismiss_leave_utub_modal_btn(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    Tests a UTub user's ability to dismiss the leave UTub modal

    GIVEN a user is a UTub member, and has opened the leave UTub modal
    WHEN the "Stay In UTub" button is clicked
    THEN ensure the modal is hidden
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_member_of = get_utub_this_user_did_not_create(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=utub_user_member_of.name,
    )

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_LEAVE)
    wait_until_visible_css_selector(page=page, css_selector=HPL.HOME_MODAL)

    dismiss_modal_btn = page.locator(HPL.BUTTON_MODAL_DISMISS).first
    expect(dismiss_modal_btn).to_be_visible()
    dismiss_modal_btn.click()
    wait_until_hidden(page=page, css_selector=HPL.BODY_MODAL)


def test_dismiss_leave_utub_modal_x(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    Tests a UTub user's ability to dismiss the leave UTub modal

    GIVEN a user is a UTub member, and has opened the leave UTub modal
    WHEN the user clicks the X button on the modal
    THEN ensure the modal is hidden
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_member_of = get_utub_this_user_did_not_create(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=utub_user_member_of.name,
    )

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_LEAVE)
    wait_until_visible_css_selector(page=page, css_selector=HPL.HOME_MODAL)

    x_btn = page.locator(HPL.HOME_MODAL).locator(HPL.BUTTON_X_CLOSE).first
    expect(x_btn).to_be_visible()
    x_btn.click()
    wait_until_hidden(page=page, css_selector=HPL.BODY_MODAL)


def test_dismiss_leave_utub_modal_key(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    Tests a UTub user's ability to dismiss the leave UTub modal

    GIVEN a user is a UTub member, and has opened the leave UTub modal
    WHEN the user presses the escape key
    THEN ensure the modal is hidden
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_member_of = get_utub_this_user_did_not_create(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=utub_user_member_of.name,
    )

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_LEAVE)
    wait_until_visible_css_selector(page=page, css_selector=HPL.HOME_MODAL)
    wait_until_in_focus(page=page, css_selector=HPL.HOME_MODAL)
    page.keyboard.press("Escape")
    wait_until_hidden(page=page, css_selector=HPL.BODY_MODAL)


def test_dismiss_leave_utub_modal_click_outside_modal(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    Tests a UTub user's ability to dismiss the leave UTub modal

    GIVEN a user is a UTub member, and has opened the leave UTub modal
    WHEN the user clicks outside the modal
    THEN ensure the modal is hidden
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_member_of = get_utub_this_user_did_not_create(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=utub_user_member_of.name,
    )

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_LEAVE)
    wait_until_visible_css_selector(page=page, css_selector=HPL.HOME_MODAL)
    wait_for_modal_ready(page=page, modal_selector=HPL.HOME_MODAL)
    dismiss_modal_with_click_out(page=page, modal_selector=HPL.HOME_MODAL)
    wait_until_hidden(page=page, css_selector=HPL.BODY_MODAL)


def test_leave_utub(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    Tests a UTub user's ability to leave a UTub.

    GIVEN a user is a UTub member
    WHEN the memberSelfBtnDelete button is selected and user submits the confirm modal
    THEN ensure the user is successfully removed from the UTub.
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_member_of = get_utub_this_user_did_not_create(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=utub_user_member_of.name,
    )

    init_num_utubs = get_num_utubs(page=page)
    utub_css_selector = f'{HPL.SELECTORS_UTUB}[utubid="{utub_user_member_of.id}"]'

    leave_utub_as_member(page=page, utub_to_leave=utub_user_member_of)

    assert get_num_utubs(page=page) == init_num_utubs - 1
    assert page.locator(utub_css_selector).count() == 0
    assert page.locator(HPL.SELECTOR_SELECTED_UTUB).count() == 0


def test_leave_button_hidden_after_leaving_utub(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN a user is a member of a UTub (with other UTubs remaining)
    WHEN they leave the UTub, after which no UTub is selected
    THEN the leave-UTub button (memberSelfBtnDelete) must not be displayed
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_member_of = get_utub_this_user_did_not_create(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=utub_user_member_of.name,
    )

    # Before-state: the leave button is visible while the member's UTub is selected
    leave_btn = wait_then_get_element(page=page, css_selector=HPL.BUTTON_UTUB_LEAVE)
    expect(leave_btn).to_be_visible()

    leave_utub_as_member(page=page, utub_to_leave=utub_user_member_of)

    # After leaving, no UTub is selected, so the leave button must be hidden again
    expect(page.locator(HPL.BUTTON_UTUB_LEAVE)).to_be_hidden()


def test_leave_utub_rate_limits(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    Tests a UTub user's ability to leave a UTub when they are rate limited

    GIVEN a user is a UTub member but they are rate limited
    WHEN the memberSelfBtnDelete button is selected and user submits the confirm modal
    THEN ensure the 429 error page is shown
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_member_of = get_utub_this_user_did_not_create(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=utub_user_member_of.name,
    )

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_LEAVE)
    wait_then_get_element(page=page, css_selector=HPL.BODY_MODAL)

    add_forced_rate_limit_header(page=page)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)
    assert_on_429_page(page=page)


def test_cannot_leave_utub_as_utub_creator(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN a user is a UTub creator
    WHEN the user tries to leave the UTub
    THEN ensure the leave UTub button is not visible to the user
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_creator_of = get_utub_this_user_created(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=utub_user_creator_of.name,
    )

    expect(page.locator(HPL.BUTTON_UTUB_LEAVE)).to_be_hidden()


def test_leave_utub_invalid_csrf_token(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    Tests a UTub user's ability to leave a UTub.

    GIVEN a user is a UTub member
    WHEN the memberSelfBtnDelete button is selected and user submits the confirm modal
    THEN ensure the user is successfully removed from the UTub.
    """
    app = provide_app
    user_id_for_test = 1
    with app.app_context():
        user: Users = Users.query.get(user_id_for_test)
        username = user.username
    utub_user_member_of = get_utub_this_user_did_not_create(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=utub_user_member_of.name,
    )

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_LEAVE)
    wait_then_get_element(page=page, css_selector=HPL.BODY_MODAL)

    invalidate_csrf_token_on_page(page=page)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)
    assert_visited_403_on_invalid_csrf_and_reload(page=page)

    assert page.locator(HPL.BUTTON_MEMBER_DELETE).count() == 0
    wait_until_hidden(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)
    assert_login_with_username(page=page, username=username)


def test_leave_utub_submit_button_reenables_on_server_error(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    Tests that the submit button re-enables after a server error so the user can retry.

    GIVEN a user is a UTub member and the leave UTub confirmation modal is open
    WHEN the DELETE request fails with a 500 server error
    THEN ensure the #modalSubmit button is re-enabled (not disabled)
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_member_of = get_utub_this_user_did_not_create(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=utub_user_member_of.name,
    )

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_LEAVE)
    wait_until_visible_css_selector(page=page, css_selector=HPL.HOME_MODAL)

    force_next_delete_ajax_failure_no_navigate(page=page)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)

    expect(page.locator(HPL.BUTTON_MODAL_SUBMIT)).to_be_enabled()


def test_leave_utub_submit_button_enabled_on_second_modal_open(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    Tests that the submit button is enabled when opening the leave UTub modal for a
    second UTub after successfully leaving the first.

    GIVEN a user is a member of at least 2 UTubs they did not create
    WHEN they successfully leave UTub A and then open the leave modal for UTub B
    THEN ensure the #modalSubmit button is NOT disabled
    """
    app = provide_app
    user_id_for_test = 1

    with app.app_context():
        non_created_utubs: list = (
            Utubs.query.join(
                Utub_Members,
                (Utub_Members.utub_id == Utubs.id)
                & (Utub_Members.user_id == user_id_for_test),
            )
            .filter(Utubs.utub_creator != user_id_for_test)
            .all()
        )
        first_utub_id = non_created_utubs[0].id
        first_utub_name = non_created_utubs[0].name
        second_utub_id = non_created_utubs[1].id
        second_utub_name = non_created_utubs[1].name

    login_user_and_select_utub_by_name(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=first_utub_name,
    )

    first_utub_css_selector = f'{HPL.SELECTORS_UTUB}[utubid="{first_utub_id}"]'
    second_utub_css_selector = f'{HPL.SELECTORS_UTUB}[utubid="{second_utub_id}"]'

    # Leave the first UTub
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_LEAVE)
    wait_until_visible_css_selector(page=page, css_selector=HPL.HOME_MODAL)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)
    wait_until_hidden(page=page, css_selector=HPL.HOME_MODAL)
    wait_for_selector_to_be_removed(page=page, css_selector=first_utub_css_selector)

    # Select the second UTub and open the leave modal
    wait_then_click_element(page=page, css_selector=second_utub_css_selector)
    wait_until_utub_name_appears(page=page, utub_name=second_utub_name)

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_LEAVE)
    wait_until_visible_css_selector(page=page, css_selector=HPL.HOME_MODAL)

    # Assert the submit button is NOT disabled when the modal opens for the second UTub
    expect(page.locator(HPL.BUTTON_MODAL_SUBMIT)).to_be_enabled()
