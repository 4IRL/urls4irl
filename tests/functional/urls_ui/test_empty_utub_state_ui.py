from flask import Flask
import pytest
from playwright.sync_api import Page, expect

from backend import db
from backend.models.utub_members import Utub_Members
from backend.models.utubs import Utubs
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.db_utils import get_utub_this_user_created
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_assert_utils import (
    assert_not_visible_css_selector,
    assert_visible_css_selector,
)
from tests.functional.playwright_login_utils import login_user_and_select_utub_by_utubid
from tests.functional.playwright_utils import (
    select_utub_by_id,
    wait_then_click_element,
    wait_then_get_element,
    wait_then_get_elements,
)
from tests.functional.urls_ui.playwright_utils import create_url

pytestmark = pytest.mark.urls_ui


def test_empty_utub_shows_no_urls_message(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a UTub with zero URLs
    WHEN the user selects that UTub
    THEN the "No URLs yet" message is displayed
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_user_created.id
    )

    assert_visible_css_selector(page=page, css_selector=HPL.SUBHEADER_NO_URLS)

    no_urls_elem = page.locator(HPL.SUBHEADER_NO_URLS).first
    expect(no_urls_elem).to_have_text(UTS.UTUB_NO_URLS)


def test_empty_utub_shows_add_url_button(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a UTub with zero URLs
    WHEN the user selects that UTub
    THEN the "Add URL" button is visible
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_user_created.id
    )

    assert_visible_css_selector(page=page, css_selector=HPL.BUTTON_DECK_URL_CREATE)

    add_url_btn = page.locator(HPL.BUTTON_DECK_URL_CREATE).first
    expect(add_url_btn).to_have_text(UTS.ADD_URL_BUTTON)


def test_add_url_button_opens_create_form(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a UTub with zero URLs showing the empty state
    WHEN the user clicks the "Add URL" button
    THEN the create URL form opens and the empty state is hidden
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_user_created.id
    )

    assert_visible_css_selector(page=page, css_selector=HPL.BUTTON_DECK_URL_CREATE)

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_DECK_URL_CREATE)

    assert_visible_css_selector(page=page, css_selector=HPL.WRAP_URL_CREATE)
    assert_not_visible_css_selector(page=page, css_selector=HPL.SUBHEADER_NO_URLS)


def test_creating_url_hides_empty_state(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a UTub with zero URLs showing the empty state
    WHEN the user creates a new URL
    THEN the empty state message and button are hidden
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_user_created.id
    )

    assert_visible_css_selector(page=page, css_selector=HPL.SUBHEADER_NO_URLS)

    create_url(page=page, url_title="Test URL", url_string="https://example.com")

    wait_then_get_element(page=page, css_selector=HPL.ROWS_URLS)

    assert_not_visible_css_selector(page=page, css_selector=HPL.SUBHEADER_NO_URLS)
    assert_not_visible_css_selector(page=page, css_selector=HPL.BUTTON_DECK_URL_CREATE)


def test_populated_utub_does_not_show_empty_state(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a UTub that has URLs
    WHEN the user selects that UTub
    THEN the empty state message is not displayed
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_user_created.id
    )

    url_rows = wait_then_get_elements(page=page, css_selector=HPL.ROWS_URLS)
    assert len(url_rows) > 0

    assert_not_visible_css_selector(page=page, css_selector=HPL.SUBHEADER_NO_URLS)
    assert_not_visible_css_selector(page=page, css_selector=HPL.BUTTON_DECK_URL_CREATE)


def test_switching_from_populated_to_empty_utub_shows_empty_state(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a user viewing a UTub with URLs
    WHEN the user switches to a UTub with zero URLs
    THEN the empty state message is shown
    """
    app = provide_app
    user_id_for_test = 1

    utub_user_created = get_utub_this_user_created(app, user_id_for_test)

    with app.app_context():
        empty_utub = Utubs(
            name="Empty UTub",
            utub_creator=user_id_for_test,
            utub_description="",
        )
        db.session.add(empty_utub)
        db.session.commit()
        empty_utub_id = empty_utub.id

        member = Utub_Members(
            utub_id=empty_utub_id,
            user_id=user_id_for_test,
            member_role=Utub_Members.member_role.default.arg,
        )
        db.session.add(member)
        db.session.commit()

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_user_created.id
    )

    url_rows = wait_then_get_elements(page=page, css_selector=HPL.ROWS_URLS)
    assert len(url_rows) > 0
    assert_not_visible_css_selector(page=page, css_selector=HPL.SUBHEADER_NO_URLS)

    select_utub_by_id(page=page, utub_id=empty_utub_id)

    assert_visible_css_selector(page=page, css_selector=HPL.SUBHEADER_NO_URLS)

    no_urls_elem = page.locator(HPL.SUBHEADER_NO_URLS).first
    expect(no_urls_elem).to_have_text(UTS.UTUB_NO_URLS)
