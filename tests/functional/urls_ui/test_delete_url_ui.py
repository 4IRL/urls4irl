import random
from typing import Tuple

from flask import Flask
from flask.testing import FlaskCliRunner
import pytest
from playwright.sync_api import Page, expect

from backend.cli.mock_constants import MOCK_URL_STRINGS
from backend.models.users import Users
from backend.models.utub_urls import Utub_Urls
from backend.utils.constants import STRINGS
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from backend.utils.strings.url_strs import DELETE_URL_WARNING
from tests.functional.db_utils import (
    add_mock_urls,
    get_url_in_utub,
    get_utub_this_user_created,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_assert_utils import (
    assert_active_utub,
    assert_elem_with_url_string_exists,
    assert_login_with_username,
    assert_on_429_page,
    assert_tooltip_animates,
    assert_visited_403_on_invalid_csrf_and_reload,
)
from tests.functional.playwright_login_utils import (
    login_user_select_utub_by_id_and_url_by_id,
)
from tests.functional.playwright_utils import (
    add_forced_rate_limit_header,
    dismiss_modal_with_click_out,
    force_next_delete_ajax_failure_no_navigate,
    get_num_url_rows,
    invalidate_csrf_token_on_page,
    wait_for_animation_to_end_check_top_lhs_corner,
    wait_for_element_to_be_removed,
    wait_for_modal_ready,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_hidden,
    wait_until_in_focus,
    wait_until_visible_css_selector,
)
from tests.functional.urls_ui.playwright_login_utils import (
    login_select_utub_select_url_click_delete_get_modal_url,
)

pytestmark = pytest.mark.urls_ui


def test_delete_url_tooltip_animates(
    page: Page,
    create_test_urls,
    runner: Tuple[Flask, FlaskCliRunner],
    provide_app: Flask,
):
    """
    Tests a tooltip showing when user hovers over the edit URL button .

    GIVEN a user has access to a URL
    WHEN the user hover over the edit URL button
    THEN ensure a tooltip is shown appropriately
    """

    _, _ = runner
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    utub_url = get_url_in_utub(app, utub_id=utub_user_created.id)

    login_user_select_utub_by_id_and_url_by_id(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_id=utub_user_created.id,
        utub_url_id=utub_url.id,
    )

    assert_tooltip_animates(
        page=page,
        parent_css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_DELETE}",
        tooltip_parent_class=HPL.BUTTON_URL_DELETE,
        tooltip_text=STRINGS.DELETE_URL_TOOLTIP,
    )


def test_delete_url_submit(page: Page, create_test_urls, provide_app: Flask):
    """
    Tests user's ability to delete a URL

    GIVEN a user, selected UTub and selected URL
    WHEN deleteURL button is selected and confirmation modal confirmed
    THEN ensure the URL is deleted from the UTub
    """
    user_id_for_test = 1

    delete_modal, url_elem_to_delete = (
        login_select_utub_select_url_click_delete_get_modal_url(
            page=page,
            app=provide_app,
            user_id=user_id_for_test,
            utub_name=UTS.TEST_UTUB_NAME_1,
            url_string=UTS.TEST_URL_STRING_CREATE,
        )
    )

    css_selector = f'{HPL.URL_STRING_READ}[href="{UTS.TEST_URL_STRING_CREATE}"]'
    expect(page.locator(css_selector).first).to_be_attached()

    init_num_url_rows = get_num_url_rows(page=page)

    confirmation_modal_body_text = delete_modal.inner_text()

    # Assert warning modal appears with appropriate text
    assert confirmation_modal_body_text == DELETE_URL_WARNING

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)

    # Assert submit button is disabled immediately after click to prevent double-submit
    modal_submit_btn = page.locator(HPL.BUTTON_MODAL_SUBMIT).first
    expect(modal_submit_btn).to_be_disabled()

    wait_until_hidden(page=page, css_selector=HPL.HOME_MODAL)

    # Wait for animation to complete
    wait_for_element_to_be_removed(page=page, locator=url_elem_to_delete)

    # Assert URL no longer exists in UTub
    expect(page.locator(css_selector)).to_have_count(0)
    assert init_num_url_rows - 1 == get_num_url_rows(page=page)


