from flask import Flask
import pytest
from playwright.sync_api import Page

from backend.models.users import Users
from tests.functional.db_utils import (
    get_tag_on_url_in_utub,
    get_url_in_utub,
    get_utub_this_user_created,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_assert_utils import (
    assert_login_with_username,
    assert_on_429_page,
    assert_visited_403_on_invalid_csrf_and_reload,
)
from tests.functional.playwright_login_utils import (
    login_user_select_utub_by_id_and_url_by_id,
)
from tests.functional.playwright_utils import (
    add_forced_rate_limit_header,
    get_selected_url,
    invalidate_csrf_token_on_page,
    open_update_url_title,
    wait_for_element_to_be_removed,
    wait_then_click_element,
    wait_until_css_property,
)
from tests.functional.tags_ui.playwright_utils import (
    get_delete_tag_button_on_hover,
    get_tag_badge_selector_on_selected_url_by_tag_id,
    get_visible_urls_and_urls_with_tag_text_by_tag_id,
)

pytestmark = pytest.mark.tags_ui


def test_get_delete_tag_button_on_hover(
    page: Page, create_test_tags, provide_app: Flask
):
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    url_in_utub = get_url_in_utub(app, utub_user_created.id)
    url_tag = get_tag_on_url_in_utub(app, utub_user_created.id, url_in_utub.id)

    login_user_select_utub_by_id_and_url_by_id(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_id=utub_user_created.id,
        utub_url_id=url_in_utub.id,
    )

    tag_badge_selector = get_tag_badge_selector_on_selected_url_by_tag_id(
        url_tag_id=url_tag.id
    )
    delete_tag_button = get_delete_tag_button_on_hover(
        page=page, tag_badge_selector=tag_badge_selector
    )

    assert delete_tag_button.is_visible()


def test_hide_delete_tag_button_after_hover(
    page: Page, create_test_tags, provide_app: Flask
):
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    url_in_utub = get_url_in_utub(app, utub_user_created.id)
    url_tag = get_tag_on_url_in_utub(app, utub_user_created.id, url_in_utub.id)

    login_user_select_utub_by_id_and_url_by_id(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_id=utub_user_created.id,
        utub_url_id=url_in_utub.id,
    )

    tag_badge_selector = get_tag_badge_selector_on_selected_url_by_tag_id(
        url_tag_id=url_tag.id
    )
    delete_tag_button = get_delete_tag_button_on_hover(
        page=page, tag_badge_selector=tag_badge_selector
    )

    assert delete_tag_button.is_visible()

    url_title_selector = f"{HPL.ROW_SELECTED_URL} {HPL.URL_TITLE_READ}"
    page.locator(url_title_selector).first.hover()

    delete_tag_btn_selector = f"{tag_badge_selector} > {HPL.BUTTON_TAG_DELETE}"
    wait_until_css_property(
        page=page,
        css_selector=delete_tag_btn_selector,
        css_property="opacity",
        expected_value="0",
    )
    assert (
        page.locator(delete_tag_btn_selector).first.evaluate(
            "element => window.getComputedStyle(element).getPropertyValue('opacity')"
        )
        == "0"
    )


def test_delete_tag(page: Page, create_test_tags, provide_app: Flask):
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    utub_id = utub_user_created.id
    url_in_utub = get_url_in_utub(app, utub_id)
    url_id = url_in_utub.id
    url_tag = get_tag_on_url_in_utub(app, utub_id, url_id)
    tag_id = url_tag.utub_tag_id

    login_user_select_utub_by_id_and_url_by_id(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_id=utub_id,
        utub_url_id=url_id,
    )

    init_vis, init_total = get_visible_urls_and_urls_with_tag_text_by_tag_id(
        page=page, tag_id=tag_id
    )

    tag_badge_selector = get_tag_badge_selector_on_selected_url_by_tag_id(
        url_tag_id=url_id
    )
    delete_tag_button = get_delete_tag_button_on_hover(
        page=page, tag_badge_selector=tag_badge_selector
    )

    tag_badge_locator = page.locator(tag_badge_selector)
    delete_tag_button.click()

    wait_for_element_to_be_removed(page=page, locator=tag_badge_locator)

    assert page.locator(tag_badge_selector).count() == 0

    final_vis, final_total = get_visible_urls_and_urls_with_tag_text_by_tag_id(
        page=page, tag_id=tag_id
    )
    assert final_vis == init_vis - 1
    assert final_total == init_total - 1


def test_delete_tag_rate_limits(page: Page, create_test_tags, provide_app: Flask):
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    utub_id = utub_user_created.id
    url_in_utub = get_url_in_utub(app, utub_id)
    url_id = url_in_utub.id

    login_user_select_utub_by_id_and_url_by_id(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_id=utub_id,
        utub_url_id=url_id,
    )

    tag_badge_selector = get_tag_badge_selector_on_selected_url_by_tag_id(
        url_tag_id=url_id
    )
    # The delete button is revealed only while its tag badge is :hover-ed.
    # Register the forced rate-limit header BEFORE revealing the button so no
    # page work happens between the hover-reveal and the click — mirroring the
    # reliable happy-path test_delete_tag ordering. An intervening call could
    # drop the :hover state under CI load, hiding the button and timing the
    # click out. Re-hover immediately before clicking as a belt-and-suspenders
    # guard against a re-render dropping the hover between reveal and click.
    add_forced_rate_limit_header(page=page)
    delete_tag_button = get_delete_tag_button_on_hover(
        page=page, tag_badge_selector=tag_badge_selector
    )
    page.locator(tag_badge_selector).first.hover()
    delete_tag_button.click()

    assert_on_429_page(page=page)


def test_no_get_delete_tag_button_on_hover_update_url_title(
    page: Page, create_test_tags, provide_app: Flask
):
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    url_in_utub = get_url_in_utub(app, utub_user_created.id)
    url_tag = get_tag_on_url_in_utub(app, utub_user_created.id, url_in_utub.id)

    login_user_select_utub_by_id_and_url_by_id(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_id=utub_user_created.id,
        utub_url_id=url_in_utub.id,
    )

    open_update_url_title(page=page, selected_url_row=get_selected_url(page=page))

    tag_badge_selector = get_tag_badge_selector_on_selected_url_by_tag_id(
        url_tag_id=url_tag.id
    )
    delete_tag_button = get_delete_tag_button_on_hover(
        page=page, tag_badge_selector=tag_badge_selector, assert_visible=False
    )
    assert not delete_tag_button.is_visible()


def test_no_get_delete_tag_button_on_hover_update_url_string(
    page: Page, create_test_tags, provide_app: Flask
):
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    url_in_utub = get_url_in_utub(app, utub_user_created.id)
    url_tag = get_tag_on_url_in_utub(app, utub_user_created.id, url_in_utub.id)

    login_user_select_utub_by_id_and_url_by_id(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_id=utub_user_created.id,
        utub_url_id=url_in_utub.id,
    )

    edit_url_selector = f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_STRING_UPDATE}"
    wait_then_click_element(page=page, css_selector=edit_url_selector)

    tag_badge_selector = get_tag_badge_selector_on_selected_url_by_tag_id(
        url_tag_id=url_tag.id
    )
    delete_tag_button = get_delete_tag_button_on_hover(
        page=page, tag_badge_selector=tag_badge_selector, assert_visible=False
    )
    assert not delete_tag_button.is_visible()


