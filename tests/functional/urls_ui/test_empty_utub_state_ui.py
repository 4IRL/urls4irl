from flask import Flask
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

from backend import db
from backend.models.utub_members import Utub_Members
from backend.models.utubs import Utubs
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.assert_utils import (
    assert_not_visible_css_selector,
    assert_visible_css_selector,
)
from tests.functional.db_utils import get_utub_this_user_created
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.login_utils import login_user_and_select_utub_by_utubid
from tests.functional.selenium_utils import (
    select_utub_by_id,
    wait_then_click_element,
    wait_then_get_element,
    wait_then_get_elements,
)
from tests.functional.urls_ui.selenium_utils import create_url

pytestmark = pytest.mark.urls_ui


def test_empty_utub_shows_no_urls_message(
    browser: WebDriver, create_test_utubs, provide_app: Flask
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
        app, browser, user_id_for_test, utub_user_created.id
    )

    assert_visible_css_selector(browser, HPL.SUBHEADER_NO_URLS, time=3)

    no_urls_elem = browser.find_element(By.CSS_SELECTOR, HPL.SUBHEADER_NO_URLS)
    assert no_urls_elem.text == UTS.UTUB_NO_URLS


def test_empty_utub_shows_add_url_button(
    browser: WebDriver, create_test_utubs, provide_app: Flask
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
        app, browser, user_id_for_test, utub_user_created.id
    )

    assert_visible_css_selector(browser, HPL.BUTTON_DECK_URL_CREATE, time=3)

    add_url_btn = browser.find_element(By.CSS_SELECTOR, HPL.BUTTON_DECK_URL_CREATE)
    assert add_url_btn.text == "Add URL"


def test_add_url_button_opens_create_form(
    browser: WebDriver, create_test_utubs, provide_app: Flask
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
        app, browser, user_id_for_test, utub_user_created.id
    )

    assert_visible_css_selector(browser, HPL.BUTTON_DECK_URL_CREATE, time=3)

    wait_then_click_element(browser, HPL.BUTTON_DECK_URL_CREATE, time=3)

    assert_visible_css_selector(browser, HPL.WRAP_URL_CREATE, time=3)
    assert_not_visible_css_selector(browser, HPL.SUBHEADER_NO_URLS, time=3)


def test_creating_url_hides_empty_state(
    browser: WebDriver, create_test_utubs, provide_app: Flask
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
        app, browser, user_id_for_test, utub_user_created.id
    )

    assert_visible_css_selector(browser, HPL.SUBHEADER_NO_URLS, time=3)

    create_url(browser, "Test URL", "https://example.com")

    url_row_elem = wait_then_get_element(browser, HPL.ROWS_URLS, time=5)
    assert url_row_elem is not None

    assert_not_visible_css_selector(browser, HPL.SUBHEADER_NO_URLS, time=3)
    assert_not_visible_css_selector(browser, HPL.BUTTON_DECK_URL_CREATE, time=3)


def test_populated_utub_does_not_show_empty_state(
    browser: WebDriver, create_test_urls, provide_app: Flask
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
        app, browser, user_id_for_test, utub_user_created.id
    )

    url_rows = wait_then_get_elements(browser, HPL.ROWS_URLS, time=5)
    assert len(url_rows) > 0

    assert_not_visible_css_selector(browser, HPL.SUBHEADER_NO_URLS, time=3)
    assert_not_visible_css_selector(browser, HPL.BUTTON_DECK_URL_CREATE, time=3)


def test_switching_from_populated_to_empty_utub_shows_empty_state(
    browser: WebDriver, create_test_urls, provide_app: Flask
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
        app, browser, user_id_for_test, utub_user_created.id
    )

    url_rows = wait_then_get_elements(browser, HPL.ROWS_URLS, time=5)
    assert len(url_rows) > 0
    assert_not_visible_css_selector(browser, HPL.SUBHEADER_NO_URLS, time=3)

    select_utub_by_id(browser, empty_utub_id)

    assert_visible_css_selector(browser, HPL.SUBHEADER_NO_URLS, time=3)

    no_urls_elem = browser.find_element(By.CSS_SELECTOR, HPL.SUBHEADER_NO_URLS)
    assert no_urls_elem.text == UTS.UTUB_NO_URLS