def test_delete_url_rate_limits(page: Page, create_test_urls, provide_app: Flask):
    """
    Tests user's ability to delete a URL when they are rate limited

    GIVEN a user, selected UTub and selected URL and they are rate limited
    WHEN deleteURL button is selected and confirmation modal confirmed
    THEN ensure the 429 error page is shown
    """
    user_id_for_test = 1

    delete_modal, _ = login_select_utub_select_url_click_delete_get_modal_url(
        page=page,
        app=provide_app,
        user_id=user_id_for_test,
        utub_name=UTS.TEST_UTUB_NAME_1,
        url_string=UTS.TEST_URL_STRING_CREATE,
    )

    css_selector = f'{HPL.URL_STRING_READ}[href="{UTS.TEST_URL_STRING_CREATE}"]'
    expect(page.locator(css_selector).first).to_be_attached()

    confirmation_modal_body_text = delete_modal.inner_text()

    # Assert warning modal appears with appropriate text
    assert confirmation_modal_body_text == DELETE_URL_WARNING

    add_forced_rate_limit_header(page=page)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)
    assert_on_429_page(page=page)


def test_delete_url_cancel_click_cancel_btn(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    Tests user's ability to delete a URL

    GIVEN a user, selected UTub and selected URL
    WHEN deleteURL button is selected and confirmation modal is cancelled by clicking the cancel btn
    THEN ensure the URL is not deleted from the UTub, and the modal is hidden
    """
    user_id_for_test = 1

    delete_modal, url_elem_to_delete = (
        login_select_utub_select_url_click_delete_get_modal_url(
            page=page,
            app=provide_app,
            user_id=user_id_for_test,
            utub_name=UTS.TEST_UTUB_NAME_1,
            url_string=UTS.TEST_URL_STRING_CREATE,
        )
    )

    init_num_url_rows = get_num_url_rows(page=page)

    confirmation_modal_body_text = delete_modal.inner_text()

    # Assert warning modal appears with appropriate text
    assert confirmation_modal_body_text == DELETE_URL_WARNING

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_DISMISS)
    wait_until_hidden(page=page, css_selector=HPL.BUTTON_MODAL_DISMISS)

    # Assert URL still exists in UTub
    assert_elem_with_url_string_exists(page=page, url_string=UTS.TEST_URL_STRING_CREATE)
    assert init_num_url_rows == get_num_url_rows(page=page)
    expect(url_elem_to_delete).to_be_visible()


def test_delete_url_cancel_click_x_btn(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    Tests user's ability to delete a URL

    GIVEN a user, selected UTub and selected URL
    WHEN deleteURL button is selected and confirmation modal is cancelled by clicking the x btn
    THEN ensure the URL is not deleted from the UTub, and the modal is hidden
    """
    user_id_for_test = 1

    delete_modal, url_elem_to_delete = (
        login_select_utub_select_url_click_delete_get_modal_url(
            page=page,
            app=provide_app,
            user_id=user_id_for_test,
            utub_name=UTS.TEST_UTUB_NAME_1,
            url_string=UTS.TEST_URL_STRING_CREATE,
        )
    )

    init_num_url_rows = get_num_url_rows(page=page)

    confirmation_modal_body_text = delete_modal.inner_text()

    # Assert warning modal appears with appropriate text
    assert confirmation_modal_body_text == DELETE_URL_WARNING

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_X_CLOSE)
    wait_until_hidden(page=page, css_selector=HPL.BUTTON_X_CLOSE)

    # Assert URL still exists in UTub
    assert_elem_with_url_string_exists(page=page, url_string=UTS.TEST_URL_STRING_CREATE)
    assert init_num_url_rows == get_num_url_rows(page=page)
    expect(url_elem_to_delete).to_be_visible()


