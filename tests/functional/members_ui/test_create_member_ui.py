from flask import Flask
import pytest
from playwright.sync_api import Page, expect

from backend.cli.mock_constants import USERNAME_BASE
from backend.models.users import Users
from backend.models.utub_members import Utub_Members
from backend.utils.strings.user_strs import MEMBER_FAILURE, USER_FAILURE
from tests.functional.db_utils import (
    get_utub_this_user_created,
    get_utub_this_user_did_not_create,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.members_ui.playwright_utils import (
    create_member_active_utub,
    get_all_member_usernames,
)
from tests.functional.playwright_assert_utils import (
    assert_login_with_username,
    assert_on_429_page,
    assert_visited_403_on_invalid_csrf_and_reload,
)
from tests.functional.playwright_login_utils import login_user_and_select_utub_by_name
from tests.functional.playwright_utils import (
    add_forced_rate_limit_header,
    invalidate_csrf_token_on_page,
    select_utub_by_name,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_hidden,
    wait_until_in_focus,
    wait_until_visible_css_selector,
)

pytestmark = pytest.mark.members_ui


def test_open_input_create_member(page: Page, create_test_utubs, provide_app: Flask):
    """
    Tests a UTub owner's ability to open the create member input field.

    GIVEN a user is the UTub owner with the UTub selected
    WHEN the user clicks the createMember plus button
    THEN ensure the createMember form is opened.
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MEMBER_CREATE)
    create_member_input = wait_then_get_element(
        page=page, css_selector=HPL.INPUT_MEMBER_CREATE
    )
    expect(create_member_input).to_be_visible()


def test_cancel_input_create_member_x(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    Tests a UTub owner's ability to close the create member input field.

    GIVEN a user is the UTub owner with the UTub selected
    WHEN the user clicks the createMember plus button, then clicks the x button
    THEN ensure the createMember form is not shown.
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MEMBER_CREATE)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MEMBER_CANCEL_CREATE)
    wait_until_hidden(page=page, css_selector=HPL.INPUT_MEMBER_CREATE)


def test_cancel_input_create_member_key(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    Tests a UTub owner's ability to close the create member input field.

    GIVEN a user is the UTub owner with the UTub selected
    WHEN the user clicks the createMember plus button, then presses the esc key
    THEN ensure the createMember form is not shown.
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MEMBER_CREATE)
    wait_until_in_focus(page=page, css_selector=HPL.INPUT_MEMBER_CREATE)
    page.keyboard.press("Escape")
    wait_until_hidden(page=page, css_selector=HPL.INPUT_MEMBER_CREATE)


def test_create_member_btn(page: Page, create_test_utubs, provide_app: Flask):
    """
    Tests a UTub owner's ability to create a member by adding another U4I user to the UTub.

    GIVEN a user is the UTub owner
    WHEN the createMember form is populated and submitted
    THEN ensure the new member is successfully added to the UTub.
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    new_member_username = USERNAME_BASE + "2"
    create_member_active_utub(page=page, member_name=new_member_username)

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MEMBER_SUBMIT_CREATE)
    wait_until_hidden(page=page, css_selector=HPL.BUTTON_MEMBER_SUBMIT_CREATE)

    member_usernames = get_all_member_usernames(page=page)
    assert new_member_username in member_usernames


def test_create_member_key(page: Page, create_test_utubs, provide_app: Flask):
    """
    Tests a UTub owner's ability to create a member by adding another U4I user to the UTub.

    GIVEN a user is the UTub owner
    WHEN the createMember form is populated and submitted via the Enter key
    THEN ensure the new member is successfully added to the UTub.
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    new_member_username = USERNAME_BASE + "2"
    create_member_active_utub(page=page, member_name=new_member_username)

    page.locator(HPL.INPUT_MEMBER_CREATE).press("Enter")
    wait_until_hidden(page=page, css_selector=HPL.BUTTON_MEMBER_SUBMIT_CREATE)

    member_usernames = get_all_member_usernames(page=page)
    assert new_member_username in member_usernames


def test_create_member_rate_limits(page: Page, create_test_utubs, provide_app: Flask):
    """
    Tests a UTub owner's ability to create a member by adding another U4I user to the UTub, but
    they are rate limited

    GIVEN a user is the UTub owner but they are rate limited
    WHEN the createMember form is populated and submitted
    THEN ensure the 429 error page is shown
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    new_member_username = USERNAME_BASE + "2"
    create_member_active_utub(page=page, member_name=new_member_username)

    add_forced_rate_limit_header(page=page)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MEMBER_SUBMIT_CREATE)
    assert_on_429_page(page=page)