def test_no_get_delete_tag_button_on_hover_add_tag(
    page: Page, create_test_tags, provide_app: Flask
):
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    url_in_utub = get_url_in_utub(app, utub_user_created.id)
    url_tag = get_tag_on_url_in_utub(app, utub_user_created.id, url_in_utub.id)

    login_user_select_utub_by_id_and_url_by_id(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_id=utub_user_created.id,
        utub_url_id=url_in_utub.id,
    )

    add_tag_selector = f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_TAG_CREATE}"
    wait_then_click_element(page=page, css_selector=add_tag_selector)

    tag_badge_selector = get_tag_badge_selector_on_selected_url_by_tag_id(
        url_tag_id=url_tag.id
    )
    delete_tag_button = get_delete_tag_button_on_hover(
        page=page, tag_badge_selector=tag_badge_selector, assert_visible=False
    )
    assert not delete_tag_button.is_visible()


def test_delete_tag_invalid_csrf(page: Page, create_test_tags, provide_app: Flask):
    app = provide_app
    user_id_for_test = 1
    with app.app_context():
        user: Users = Users.query.get(user_id_for_test)

    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    url_in_utub = get_url_in_utub(app, utub_user_created.id)
    url_tag = get_tag_on_url_in_utub(app, utub_user_created.id, url_in_utub.id)

    login_user_select_utub_by_id_and_url_by_id(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_id=utub_user_created.id,
        utub_url_id=url_in_utub.id,
    )

    tag_badge_selector = get_tag_badge_selector_on_selected_url_by_tag_id(
        url_tag_id=url_tag.id
    )
    delete_tag_button = get_delete_tag_button_on_hover(
        page=page, tag_badge_selector=tag_badge_selector
    )

    invalidate_csrf_token_on_page(page=page)
    delete_tag_button.click()

    assert_visited_403_on_invalid_csrf_and_reload(page=page)
    assert_login_with_username(page=page, username=user.username)

    assert page.locator(tag_badge_selector).count() == 0