def test_delete_url_cancel_press_esc_key(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    Tests user's ability to delete a URL

    GIVEN a user, selected UTub and selected URL
    WHEN deleteURL button is selected and confirmation modal is cancelled by pressing esc key
    THEN ensure the URL is not deleted from the UTub, and the modal is hidden
    """
    user_id_for_test = 1

    delete_modal, url_elem_to_delete = (
        login_select_utub_select_url_click_delete_get_modal_url(
            page=page,
            app=provide_app,
            user_id=user_id_for_test,
            utub_name=UTS.TEST_UTUB_NAME_1,
            url_string=UTS.TEST_URL_STRING_CREATE,
        )
    )

    init_num_url_rows = get_num_url_rows(page=page)

    confirmation_modal_body_text = delete_modal.inner_text()

    # Assert warning modal appears with appropriate text
    assert confirmation_modal_body_text == DELETE_URL_WARNING

    wait_until_in_focus(page=page, css_selector=HPL.HOME_MODAL)
    page.keyboard.press("Escape")
    wait_until_hidden(page=page, css_selector=HPL.HOME_MODAL)

    # Assert URL still exists in UTub
    assert_elem_with_url_string_exists(page=page, url_string=UTS.TEST_URL_STRING_CREATE)
    assert init_num_url_rows == get_num_url_rows(page=page)
    expect(url_elem_to_delete).to_be_visible()


def test_delete_url_cancel_click_outside_modal(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    Tests user's ability to delete a URL

    GIVEN a user, selected UTub and selected URL
    WHEN deleteURL button is selected and confirmation modal is cancelled by clicking outside the modal
    THEN ensure the URL is not deleted from the UTub, and the modal is hidden
    """
    user_id_for_test = 1

    delete_modal, url_elem_to_delete = (
        login_select_utub_select_url_click_delete_get_modal_url(
            page=page,
            app=provide_app,
            user_id=user_id_for_test,
            utub_name=UTS.TEST_UTUB_NAME_1,
            url_string=UTS.TEST_URL_STRING_CREATE,
        )
    )

    init_num_url_rows = get_num_url_rows(page=page)

    confirmation_modal_body_text = delete_modal.inner_text()

    # Assert warning modal appears with appropriate text
    assert confirmation_modal_body_text == DELETE_URL_WARNING

    wait_for_modal_ready(page=page, modal_selector=HPL.HOME_MODAL)
    dismiss_modal_with_click_out(page=page, modal_selector=HPL.HOME_MODAL)
    wait_until_hidden(page=page, css_selector=HPL.HOME_MODAL)

    # Assert URL still exists in UTub
    assert_elem_with_url_string_exists(page=page, url_string=UTS.TEST_URL_STRING_CREATE)
    assert init_num_url_rows == get_num_url_rows(page=page)
    expect(url_elem_to_delete).to_be_visible()


def test_delete_last_url(
    page: Page,
    runner: Tuple[Flask, FlaskCliRunner],
    create_test_utubs,
    provide_app: Flask,
):
    """
    Confirms site UI prompts user to create a URL when last URL is deleted.

    GIVEN a user has URLs
    WHEN all URLs are deleted
    THEN ensure the empty UTub prompts user to create a URL.
    """
    _, cli_runner = runner

    random_url_to_add_as_last = random.sample(MOCK_URL_STRINGS, 1)[0]

    add_mock_urls(
        cli_runner,
        [
            random_url_to_add_as_last,
        ],
    )

    user_id_for_test = 1

    _, url_elem_to_delete = login_select_utub_select_url_click_delete_get_modal_url(
        page=page,
        app=provide_app,
        user_id=user_id_for_test,
        utub_name=UTS.TEST_UTUB_NAME_1,
        url_string=random_url_to_add_as_last,
    )

    css_selector = f'{HPL.URL_STRING_READ}[href="{random_url_to_add_as_last}"]'
    expect(page.locator(css_selector).first).to_be_attached()

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)
    wait_until_hidden(page=page, css_selector=HPL.HOME_MODAL)
    wait_for_element_to_be_removed(page=page, locator=url_elem_to_delete)
    expect(page.locator(css_selector)).to_have_count(0)

    no_url_subheader = wait_then_get_element(
        page=page, css_selector=HPL.SUBHEADER_NO_URLS
    )
    expect(no_url_subheader).to_have_text(UTS.UTUB_NO_URLS)


