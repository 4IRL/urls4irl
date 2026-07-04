from flask import Flask
import pytest
from playwright.sync_api import Page, expect

from backend import db
from backend.models.users import Users
from backend.models.utub_tags import Utub_Tags
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.utils.constants import TAG_CONSTANTS
from tests.functional.db_utils import get_utub_this_user_created
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_assert_utils import (
    assert_active_utub,
    assert_login_with_username,
    assert_not_visible_css_selector,
    assert_on_429_page,
    assert_visible_css_selector,
    assert_visited_403_on_invalid_csrf_and_reload,
)
from tests.functional.playwright_login_utils import login_user_and_select_utub_by_utubid
from tests.functional.playwright_utils import (
    add_forced_rate_limit_header,
    dismiss_modal_with_click_out,
    force_next_delete_ajax_failure_no_navigate,
    invalidate_csrf_token_on_page,
    wait_for_modal_ready,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_hidden,
    wait_until_visible_css_selector,
)
from tests.functional.tags_ui.playwright_assert_utils import (
    assert_delete_utub_tag_modal_shown,
)
from tests.functional.tags_ui.playwright_utils import (
    apply_tag_filter_by_id_and_get_shown_urls,
    click_open_update_utub_tags_btn,
    delete_utub_tag_elem,
    get_all_utub_tags_ids_in_utub,
    get_first_visible_tag_in_utub,
    open_delete_utub_tag_confirm_modal_for_tag,
)

pytestmark = pytest.mark.tags_ui


def test_open_delete_utub_tag_modal_click(
    page: Page, create_test_tags, provide_app: Flask
):
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id, utub_id=utub_user_created.id
    )

    tag_id = get_first_visible_tag_in_utub(page=page).get_attribute(
        HPL.TAG_BADGE_ID_ATTRIB
    )
    assert tag_id

    click_open_update_utub_tags_btn(page=page)
    delete_utub_tag_css_selector = (
        f"{HPL.TAG_FILTERS}[{HPL.TAG_BADGE_ID_ATTRIB}='{tag_id}']"
        f" > {HPL.UTUB_TAG_MENU_WRAP}"
        f" > {HPL.BUTTON_UTUB_TAG_DELETE}"
    )

    assert_visible_css_selector(page=page, css_selector=delete_utub_tag_css_selector)
    wait_then_click_element(page=page, css_selector=delete_utub_tag_css_selector)

    assert_delete_utub_tag_modal_shown(page=page, tag_id=int(tag_id), app=app)


def test_open_delete_utub_tag_modal_key(
    page: Page, create_test_tags, provide_app: Flask
):
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id, utub_id=utub_user_created.id
    )

    tag_id = get_first_visible_tag_in_utub(page=page).get_attribute(
        HPL.TAG_BADGE_ID_ATTRIB
    )
    assert tag_id

    click_open_update_utub_tags_btn(page=page)
    delete_utub_tag_css_selector = (
        f"{HPL.TAG_FILTERS}[{HPL.TAG_BADGE_ID_ATTRIB}='{tag_id}']"
        f" > {HPL.UTUB_TAG_MENU_WRAP}"
        f" > {HPL.BUTTON_UTUB_TAG_DELETE}"
    )

    assert_visible_css_selector(page=page, css_selector=delete_utub_tag_css_selector)
    delete_tag_btn = wait_then_get_element(
        page=page, css_selector=delete_utub_tag_css_selector
    )
    assert delete_tag_btn

    delete_tag_btn.press("Enter")
    assert_delete_utub_tag_modal_shown(page=page, tag_id=int(tag_id), app=app)


def test_dismiss_delete_utub_tag_modal_btn_click(
    page: Page, create_test_tags, provide_app: Flask
):
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id, utub_id=utub_user_created.id
    )

    tag_id = get_first_visible_tag_in_utub(page=page).get_attribute(
        HPL.TAG_BADGE_ID_ATTRIB
    )
    assert tag_id

    open_delete_utub_tag_confirm_modal_for_tag(page=page, tag_id=tag_id, app=app)

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_DISMISS)

    wait_until_hidden(page=page, css_selector=HPL.HOME_MODAL)


def test_dismiss_delete_utub_tag_modal_btn_key(
    page: Page, create_test_tags, provide_app: Flask
):
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id, utub_id=utub_user_created.id
    )

    tag_id = get_first_visible_tag_in_utub(page=page).get_attribute(
        HPL.TAG_BADGE_ID_ATTRIB
    )
    assert tag_id

    open_delete_utub_tag_confirm_modal_for_tag(page=page, tag_id=tag_id, app=app)

    # Wait for Bootstrap's show transition to complete before pressing Enter.
    # press() does not auto-wait for parent element stability (unlike click()), so
    # if the modal is mid-fade-in when Enter fires, Bootstrap's modal.hide() call
    # is a no-op (_isTransitioning guard).
    wait_for_modal_ready(page=page, modal_selector=HPL.HOME_MODAL)

    close_btn = wait_then_get_element(page=page, css_selector=HPL.BUTTON_MODAL_DISMISS)
    assert close_btn

    close_btn.press("Enter")

    wait_until_hidden(page=page, css_selector=HPL.HOME_MODAL)


