from flask import Flask
from playwright.sync_api import Page, expect

from backend.models.users import Users
from backend.utils.strings.utub_strs import UTUB_ID_QUERY_PARAM
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_assert_utils import (
    assert_login_with_username,
    assert_panel_visibility_mobile,
)
from tests.functional.playwright_utils import (
    Decks,
    current_base_url,
    login_user_to_home_page,
    select_url_by_title,
    select_url_by_url_string,
    select_utub_by_name,
    wait_then_click_element,
    wait_until_visible_css_selector,
)


def login_user_and_select_utub_by_utubid(
    *, app: Flask, page: Page, user_id: int, utub_id: int
) -> None:
    login_user_to_home_page(app=app, page=page, user_id=user_id)

    with app.app_context():
        user: Users = Users.query.get(user_id)

    assert_login_with_username(page=page, username=user.username)
    wait_then_click_element(
        page=page, css_selector=f"{HPL.SELECTORS_UTUB}[utubid='{utub_id}']"
    )


def login_user_and_visit_preselected_utub(
    *, app: Flask, page: Page, user_id: int, utub_id: int
) -> None:
    login_user_to_home_page(app=app, page=page, user_id=user_id)
    base_url = current_base_url(page=page)
    page.goto(f"{base_url}/home?{UTUB_ID_QUERY_PARAM}={utub_id}")


def login_user_and_select_utub_by_utubid_mobile(
    *, app: Flask, page: Page, user_id: int, utub_id: int
) -> None:
    login_user_to_home_page(app=app, page=page, user_id=user_id)
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.UTUBS)

    wait_then_click_element(
        page=page, css_selector=f"{HPL.SELECTORS_UTUB}[utubid='{utub_id}']"
    )


def login_user_select_utub_by_id_and_url_by_id(
    *, app: Flask, page: Page, user_id: int, utub_id: int, utub_url_id: int
) -> None:
    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id, utub_id=utub_id
    )
    url_row_selector = f"{HPL.ROWS_URLS}[utuburlid='{utub_url_id}']"
    wait_then_click_element(page=page, css_selector=url_row_selector)
    selected_url_access_btn = f"{url_row_selector} {HPL.BUTTON_URL_ACCESS}"
    wait_until_visible_css_selector(page=page, css_selector=selected_url_access_btn)
    expect(page.locator(selected_url_access_btn)).to_be_enabled()


def login_user_and_select_utub_by_name(
    *, app: Flask, page: Page, user_id: int, utub_name: str
) -> None:
    login_user_to_home_page(app=app, page=page, user_id=user_id)
    select_utub_by_name(page=page, utub_name=utub_name)


def login_user_select_utub_by_name_and_url_by_title(
    *, app: Flask, page: Page, user_id: int, utub_name: str, url_title: str
) -> None:
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_name
    )
    select_url_by_title(page=page, url_title=url_title)


def login_user_select_utub_by_name_and_url_by_string(
    *, app: Flask, page: Page, user_id: int, utub_name: str, url_string: str
) -> None:
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_name
    )
    select_url_by_url_string(page=page, url_string=url_string)


def login_user_select_utub_by_id_open_create_utub_tag(
    *, app: Flask, page: Page, user_id: int, utub_id: int
) -> None:
    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id, utub_id=utub_id
    )
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_TAG_CREATE)