def test_create_member_denied(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    Tests a UTub member's inability to create a member in the UTub.

    GIVEN a user is a UTub member
    THEN the user does not have access to the createMember plus button
    """
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    utub_user_member_of = get_utub_this_user_did_not_create(app, user_id)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    select_utub_by_name(page=page, utub_name=utub_user_member_of.name)
    wait_until_hidden(page=page, css_selector=HPL.BUTTON_MEMBER_CREATE)


def test_create_member_username_not_exist(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a user is the UTub owner
    WHEN the createMember form is populated and submitted with a username that does not exist
    THEN ensure U4I responds appropriately with error message.
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    new_member_username = USERNAME_BASE + "999A"
    create_member_active_utub(page=page, member_name=new_member_username)

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MEMBER_SUBMIT_CREATE)
    wait_until_visible_css_selector(
        page=page, css_selector=HPL.INPUT_MEMBER_CREATE_ERROR
    )
    expect(page.locator(HPL.INPUT_MEMBER_CREATE_ERROR)).to_have_text(
        USER_FAILURE.USER_NOT_EXIST
    )


def test_create_member_username_field_empty(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a user is the UTub owner
    WHEN the createMember form is submitted with an empty field
    THEN ensure U4I responds appropriately with error message.
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    create_member_active_utub(page=page, member_name="")

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MEMBER_SUBMIT_CREATE)
    wait_until_visible_css_selector(
        page=page, css_selector=HPL.INPUT_MEMBER_CREATE_ERROR
    )
    expect(page.locator(HPL.INPUT_MEMBER_CREATE_ERROR)).to_have_text(
        "Must be at least 3 characters."
    )


def test_create_member_duplicate_member(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a user is the UTub owner
    WHEN the createMember form is submitted with a user that is already a member
    THEN ensure U4I responds appropriately with error message.
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )
    with app.app_context():
        utub_member: Utub_Members = Utub_Members.query.filter(
            Utub_Members.user_id != user_id,
            Utub_Members.utub_id == utub_user_created.id,
        ).first()
        utub_member_user: Users = utub_member.to_user
        utub_member_username = utub_member_user.username

    create_member_active_utub(page=page, member_name=utub_member_username)

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MEMBER_SUBMIT_CREATE)
    wait_until_visible_css_selector(
        page=page, css_selector=HPL.INPUT_MEMBER_CREATE_ERROR
    )
    expect(page.locator(HPL.INPUT_MEMBER_CREATE_ERROR)).to_have_text(
        MEMBER_FAILURE.MEMBER_ALREADY_IN_UTUB
    )


def test_create_member_form_resets_on_close(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a user is the UTub owner
    WHEN the createMember form is populated and submitted with a username that does not exist, an error is shown, and the user closes the form
    THEN ensure the form is reset without errors
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    new_member_username = USERNAME_BASE + "999A"
    create_member_active_utub(page=page, member_name=new_member_username)

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MEMBER_SUBMIT_CREATE)
    wait_until_visible_css_selector(
        page=page, css_selector=HPL.INPUT_MEMBER_CREATE_ERROR
    )

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MEMBER_CANCEL_CREATE)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MEMBER_CREATE)

    member_error_locator = page.locator(HPL.INPUT_MEMBER_CREATE_ERROR)
    expect(member_error_locator).to_be_hidden()


def test_create_member_invalid_csrf_token(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    Tests a UTub owner's ability to attempt to create a member with an invalid CSRF token.

    GIVEN a user is the UTub owner
    WHEN the createMember form is populated and submitted with an invalid CSRF token
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

    new_member_username = USERNAME_BASE + "2"
    create_member_active_utub(page=page, member_name=new_member_username)
    invalidate_csrf_token_on_page(page=page)

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MEMBER_SUBMIT_CREATE)
    assert_visited_403_on_invalid_csrf_and_reload(page=page)

    wait_until_hidden(page=page, css_selector=HPL.INPUT_MEMBER_CREATE)
    assert_login_with_username(page=page, username=username)