def test_dismiss_delete_utub_tag_modal_x(
    page: Page, create_test_tags, provide_app: Flask
):
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id, utub_id=utub_user_created.id
    )

    tag_id = get_first_visible_tag_in_utub(page=page).get_attribute(
        HPL.TAG_BADGE_ID_ATTRIB
    )
    assert tag_id

    open_delete_utub_tag_confirm_modal_for_tag(page=page, tag_id=tag_id, app=app)

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_X_CLOSE)

    wait_until_hidden(page=page, css_selector=HPL.HOME_MODAL)


def test_dismiss_delete_utub_tag_modal_click_outside_modal(
    page: Page, create_test_tags, provide_app: Flask
):
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id, utub_id=utub_user_created.id
    )

    tag_id = get_first_visible_tag_in_utub(page=page).get_attribute(
        HPL.TAG_BADGE_ID_ATTRIB
    )
    assert tag_id

    open_delete_utub_tag_confirm_modal_for_tag(page=page, tag_id=tag_id, app=app)
    # Wait for Bootstrap's show transition to complete before clicking outside.
    # Clicking the backdrop while _isTransitioning is true is a no-op, so the
    # modal never becomes hidden.
    wait_for_modal_ready(page=page, modal_selector=HPL.HOME_MODAL)
    dismiss_modal_with_click_out(page=page, modal_selector=HPL.HOME_MODAL)

    wait_until_hidden(page=page, css_selector=HPL.HOME_MODAL)


def test_delete_utub_tag_removes_utub_tag_elem(
    page: Page, create_test_tags, provide_app: Flask
):
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id, utub_id=utub_user_created.id
    )

    tag_id = get_first_visible_tag_in_utub(page=page).get_attribute(
        HPL.TAG_BADGE_ID_ATTRIB
    )
    assert tag_id

    delete_utub_tag_elem(page=page, tag_id=tag_id, app=app)

    assert tag_id not in get_all_utub_tags_ids_in_utub(page=page)


def test_delete_utub_tag_removes_url_tag_elems(
    page: Page, create_test_tags, provide_app: Flask
):
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id, utub_id=utub_user_created.id
    )

    tag_id = get_first_visible_tag_in_utub(page=page).get_attribute(
        HPL.TAG_BADGE_ID_ATTRIB
    )
    assert tag_id

    url_tag_badge_selector = f"{HPL.TAG_BADGES}[{HPL.TAG_BADGE_ID_ATTRIB}='{tag_id}']"
    assert page.locator(url_tag_badge_selector).count() > 0

    delete_utub_tag_elem(page=page, tag_id=tag_id, app=app)

    assert page.locator(url_tag_badge_selector).count() == 0


def test_delete_utub_tag_while_selected_unfilters_url_and_updates_text(
    page: Page, create_test_urls, provide_app: Flask
):
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    with app.app_context():
        utub_urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_user_created.id
        ).all()
        first_url, second_url = utub_urls[0], utub_urls[1]
        for tag_string, url in zip(("tag_1", "tag_2"), (first_url, second_url)):
            new_tag = Utub_Tags(
                utub_id=utub_user_created.id, tag_string=tag_string, created_by=user_id
            )
            db.session.add(new_tag)
            db.session.commit()

            new_utub_url_tag = Utub_Url_Tags(
                utub_id=utub_user_created.id,
                utub_tag_id=new_tag.id,
                utub_url_id=url.id,
            )
            db.session.add(new_utub_url_tag)
            db.session.commit()

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id, utub_id=utub_user_created.id
    )

    tag_id = get_first_visible_tag_in_utub(page=page).get_attribute(
        HPL.TAG_BADGE_ID_ATTRIB
    )
    assert tag_id

    displayed_urls_with_tag = apply_tag_filter_by_id_and_get_shown_urls(
        page=page, utub_tag_id=int(tag_id)
    )

    tag_deck_count = wait_then_get_element(page=page, css_selector=HPL.TAG_DECK_COUNT)
    assert tag_deck_count

    tag_deck_count_txt = tag_deck_count.inner_text()
    assert f"(1/{TAG_CONSTANTS.MAX_URL_TAGS})" in tag_deck_count_txt

    delete_utub_tag_elem(page=page, tag_id=tag_id, app=app)

    url_row_elements = page.locator(HPL.ROWS_URLS).all()
    visible_urls = [url_row for url_row in url_row_elements if url_row.is_visible()]

    assert len(visible_urls) > len(displayed_urls_with_tag)

    tag_deck_count = wait_then_get_element(page=page, css_selector=HPL.TAG_DECK_COUNT)
    assert tag_deck_count

    tag_deck_count_txt = tag_deck_count.inner_text()
    assert f"(0/{TAG_CONSTANTS.MAX_URL_TAGS})" in tag_deck_count_txt


