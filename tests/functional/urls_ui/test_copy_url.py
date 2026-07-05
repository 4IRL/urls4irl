from flask import Flask
import pytest
from playwright.sync_api import Page

from backend.models.urls import Urls
from backend.utils.constants import STRINGS
from tests.functional.db_utils import get_utub_this_user_created, get_url_in_utub
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_assert_utils import (
    assert_not_visible_css_selector,
    assert_tooltip_animates,
    assert_visible_css_selector,
)
from tests.functional.playwright_login_utils import (
    login_user_select_utub_by_id_and_url_by_id,
)
from tests.functional.playwright_utils import (
    set_focus_on_element,
    wait_for_animation_to_end_check_top_lhs_corner,
    wait_for_any_element_with_text,
    wait_for_element_with_text,
    wait_then_click_element,
    wait_then_get_element,
)
from tests.functional.urls_ui.playwright_utils import ClipboardMockHelper

pytestmark = pytest.mark.urls_ui


def test_copy_url_btn_tooltip_animates_hvr(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    Tests a member's ability to see the tooltip animate when hovering over the copy URL button.

    GIVEN a user in a UTub with URLs
    WHEN the user selects a URL, and hovers over the copy URL button
    THEN ensure the tooltip for the copy URL button is animated properly
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    url_in_utub = get_url_in_utub(app, utub_user_created.id)

    login_user_select_utub_by_id_and_url_by_id(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_id=utub_user_created.id,
        utub_url_id=url_in_utub.id,
    )

    assert_tooltip_animates(
        page=page,
        parent_css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_COPY}",
        tooltip_parent_class=HPL.BUTTON_URL_COPY,
        tooltip_text=STRINGS.COPY_URL_TOOLTIP,
    )


def test_copy_url_btn_click_fail(
    page: Page,
    create_test_urls,
    provide_app: Flask,
    clipboard_mock_playwright: ClipboardMockHelper,
):
    """
    Tests a User's ability to copy the URL when clicking on URL button, and that
    the tooltip animates properly on failure.

    GIVEN a user is member of a selected UTub with a URL selected
    WHEN the user clicks on the copy URL button, but the copy fails
    THEN ensure the tooltip is shown properly.
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    url_in_utub = get_url_in_utub(app, utub_user_created.id)

    login_user_select_utub_by_id_and_url_by_id(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_id=utub_user_created.id,
        utub_url_id=url_in_utub.id,
    )

    assert_not_visible_css_selector(
        page=page, css_selector=f"{HPL.BUTTON_URL_COPY}{HPL.TOOLTIP_SUFFIX}"
    )
    copy_btn = f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_COPY}"

    url_copy_btn = wait_then_get_element(page=page, css_selector=copy_btn)
    url_copy_btn.hover()
    wait_for_animation_to_end_check_top_lhs_corner(
        page=page, css_selector=f"{HPL.BUTTON_URL_COPY}{HPL.TOOLTIP_SUFFIX}"
    )
    assert_visible_css_selector(
        page=page, css_selector=f"{HPL.BUTTON_URL_COPY}{HPL.TOOLTIP_SUFFIX}"
    )

    tooltip_on_hvr = wait_then_get_element(
        page=page, css_selector=f"{HPL.BUTTON_URL_COPY}{HPL.TOOLTIP_SUFFIX}"
    )
    assert tooltip_on_hvr.inner_text() == STRINGS.COPY_URL_TOOLTIP

    clipboard_mock_playwright.setup_clipboard_failure()
    assert clipboard_mock_playwright.verify_mock_setup()

    wait_then_click_element(page=page, css_selector=copy_btn)

    wait_for_any_element_with_text(
        page=page,
        css_selector=f"{HPL.BUTTON_URL_COPY}{HPL.TOOLTIP_SUFFIX}",
        expected_text=STRINGS.COPIED_URL_FAILURE_TOOLIP,
    )
    tooltip_on_click = wait_then_get_element(
        page=page, css_selector=f"{HPL.BUTTON_URL_COPY}{HPL.TOOLTIP_SUFFIX}"
    )
    assert tooltip_on_click.inner_text() == STRINGS.COPIED_URL_FAILURE_TOOLIP

    wait_for_animation_to_end_check_top_lhs_corner(
        page=page, css_selector=f"{HPL.BUTTON_URL_COPY}{HPL.TOOLTIP_SUFFIX}"
    )
    assert_not_visible_css_selector(
        page=page, css_selector=f"{HPL.BUTTON_URL_COPY}{HPL.TOOLTIP_SUFFIX}"
    )


def test_copy_url_btn_click(
    page: Page,
    create_test_urls,
    provide_app: Flask,
    clipboard_mock_playwright: ClipboardMockHelper,
):
    """
    Tests a User's ability to copy the URL when clicking on URL button, and that
    the tooltip animates properly on success.

    GIVEN a user is member of a selected UTub with a URL selected
    WHEN the user clicks on the copy URL button
    THEN ensure the URL is copied.
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    url_in_utub = get_url_in_utub(app, utub_user_created.id)

    with app.app_context():
        url: Urls = Urls.query.get(url_in_utub.url_id)
        url_string = url.url_string

    login_user_select_utub_by_id_and_url_by_id(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_id=utub_user_created.id,
        utub_url_id=url_in_utub.id,
    )

    assert_not_visible_css_selector(
        page=page, css_selector=f"{HPL.BUTTON_URL_COPY}{HPL.TOOLTIP_SUFFIX}"
    )
    copy_btn = f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_COPY}"

    url_copy_btn = wait_then_get_element(page=page, css_selector=copy_btn)
    url_copy_btn.hover()
    wait_for_animation_to_end_check_top_lhs_corner(
        page=page, css_selector=f"{HPL.BUTTON_URL_COPY}{HPL.TOOLTIP_SUFFIX}"
    )
    assert_visible_css_selector(
        page=page, css_selector=f"{HPL.BUTTON_URL_COPY}{HPL.TOOLTIP_SUFFIX}"
    )

    tooltip_on_hvr = wait_then_get_element(
        page=page, css_selector=f"{HPL.BUTTON_URL_COPY}{HPL.TOOLTIP_SUFFIX}"
    )
    assert tooltip_on_hvr.inner_text() == STRINGS.COPY_URL_TOOLTIP

    clipboard_mock_playwright.setup_clipboard_mock()
    assert clipboard_mock_playwright.verify_mock_setup()

    wait_then_click_element(page=page, css_selector=copy_btn)

    wait_for_element_with_text(
        page=page,
        css_selector=f"{HPL.BUTTON_URL_COPY}{HPL.TOOLTIP_SUFFIX}",
        expected_text=STRINGS.COPIED_URL_TOOLTIP,
    )
    tooltip_on_click = wait_then_get_element(
        page=page, css_selector=f"{HPL.BUTTON_URL_COPY}{HPL.TOOLTIP_SUFFIX}"
    )
    assert tooltip_on_click.inner_text() == STRINGS.COPIED_URL_TOOLTIP

    assert clipboard_mock_playwright.get_clipboard_content() == url_string

    wait_for_animation_to_end_check_top_lhs_corner(
        page=page, css_selector=f"{HPL.BUTTON_URL_COPY}{HPL.TOOLTIP_SUFFIX}"
    )
    assert_not_visible_css_selector(
        page=page, css_selector=f"{HPL.BUTTON_URL_COPY}{HPL.TOOLTIP_SUFFIX}"
    )


