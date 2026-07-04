from flask import Flask
import pytest
from playwright.sync_api import Page, expect

from backend.models.utub_members import Member_Role, Utub_Members
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_assert_utils import (
    assert_on_429_page,
    assert_url_coloring_is_correct,
    assert_utub_selected,
)
from tests.functional.db_utils import (
    get_utub_this_user_created,
    get_utub_this_user_did_not_create,
)
from tests.functional.login_utils import create_user_session_and_provide_session_id
from tests.functional.playwright_login_utils import (
    login_user_and_select_utub_by_utubid,
)
from tests.functional.playwright_utils import (
    add_forced_rate_limit_header,
    current_base_url,
    login_user_to_home_page,
    login_user_with_cookie_from_session,
    select_utub_by_id,
    wait_for_element_presence,
    wait_then_click_element,
    wait_until_visible_css_selector,
)
from tests.functional.utubs_ui.playwright_assert_utils import (
    assert_in_created_utub,
    assert_in_member_utub,
)

pytestmark = pytest.mark.utubs_ui


def test_select_member_utub_from_home_page(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN a fresh load of the U4i Home page, where user is in multiple UTubs
    WHEN user clicks one of the UTubs they did not create
    THEN ensure the all appropriate elements are visible and ready
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_did_not_create = get_utub_this_user_did_not_create(app, user_id_for_test)

    login_user_to_home_page(app=app, page=page, user_id=user_id_for_test)
    select_utub_by_id(page=page, utub_id=utub_user_did_not_create.id)
    assert_utub_selected(page=page, app=app, utub_id=utub_user_did_not_create.id)
    assert_url_coloring_is_correct(page=page)
    assert_in_member_utub(page=page)


def test_select_created_utub_from_home_page(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN a fresh load of the U4i Home page, where user is in multiple UTubs
    WHEN user clicks one of the UTubs they did create
    THEN ensure the all appropriate elements are visible and ready
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_did_create = get_utub_this_user_created(app, user_id_for_test)

    login_user_to_home_page(app=app, page=page, user_id=user_id_for_test)
    select_utub_by_id(page=page, utub_id=utub_user_did_create.id)
    assert_utub_selected(page=page, app=app, utub_id=utub_user_did_create.id)
    assert_url_coloring_is_correct(page=page)
    assert_in_created_utub(page=page)


def test_select_member_utub_from_created_utub(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN a fresh load of the U4i Home page, where user is in multiple UTubs, and they select a UTub they created
    WHEN user clicks one of the UTubs they did not create
    THEN ensure the all appropriate elements are visible and ready
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_did_create = get_utub_this_user_created(app, user_id_for_test)
    utub_user_did_not_create = get_utub_this_user_did_not_create(app, user_id_for_test)

    login_user_to_home_page(app=app, page=page, user_id=user_id_for_test)
    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_user_did_create.id
    )
    assert_utub_selected(page=page, app=app, utub_id=utub_user_did_create.id)

    select_utub_by_id(page=page, utub_id=utub_user_did_not_create.id)
    assert_utub_selected(page=page, app=app, utub_id=utub_user_did_not_create.id)
    assert_url_coloring_is_correct(page=page)
    assert_in_member_utub(page=page)


def test_select_created_utub_from_member_utub(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN a fresh load of the U4i Home page, where user is in multiple UTubs and they select a UTub they did not create
    WHEN user clicks one of the UTubs they did create
    THEN ensure the all appropriate elements are visible and ready
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_did_not_create = get_utub_this_user_did_not_create(app, user_id_for_test)
    utub_user_did_create = get_utub_this_user_created(app, user_id_for_test)

    login_user_and_select_utub_by_utubid(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_id=utub_user_did_not_create.id,
    )
    assert_utub_selected(page=page, app=app, utub_id=utub_user_did_not_create.id)

    select_utub_by_id(page=page, utub_id=utub_user_did_create.id)
    assert_utub_selected(page=page, app=app, utub_id=utub_user_did_create.id)
    assert_url_coloring_is_correct(page=page)
    assert_in_created_utub(page=page)


def test_select_utub_rate_limits(page: Page, create_test_tags, provide_app: Flask):
    """
    GIVEN a fresh load of the U4i Home page, where user is in multiple UTubs, but they are rate limited
    WHEN user clicks one of the UTubs
    THEN ensure the 429 error page is shown
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_did_not_create = get_utub_this_user_did_not_create(app, user_id_for_test)

    login_user_to_home_page(app=app, page=page, user_id=user_id_for_test)
    utub_selector = f"{HPL.SELECTORS_UTUB}[utubid='{utub_user_did_not_create.id}']"

    utub_selector_elem = wait_for_element_presence(
        page=page, css_selector=utub_selector
    )
    assert utub_selector_elem is not None

    add_forced_rate_limit_header(page=page)
    wait_then_click_element(page=page, css_selector=utub_selector)

    assert_on_429_page(page=page)


def test_utub_member_icon(page: Page, create_test_tags, provide_app: Flask):
    """
    GIVEN a set of UTubs with URLs, member, and tags within that UTub, and the user has no session cookie
    WHEN the user logs in and sees their UTubs
    THEN verify that the UTubs contain the correct member icon
    """
    app = provide_app
    user_id = 1

    with app.app_context():
        members_of: list[Utub_Members] = Utub_Members.query.filter(
            Utub_Members.user_id == user_id
        ).all()

    session_id = create_user_session_and_provide_session_id(app, user_id)
    base_url = current_base_url(page=page)
    login_user_with_cookie_from_session(
        context=page.context, session_id=session_id, base_url=base_url
    )
    page.goto(f"{base_url}/home")

    for utub_member in members_of:
        utub_selector = f"{HPL.SELECTORS_UTUB}[utubid='{utub_member.utub_id}'] "

        if utub_member.member_role == Member_Role.CREATOR.value:
            utub_selector += HPL.CREATOR_ICON

        elif utub_member.member_role == Member_Role.CO_CREATOR.value:
            utub_selector += HPL.CO_CREATOR_ICON

        elif utub_member.member_role == Member_Role.MEMBER.value:
            utub_selector += HPL.MEMBER_ICON

        wait_until_visible_css_selector(page=page, css_selector=utub_selector)
        expect(page.locator(utub_selector).first).to_be_visible()
