from flask import Flask
import pytest
from selenium.webdriver.remote.webdriver import WebDriver

from tests.functional.assert_utils import (
    assert_on_429_page,
    assert_url_coloring_is_correct,
    assert_utub_selected,
)
from tests.functional.db_utils import (
    get_utub_this_user_created,
    get_utub_this_user_did_not_create,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.login_utils import (
    login_user_and_select_utub_by_utubid,
    login_user_to_home_page,
)
from tests.functional.selenium_utils import (
    add_forced_rate_limit_header,
    select_utub_by_id,
    wait_for_element_presence,
    wait_then_click_element,
)
from tests.functional.utubs_ui.assert_utils import (
    assert_in_created_utub,
    assert_in_member_utub,
)

pytestmark = pytest.mark.utubs_ui


def test_select_member_utub_from_home_page(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    GIVEN a fresh load of the U4i Home page, where user is in multiple UTubs
    WHEN user clicks one of the UTubs they did not create
    THEN ensure the all appropriate elements are visible and ready
    """

    app = provide_app
    user_id_for_test = 1
    utub_user_did_not_create = get_utub_this_user_did_not_create(app, user_id_for_test)

    login_user_to_home_page(app, browser, user_id_for_test)
    select_utub_by_id(browser, utub_user_did_not_create.id)
    assert_utub_selected(browser, app, utub_user_did_not_create.id)
    assert_url_coloring_is_correct(browser)
    assert_in_member_utub(browser)


def test_select_created_utub_from_home_page(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    GIVEN a fresh load of the U4i Home page, where user is in multiple UTubs
    WHEN user clicks one of the UTubs they did create
    THEN ensure the all appropriate elements are visible and ready
    """

    app = provide_app
    user_id_for_test = 1
    utub_user_did_not_create = get_utub_this_user_created(app, user_id_for_test)

    login_user_to_home_page(app, browser, user_id_for_test)
    select_utub_by_id(browser, utub_user_did_not_create.id)
    assert_utub_selected(browser, app, utub_user_did_not_create.id)
    assert_url_coloring_is_correct(browser)
    assert_in_created_utub(browser)


def test_select_member_utub_from_created_utub(
    browser: WebDriver, create_test_tags, provide_app: Flask
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

    login_user_to_home_page(app, browser, user_id_for_test)
    login_user_and_select_utub_by_utubid(
        app, browser, user_id_for_test, utub_user_did_create.id
    )
    assert_utub_selected(browser, app, utub_user_did_create.id)

    select_utub_by_id(browser, utub_user_did_not_create.id)
    assert_utub_selected(browser, app, utub_user_did_not_create.id)
    assert_url_coloring_is_correct(browser)
    assert_in_member_utub(browser)


def test_select_created_utub_from_member_utub(
    browser: WebDriver, create_test_tags, provide_app: Flask
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
        app, browser, user_id_for_test, utub_user_did_not_create.id
    )
    assert_utub_selected(browser, app, utub_user_did_not_create.id)

    select_utub_by_id(browser, utub_user_did_create.id)
    assert_utub_selected(browser, app, utub_user_did_create.id)
    assert_url_coloring_is_correct(browser)
    assert_in_created_utub(browser)


def test_select_utub_rate_limits(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    GIVEN a fresh load of the U4i Home page, where user is in multiple UTubs, but they are rate limited
    WHEN user clicks one of the UTubs
    THEN ensure the 429 error page is shown
    """

    app = provide_app
    user_id_for_test = 1
    utub_user_did_not_create = get_utub_this_user_did_not_create(app, user_id_for_test)

    login_user_to_home_page(app, browser, user_id_for_test)
    utub_selector = f"{HPL.SELECTORS_UTUB}[utubid='{utub_user_did_not_create.id}']"

    utub_selector_elem = wait_for_element_presence(browser, utub_selector, timeout=10)

    assert utub_selector_elem is not None

    add_forced_rate_limit_header(browser)
    wait_then_click_element(browser, utub_selector, time=3)

    assert_on_429_page(browser)