def test_copy_url_btn_key(
    page: Page,
    create_test_urls,
    provide_app: Flask,
    clipboard_mock_playwright: ClipboardMockHelper,
):
    """
    Tests a User's ability to copy the URL when clicking on URL button, and that
    the tooltip animates properly on success.

    GIVEN a user is member of a selected UTub with a URL selected
    WHEN the user presses enter on the copy URL button after it is focused
    THEN ensure the URL is copied.
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    url_in_utub = get_url_in_utub(app, utub_user_created.id)

    with app.app_context():
        url: Urls = Urls.query.get(url_in_utub.url_id)
        url_string = url.url_string

    login_user_select_utub_by_id_and_url_by_id(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_id=utub_user_created.id,
        utub_url_id=url_in_utub.id,
    )

    assert_not_visible_css_selector(
        page=page, css_selector=f"{HPL.BUTTON_URL_COPY}{HPL.TOOLTIP_SUFFIX}"
    )
    copy_btn = f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_COPY}"

    url_copy_btn = wait_then_get_element(page=page, css_selector=copy_btn)
    set_focus_on_element(page=page, locator=url_copy_btn)

    wait_for_animation_to_end_check_top_lhs_corner(
        page=page, css_selector=f"{HPL.BUTTON_URL_COPY}{HPL.TOOLTIP_SUFFIX}"
    )
    assert_visible_css_selector(
        page=page, css_selector=f"{HPL.BUTTON_URL_COPY}{HPL.TOOLTIP_SUFFIX}"
    )

    tooltip_on_hvr = wait_then_get_element(
        page=page, css_selector=f"{HPL.BUTTON_URL_COPY}{HPL.TOOLTIP_SUFFIX}"
    )
    assert tooltip_on_hvr.inner_text() == STRINGS.COPY_URL_TOOLTIP

    clipboard_mock_playwright.setup_clipboard_mock()
    assert clipboard_mock_playwright.verify_mock_setup()

    url_copy_btn = wait_then_get_element(page=page, css_selector=copy_btn)
    url_copy_btn.press("Enter")

    wait_for_element_with_text(
        page=page,
        css_selector=f"{HPL.BUTTON_URL_COPY}{HPL.TOOLTIP_SUFFIX}",
        expected_text=STRINGS.COPIED_URL_TOOLTIP,
    )
    tooltip_on_click = wait_then_get_element(
        page=page, css_selector=f"{HPL.BUTTON_URL_COPY}{HPL.TOOLTIP_SUFFIX}"
    )
    assert tooltip_on_click.inner_text() == STRINGS.COPIED_URL_TOOLTIP

    assert clipboard_mock_playwright.get_clipboard_content() == url_string

    wait_for_animation_to_end_check_top_lhs_corner(
        page=page, css_selector=f"{HPL.BUTTON_URL_COPY}{HPL.TOOLTIP_SUFFIX}"
    )
    assert_not_visible_css_selector(
        page=page, css_selector=f"{HPL.BUTTON_URL_COPY}{HPL.TOOLTIP_SUFFIX}"
    )
