from flask import Flask
import pytest
from playwright.sync_api import Page, expect

from tests.functional.locators import HomePageLocators as HPL
from backend.models.users import Users
from backend.models.utub_members import Member_Role, Utub_Members
from backend.utils.strings.user_strs import MEMBER_DELETE_WARNING
from tests.functional.db_utils import (
    get_other_member_in_utub,
    get_utub_this_user_created,
    get_utub_this_user_did_not_create,
)
from tests.functional.members_ui.playwright_utils import (
    delete_member_active_utub,
    get_all_member_usernames,
)
from tests.functional.playwright_assert_utils import (
    assert_active_utub,
    assert_login_with_username,
    assert_on_429_page,
    assert_visited_403_on_invalid_csrf_and_reload,
)
from tests.functional.playwright_login_utils import login_user_and_select_utub_by_name
from tests.functional.playwright_utils import (
    add_forced_rate_limit_header,
    dismiss_modal_with_click_out,
    force_next_delete_ajax_failure_no_navigate,
    invalidate_csrf_token_on_page,
    wait_for_modal_ready,
    wait_for_selector_to_be_removed,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_css_property,
    wait_until_hidden,
    wait_until_in_focus,
    wait_until_visible_css_selector,
)

pytestmark = pytest.mark.members_ui


def test_open_delete_member_modal(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN a user owns a UTub with members
    WHEN they click on the delete member button after hovering over the member
    THEN ensure the modal to confirm deleting a member is shown
    """
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )
    other_member = get_other_member_in_utub(app, utub_user_created.id, user_id)

    member_name = other_member.username
    delete_member_active_utub(page=page, member_name=member_name)

    warning_modal = wait_then_get_element(page=page, css_selector=HPL.HOME_MODAL)
    expect(warning_modal).to_be_visible()

    warning_modal_body = page.locator(HPL.BODY_MODAL)
    expect(warning_modal_body).to_have_text(MEMBER_DELETE_WARNING)


def test_dismiss_delete_member_modal_btn(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN a user owns a UTub with members
    WHEN they open the delete member modal, but dismiss it by clicking the cancel button
    THEN ensure the modal is then dismissed
    """
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )
    other_member = get_other_member_in_utub(app, utub_user_created.id, user_id)

    member_name = other_member.username
    delete_member_active_utub(page=page, member_name=member_name)

    # Gate on the show-transition being fully settled (_isTransitioning === false)
    # before clicking dismiss. Clicking while Bootstrap's fade-in is still running
    # causes the modal("hide") to be dropped as an overlapping transition, leaving
    # the modal visible and racing wait_until_hidden.
    wait_for_modal_ready(page=page, modal_selector=HPL.HOME_MODAL)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_DISMISS)
    wait_until_hidden(page=page, css_selector=HPL.HOME_MODAL)


def test_dismiss_delete_member_modal_x(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN a user owns a UTub with members
    WHEN they open the delete member modal, but dismiss it by clicking the X button on the modal
    THEN ensure the modal is then dismissed
    """
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )
    other_member = get_other_member_in_utub(app, utub_user_created.id, user_id)

    member_name = other_member.username
    delete_member_active_utub(page=page, member_name=member_name)

    wait_for_modal_ready(page=page, modal_selector=HPL.HOME_MODAL)
    x_btn = page.locator(HPL.HOME_MODAL).locator(HPL.BUTTON_X_CLOSE).first
    expect(x_btn).to_be_visible()
    x_btn.click()
    wait_until_hidden(page=page, css_selector=HPL.HOME_MODAL)


def test_dismiss_delete_member_modal_click_outside_modal(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN a user owns a UTub with members
    WHEN they open the delete member modal, but dismiss it by clicking outside the modal
    THEN ensure the modal is then dismissed
    """
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )
    other_member = get_other_member_in_utub(app, utub_user_created.id, user_id)

    member_name = other_member.username
    delete_member_active_utub(page=page, member_name=member_name)

    wait_until_visible_css_selector(page=page, css_selector=HPL.HOME_MODAL)
    wait_for_modal_ready(page=page, modal_selector=HPL.HOME_MODAL)
    dismiss_modal_with_click_out(page=page, modal_selector=HPL.HOME_MODAL)
    wait_until_hidden(page=page, css_selector=HPL.HOME_MODAL)


def test_dismiss_delete_member_modal_key(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN a user owns a UTub with members
    WHEN they open the delete member modal, but dismiss it by pressing the escape key
    THEN ensure the modal is then dismissed
    """
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )
    other_member = get_other_member_in_utub(app, utub_user_created.id, user_id)

    member_name = other_member.username
    delete_member_active_utub(page=page, member_name=member_name)

    wait_until_visible_css_selector(page=page, css_selector=HPL.HOME_MODAL)
    wait_until_in_focus(page=page, css_selector=HPL.HOME_MODAL)
    page.keyboard.press("Escape")
    wait_until_hidden(page=page, css_selector=HPL.HOME_MODAL)


def test_delete_member_btn(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN a user owns a UTub with members
    WHEN they submit the delete UTub Member modal
    THEN ensure the member is removed from the UTub
    """
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )
    other_member = get_other_member_in_utub(app, utub_user_created.id, user_id)

    member_name = other_member.username
    delete_member_active_utub(page=page, member_name=other_member.username)

    # Gate on the modal being fully shown (fade-in transition settled) before clicking
    # submit. Clicking while Bootstrap's show-transition is still running causes the
    # subsequent modal("hide") issued by removeMemberSuccess to be dropped as an
    # overlapping transition, which leaves the modal visible and races wait_until_hidden.
    wait_until_css_property(
        page=page,
        css_selector=HPL.HOME_MODAL,
        css_property="opacity",
        expected_value="1",
    )

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)

    # Assert submit button is disabled immediately after click to prevent double-submit
    expect(page.locator(HPL.BUTTON_MODAL_SUBMIT)).to_be_disabled()

    # Wait for DELETE request and member removal
    member_selector = f'{HPL.BADGES_MEMBERS}[memberid="{other_member.id}"]'
    wait_until_hidden(page=page, css_selector=HPL.HOME_MODAL)
    wait_for_selector_to_be_removed(page=page, css_selector=member_selector)

    member_usernames = get_all_member_usernames(page=page)
    assert member_name not in member_usernames