def test_delete_utub_tag_rate_limits(page: Page, create_test_tags, provide_app: Flask):
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id, utub_id=utub_user_created.id
    )

    tag_id = get_first_visible_tag_in_utub(page=page).get_attribute(
        HPL.TAG_BADGE_ID_ATTRIB
    )
    assert tag_id

    url_tag_badge_selector = f"{HPL.TAG_BADGES}[{HPL.TAG_BADGE_ID_ATTRIB}='{tag_id}']"
    assert page.locator(url_tag_badge_selector).count() > 0

    add_forced_rate_limit_header(page=page)
    open_delete_utub_tag_confirm_modal_for_tag(page=page, tag_id=tag_id, app=app)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)

    assert_on_429_page(page=page)


def test_delete_last_utub_tag_closes_utub_tag_menu(
    page: Page, create_test_urls, provide_app: Flask
):
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    with app.app_context():
        new_tag = Utub_Tags(
            utub_id=utub_user_created.id, tag_string="tag_1", created_by=user_id
        )
        db.session.add(new_tag)
        db.session.commit()

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id, utub_id=utub_user_created.id
    )

    tag_id = get_first_visible_tag_in_utub(page=page).get_attribute(
        HPL.TAG_BADGE_ID_ATTRIB
    )
    assert tag_id

    delete_utub_tag_elem(page=page, tag_id=tag_id, app=app)

    assert_visible_css_selector(
        page=page, css_selector=HPL.WRAP_BUTTONS_CREATE_UNFILTER_UTUB_TAGS
    )
    assert_not_visible_css_selector(page=page, css_selector=HPL.UTUB_TAG_MENU_WRAP)
    assert_not_visible_css_selector(
        page=page, css_selector=HPL.WRAP_BUTTON_UPDATE_TAG_ALL_CLOSE
    )
    assert_not_visible_css_selector(page=page, css_selector=HPL.BUTTON_UTUB_TAG_DELETE)


def test_delete_utub_tag_invalid_csrf_token(
    page: Page, create_test_tags, provide_app: Flask
):
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    with app.app_context():
        user: Users = Users.query.get(1)
        username = user.username

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id, utub_id=utub_user_created.id
    )

    tag_id = get_first_visible_tag_in_utub(page=page).get_attribute(
        HPL.TAG_BADGE_ID_ATTRIB
    )
    assert tag_id

    invalidate_csrf_token_on_page(page=page)
    open_delete_utub_tag_confirm_modal_for_tag(page=page, tag_id=tag_id, app=app)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)

    assert_visited_403_on_invalid_csrf_and_reload(page=page)

    assert_login_with_username(page=page, username=username)

    assert_active_utub(page=page, utub_name=utub_user_created.name)

    wait_until_hidden(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)


def test_delete_utub_tag_submit_button_reenables_on_server_error(
    page: Page, create_test_tags, provide_app: Flask
):
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id, utub_id=utub_user_created.id
    )

    tag_id = get_first_visible_tag_in_utub(page=page).get_attribute(
        HPL.TAG_BADGE_ID_ATTRIB
    )
    assert tag_id

    open_delete_utub_tag_confirm_modal_for_tag(page=page, tag_id=tag_id, app=app)

    force_next_delete_ajax_failure_no_navigate(page=page)

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)

    expect(page.locator(HPL.BUTTON_MODAL_SUBMIT).first).to_be_enabled()


def test_delete_utub_tag_submit_button_enabled_on_second_modal_open(
    page: Page, create_test_tags, provide_app: Flask
):
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id, utub_id=utub_user_created.id
    )

    first_tag_elem = get_first_visible_tag_in_utub(page=page)
    first_tag_id = first_tag_elem.get_attribute(HPL.TAG_BADGE_ID_ATTRIB)
    assert first_tag_id

    delete_utub_tag_elem(page=page, tag_id=first_tag_id, app=app)

    second_tag_elem = get_first_visible_tag_in_utub(page=page)
    second_tag_id = second_tag_elem.get_attribute(HPL.TAG_BADGE_ID_ATTRIB)
    assert second_tag_id

    second_tag_delete_selector = (
        f"{HPL.TAG_FILTERS}[{HPL.TAG_BADGE_ID_ATTRIB}='{second_tag_id}']"
        f" > {HPL.UTUB_TAG_MENU_WRAP} > {HPL.BUTTON_UTUB_TAG_DELETE}"
    )
    wait_then_click_element(page=page, css_selector=second_tag_delete_selector)
    wait_until_visible_css_selector(page=page, css_selector=HPL.HOME_MODAL)

    expect(page.locator(HPL.BUTTON_MODAL_SUBMIT).first).to_be_enabled()
