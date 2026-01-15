import secrets

from flask import Flask, session
from selenium.webdriver.remote.webdriver import WebDriver


from src.models.users import Users
from tests.functional.assert_utils import (
    assert_login_with_username,
    assert_panel_visibility_mobile,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.selenium_utils import (
    Decks,
    select_url_by_title,
    select_url_by_url_string,
    select_utub_by_name,
    wait_for_animation_to_end_check_top_lhs_corner,
    wait_for_page_complete_and_dom_stable,
    wait_then_click_element,
    wait_until_visible_css_selector,
)


def create_user_session_and_provide_session_id(app: Flask, user_id: int) -> str:
    """
    Manually creates a user session to allow user to be logged in
    without needing UI interaction.

    Args:
        app (Flask): The Flask application is necessary to generate a request context in order to insert the session into the appropriate session engine
        user_id (int): The user ID wanting to be logged in as

    Returns:
        (str): The session ID of the user that can be used to log the user in
    """
    random_sid = _create_random_sid()
    with app.test_request_context("/"):
        user: Users = Users.query.get(user_id)
        session["_user_id"] = user.get_id()
        session["_fresh"] = True
        session["_id"] = _create_random_identifier()
        session.sid = random_sid
        session.modified = True

        app.session_interface.save_session(
            app, session, response=app.make_response("Testing")
        )
    return random_sid


def _create_random_identifier() -> str:
    return secrets.token_hex(64)


def _create_random_sid() -> str:
    return secrets.token_urlsafe(32)


def login_user_with_cookie_from_session(browser: WebDriver, session_id: str):
    cookie = {
        "name": "session",
        "value": session_id,
        "path": "/",
        "httpOnly": True,
    }

    browser.add_cookie(cookie)

    # Refresh to redirect user to their home page since they're logged in
    browser.refresh()


def login_user_to_home_page(app: Flask, browser: WebDriver, user_id: int):
    session_id = create_user_session_and_provide_session_id(app, user_id)
    login_user_with_cookie_from_session(browser, session_id)


def login_user_and_select_utub_by_utubid(
    app: Flask, browser: WebDriver, user_id: int, utub_id: int
):
    session_id = create_user_session_and_provide_session_id(app, user_id)
    login_user_with_cookie_from_session(browser, session_id)

    with app.app_context():
        user: Users = Users.query.get(user_id)

    assert_login_with_username(browser, user.username)
    wait_then_click_element(
        browser, f"{HPL.SELECTORS_UTUB}[utubid='{utub_id}']", time=10
    )


def login_user_and_select_utub_by_utubid_mobile(
    app: Flask, browser: WebDriver, user_id: int, utub_id: int
):
    session_id = create_user_session_and_provide_session_id(app, user_id)
    login_user_with_cookie_from_session(browser, session_id)
    assert_panel_visibility_mobile(browser, Decks.UTUBS)

    wait_then_click_element(
        browser, f"{HPL.SELECTORS_UTUB}[utubid='{utub_id}']", time=10
    )


def login_user_select_utub_by_id_and_url_by_id(
    app: Flask, browser: WebDriver, user_id: int, utub_id: int, utub_url_id: int
):
    login_user_and_select_utub_by_utubid(app, browser, user_id, utub_id)
    url_row_selector = f"{HPL.ROWS_URLS}[utuburlid='{utub_url_id}']"
    wait_then_click_element(browser, url_row_selector, time=10)
    selected_url_access_btn = f"{url_row_selector} {HPL.BUTTON_URL_ACCESS}"
    wait_until_visible_css_selector(browser, selected_url_access_btn, timeout=3)
    wait_for_animation_to_end_check_top_lhs_corner(browser, selected_url_access_btn)


def login_user_and_select_utub_by_name(
    app: Flask, browser: WebDriver, user_id: int, utub_name: str
):
    session_id = create_user_session_and_provide_session_id(app, user_id)
    login_user_with_cookie_from_session(browser, session_id)
    select_utub_by_name(browser, utub_name)


def login_user_select_utub_by_name_and_url_by_title(
    app: Flask, browser: WebDriver, user_id: int, utub_name: str, url_title: str
):
    login_user_and_select_utub_by_name(app, browser, user_id, utub_name)
    select_url_by_title(browser, url_title)


def login_user_select_utub_by_name_and_url_by_string(
    app: Flask, browser: WebDriver, user_id: int, utub_name: str, url_string: str
):
    login_user_and_select_utub_by_name(app, browser, user_id, utub_name)
    select_url_by_url_string(browser, url_string)
    wait_for_page_complete_and_dom_stable(browser)


def login_user_select_utub_by_id_open_create_utub_tag(
    app: Flask, browser: WebDriver, user_id: int, utub_id: int
):
    login_user_and_select_utub_by_utubid(app, browser, user_id, utub_id)
    wait_then_click_element(browser, HPL.BUTTON_UTUB_TAG_CREATE)