def test_delete_member_rate_limits(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN a user owns a UTub with members but they are rate limited
    WHEN they submit the delete UTub Member modal
    THEN ensure the 429 error page is shown
    """
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )
    other_member = get_other_member_in_utub(app, utub_user_created.id, user_id)

    delete_member_active_utub(page=page, member_name=other_member.username)

    add_forced_rate_limit_header(page=page)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)
    assert_on_429_page(page=page)


def test_open_delete_member_modal_fails_as_member(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN a user who is a member of a UTub
    WHEN they hover over another member in the UTub
    THEN ensure delete member button is not shown to the user
    """
    app = provide_app

    user_id = 1
    utub_user_member_of = get_utub_this_user_did_not_create(app, user_id)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_member_of.name
    )

    with app.app_context():
        other_member: Utub_Members = Utub_Members.query.filter(
            Utub_Members.user_id != user_id,
            Utub_Members.utub_id == utub_user_member_of.id,
            Utub_Members.member_role == Member_Role.MEMBER,
        ).first()
        other_user = other_member.to_user

    member_selector = f'{HPL.BADGES_MEMBERS}[memberid="{other_user.id}"]'
    other_member_element = wait_then_get_element(
        page=page, css_selector=member_selector
    )
    other_member_element.hover()
    assert other_member_element.locator(HPL.BUTTON_MEMBER_DELETE).count() == 0


def test_delete_member_invalid_csrf_token(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN a user owns a UTub with members
    WHEN they submit the delete UTub Member modal with an invalid CSRF token
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
    other_member = get_other_member_in_utub(app, utub_user_created.id, user_id)

    member_name = other_member.username
    delete_member_active_utub(page=page, member_name=member_name)

    invalidate_csrf_token_on_page(page=page)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)
    assert_visited_403_on_invalid_csrf_and_reload(page=page)

    assert_login_with_username(page=page, username=username)
    assert_active_utub(page=page, utub_name=utub_user_created.name)
    wait_until_hidden(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)


def test_delete_member_submit_button_reenables_on_server_error(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    Tests that the submit button re-enables after a server error so the user can retry.

    GIVEN a user owns a UTub with members and the delete member confirmation modal is open
    WHEN the DELETE request fails with a 500 server error
    THEN ensure the #modalSubmit button is re-enabled (not disabled)
    """
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )
    other_member = get_other_member_in_utub(app, utub_user_created.id, user_id)

    delete_member_active_utub(page=page, member_name=other_member.username)

    force_next_delete_ajax_failure_no_navigate(page=page)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)

    expect(page.locator(HPL.BUTTON_MODAL_SUBMIT)).to_be_enabled()


def test_delete_member_submit_button_enabled_on_second_modal_open(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    Tests that the submit button is enabled when opening the delete modal for a
    second member after successfully deleting the first.

    GIVEN a user owns a UTub with at least 2 other members
    WHEN they successfully delete member 1 and then open the delete modal for member 2
    THEN ensure the #modalSubmit button is NOT disabled
    """
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    with app.app_context():
        other_members: list[Utub_Members] = Utub_Members.query.filter(
            Utub_Members.user_id != user_id,
            Utub_Members.utub_id == utub_user_created.id,
        ).all()
        first_member_user = other_members[0].to_user
        second_member_user = other_members[1].to_user

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    # Delete the first member
    delete_member_active_utub(page=page, member_name=first_member_user.username)

    # Gate on the modal being fully shown (fade-in transition settled) before clicking
    # submit. Clicking while Bootstrap's show-transition is still running causes the
    # subsequent modal("hide") issued by removeMemberSuccess to be dropped as an
    # overlapping transition, which leaves the modal visible and races wait_until_hidden.
    wait_until_css_property(
        page=page,
        css_selector=HPL.HOME_MODAL,
        css_property="opacity",
        expected_value="1",
    )
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)

    # Wait for the first member's badge to be removed from the DOM
    first_member_selector = f'{HPL.BADGES_MEMBERS}[memberid="{first_member_user.id}"]'
    wait_until_hidden(page=page, css_selector=HPL.HOME_MODAL)
    wait_for_selector_to_be_removed(page=page, css_selector=first_member_selector)

    # Open the delete modal for the second member
    delete_member_active_utub(page=page, member_name=second_member_user.username)

    # Gate on the modal being fully rendered before asserting on its submit button,
    # so the button-enabled check is not raced against modal render under parallel load
    wait_until_visible_css_selector(page=page, css_selector=HPL.HOME_MODAL)

    # Assert the submit button is NOT disabled when the modal opens for the second member
    expect(page.locator(HPL.BUTTON_MODAL_SUBMIT)).to_be_enabled()