def test_delete_url_invalid_csrf_token(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    Tests a user's ability to attempt to delete a URL with an invalid CSRF token

    GIVEN a user attempting to delete a URL in a UTub
    WHEN the deleteURL form is sent with an invalid CSRF token
    THEN ensure U4I responds with a proper error message
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    with app.app_context():
        user: Users = Users.query.get(user_id_for_test)
        url_to_delete: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_user_created.id
        ).first()
        url_string_to_delete = url_to_delete.standalone_url.url_string

    login_select_utub_select_url_click_delete_get_modal_url(
        page=page,
        app=provide_app,
        user_id=user_id_for_test,
        utub_name=UTS.TEST_UTUB_NAME_1,
        url_string=url_string_to_delete,
    )

    invalidate_csrf_token_on_page(page=page)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)

    assert_visited_403_on_invalid_csrf_and_reload(page=page)

    # Page reloads after user clicks button in CSRF 403 error page
    wait_until_hidden(page=page, css_selector=HPL.HOME_MODAL)
    assert_login_with_username(page=page, username=user.username)

    # Reload will bring user back to the UTub they were in before
    assert_active_utub(page=page, utub_name=utub_user_created.name)


def test_delete_url_submit_button_reenables_on_server_error(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    Tests that the submit button re-enables after a server error so the user can retry.

    GIVEN a user with a selected URL and the delete confirmation modal open
    WHEN the DELETE request fails with a 500 server error
    THEN ensure the #modalSubmit button is re-enabled (not disabled)
    """
    user_id_for_test = 1

    delete_modal, _ = login_select_utub_select_url_click_delete_get_modal_url(
        page=page,
        app=provide_app,
        user_id=user_id_for_test,
        utub_name=UTS.TEST_UTUB_NAME_1,
        url_string=UTS.TEST_URL_STRING_CREATE,
    )

    confirmation_modal_body_text = delete_modal.inner_text()
    assert confirmation_modal_body_text == DELETE_URL_WARNING

    # Force the next DELETE ajax call to fail (with early return to prevent navigation)
    force_next_delete_ajax_failure_no_navigate(page=page)

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)

    # Poll until the async failure handler re-enables the submit button
    expect(page.locator(HPL.BUTTON_MODAL_SUBMIT)).to_be_enabled()


def test_delete_url_submit_button_enabled_on_second_modal_open(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    Tests that the submit button is enabled when opening the delete modal for a
    second URL after successfully deleting the first.

    GIVEN a user with a selected UTub containing at least 2 URLs
    WHEN they successfully delete URL 1 and then open the delete modal for URL 2
    THEN ensure the #modalSubmit button is NOT disabled
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)

    with app.app_context():
        utub_urls: list[Utub_Urls] = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_user_created.id
        ).all()
        first_utub_url_id = utub_urls[0].id
        first_utub_url_string = utub_urls[0].standalone_url.url_string
        second_utub_url_id = utub_urls[1].id

    login_select_utub_select_url_click_delete_get_modal_url(
        page=page,
        app=app,
        user_id=user_id_for_test,
        utub_name=utub_user_created.name,
        url_string=first_utub_url_string,
    )

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)

    # Wait for the first URL row to be removed from the DOM
    first_url_row_selector = f'{HPL.ROWS_URLS}[utuburlid="{first_utub_url_id}"]'
    first_url_row_elem = page.locator(first_url_row_selector).first
    wait_until_hidden(page=page, css_selector=HPL.HOME_MODAL)
    wait_for_element_to_be_removed(page=page, locator=first_url_row_elem)

    # Select the second URL and open its delete modal
    second_url_row_selector = f'{HPL.ROWS_URLS}[utuburlid="{second_utub_url_id}"]'
    wait_then_click_element(page=page, css_selector=second_url_row_selector)
    wait_for_animation_to_end_check_top_lhs_corner(
        page=page, css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_ACCESS}"
    )
    wait_then_click_element(
        page=page, css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_DELETE}"
    )
    wait_until_visible_css_selector(page=page, css_selector=HPL.HOME_MODAL)

    # Assert the submit button is NOT disabled when the modal opens for the second URL
    expect(page.locator(HPL.BUTTON_MODAL_SUBMIT)).to_be_enabled()
