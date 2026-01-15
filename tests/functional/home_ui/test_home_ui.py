from flask import Flask
import pytest
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC

from src.models.utub_members import Utub_Members
from src.models.utubs import Utubs
from src.utils.strings.html_identifiers import IDENTIFIERS
from tests.functional.assert_utils import (
    assert_login,
    assert_no_utub_selected,
    assert_utub_icon,
    assert_utub_selected,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.locators import SplashPageLocators as SPL
from tests.functional.login_utils import (
    create_user_session_and_provide_session_id,
    login_user_and_select_utub_by_name,
    login_user_with_cookie_from_session,
)
from tests.functional.selenium_utils import (
    ChromeRemoteWebDriver,
    login_user_ui,
    select_utub_by_id,
    wait_for_element_to_be_removed,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_hidden,
    wait_until_utub_name_appears,
)
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS

pytestmark = pytest.mark.home_ui


def test_logout(browser: WebDriver, create_test_users, provide_app: Flask):
    """
    Tests a user's ability to logout.

    GIVEN a fresh load of the U4I Home page
    WHEN user clicks the upper RHS logout button
    THEN ensure the U4I Splash page is displayed
    """
    app = provide_app
    user_id = 1
    session_id = create_user_session_and_provide_session_id(app, user_id)
    login_user_with_cookie_from_session(browser, session_id)

    logout_btn = wait_then_get_element(browser, HPL.BUTTON_LOGOUT)
    assert logout_btn is not None
    logout_btn.click()

    assert EC.staleness_of(logout_btn)

    welcome_text = wait_then_get_element(browser, SPL.WELCOME_TEXT)
    assert welcome_text is not None

    assert welcome_text.text == IDENTIFIERS.SPLASH_PAGE

    navbar = wait_then_get_element(browser, SPL.SPLASH_NAVBAR)
    assert navbar is not None

    login_btn = navbar.find_element(By.CSS_SELECTOR, SPL.NAVBAR_LOGIN)

    assert login_btn.is_displayed()


def test_refresh_logo(browser: WebDriver, create_test_utubs, provide_app: Flask):
    """
    Tests a user's ability to refresh the U4I Home page by clicking the upper LHS logo.

    GIVEN a fresh load of the U4I Home page, and any item selected
    WHEN user clicks upper LHS logo
    THEN ensure the Home page is re-displayed with nothing selected
    """

    app = provide_app
    user_id = 1
    login_user_and_select_utub_by_name(app, browser, user_id, UTS.TEST_UTUB_NAME_1)

    wait_then_click_element(browser, HPL.U4I_LOGO)

    assert_login(browser)

    active_utubs = wait_then_get_element(browser, HPL.SELECTOR_SELECTED_UTUB, time=3)
    assert active_utubs is None


def test_back_and_forward_history(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    GIVEN a set of UTubs with URLs, member, and tags within that UTub
    WHEN the user selects each UTub 1 by 1, then uses browser back and then forward history
    THEN verify that each UTub is shown in the order it was clicked
    """
    app = provide_app
    user_id = 1
    session_id = create_user_session_and_provide_session_id(app, user_id)
    login_user_with_cookie_from_session(browser, session_id)

    with app.app_context():
        utub_members_with_user: list[Utub_Members] = Utub_Members.query.filter(
            Utub_Members.user_id == user_id
        ).all()
        utub_ids: list[int] = [
            utub_member.utub_id for utub_member in utub_members_with_user
        ]

    for utub_id in utub_ids:
        select_utub_by_id(browser, utub_id)

    # Go backwards
    for idx in range(len(utub_ids)):
        utub_idx = len(utub_ids) - idx - 1
        utub_id = utub_ids[utub_idx]

        assert_utub_selected(browser, app, utub_id)
        assert_utub_icon(browser, app, user_id, utub_id)

        browser.back()

    assert_no_utub_selected(browser)

    # Go forwards
    for utub_id in utub_ids:
        browser.forward()

        assert_utub_selected(browser, app, utub_id)
        assert_utub_icon(browser, app, user_id, utub_id)


def test_back_and_forward_history_with_one_utub_deleted(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    GIVEN a set of UTubs with URLs, member, and tags within that UTub
    WHEN the user selects each UTub 1 by 1, then deletes a UTub, then uses the browser back and forward history
    THEN verify that each UTub is shown in the order it was clicked, and the deleted
        UTub shows no UTub selected
    """
    app = provide_app
    user_id = 3
    session_id = create_user_session_and_provide_session_id(app, user_id)
    login_user_with_cookie_from_session(browser, session_id)

    with app.app_context():
        utub_members_with_user: list[Utub_Members] = Utub_Members.query.filter(
            Utub_Members.user_id == user_id
        ).all()
        utub_ids: list[int] = [
            utub_member.utub_id for utub_member in utub_members_with_user
        ]
        utub_user_created: Utubs = Utubs.query.filter(
            Utubs.utub_creator == user_id
        ).first()
        utub_id_to_delete = utub_user_created.id

    # Sort the UTubIDs so the 3rd UTub (the one this user created) is right in the middle
    utub_ids.sort()
    for utub_id in utub_ids:
        select_utub_by_id(browser, utub_id)

    select_utub_by_id(browser, utub_id_to_delete)

    wait_then_click_element(browser, HPL.BUTTON_UTUB_DELETE, time=3)

    wait_then_click_element(browser, HPL.BUTTON_MODAL_SUBMIT, time=3)

    # Wait for DELETE request
    wait_until_hidden(browser, HPL.BUTTON_MODAL_SUBMIT, timeout=3)
    css_selector = f'{HPL.SELECTORS_UTUB}[utubid="{utub_id_to_delete}"]'
    utub_selector = browser.find_element(By.CSS_SELECTOR, css_selector)
    wait_for_element_to_be_removed(browser, utub_selector)

    # Assert UTub selector no longer exists
    with pytest.raises(NoSuchElementException):
        browser.find_element(By.CSS_SELECTOR, css_selector)

    assert_no_utub_selected(browser)

    # Start at the end of the selected UTubs again
    utub_ids.append(utub_id_to_delete)

    # Go backwards
    for idx in range(len(utub_ids)):
        browser.back()
        utub_idx = -1 - idx
        utub_id = utub_ids[utub_idx]

        if utub_id == utub_id_to_delete:
            assert_no_utub_selected(browser)
            continue

        with app.app_context():
            utub: Utubs = Utubs.query.get(utub_id)
            wait_until_utub_name_appears(browser, utub.name)

        assert_utub_selected(browser, app, utub_id)
        assert_utub_icon(browser, app, user_id, utub_id)

    # Go back to the home page when no UTubs were selected
    browser.back()
    assert_no_utub_selected(browser)

    # Go forwards
    for utub_id in utub_ids:
        browser.forward()

        if utub_id == utub_id_to_delete:
            assert_no_utub_selected(browser)
            continue

        assert_utub_selected(browser, app, utub_id)
        assert_utub_icon(browser, app, user_id, utub_id)


def test_back_and_forward_history_with_leaving_one_utub(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    GIVEN a set of UTubs with URLs, member, and tags within that UTub
    WHEN the user selects each UTub 1 by 1, then removes themself from UTub, then uses the browser back and forward history
    THEN verify that each UTub is shown in the order it was clicked, and the UTub they left shows no UTub selected
    """
    app = provide_app
    user_id = 1
    session_id = create_user_session_and_provide_session_id(app, user_id)
    login_user_with_cookie_from_session(browser, session_id)

    with app.app_context():
        utub_members_with_user: list[Utub_Members] = Utub_Members.query.filter(
            Utub_Members.user_id == user_id
        ).all()
        utub_ids: list[int] = [
            utub_member.utub_id for utub_member in utub_members_with_user
        ]
    utub_id_to_delete = 3
    assert utub_id_to_delete in utub_ids

    # Sort the UTubIDs so the 3rd UTub (the one this user is a member of) is right in the middle
    utub_ids.sort()
    for utub_id in utub_ids:
        select_utub_by_id(browser, utub_id)

    select_utub_by_id(browser, utub_id_to_delete)
    wait_then_click_element(browser, HPL.BUTTON_UTUB_LEAVE, time=3)
    warning_modal_body = wait_then_get_element(browser, HPL.BODY_MODAL)
    assert warning_modal_body is not None

    # Wait for DELETE request
    wait_then_click_element(browser, HPL.BUTTON_MODAL_SUBMIT, time=3)
    wait_until_hidden(browser, HPL.BUTTON_MODAL_SUBMIT, timeout=3)
    utub_css_selector = f"{HPL.SELECTORS_UTUB}[utubid='{utub_id_to_delete}']"
    utub_selector = browser.find_element(By.CSS_SELECTOR, utub_css_selector)
    wait_for_element_to_be_removed(browser, utub_selector)

    # Assert UTub selector no longer exists
    with pytest.raises(NoSuchElementException):
        browser.find_element(By.CSS_SELECTOR, utub_css_selector)

    assert_no_utub_selected(browser)

    # Start at the end of the selected UTubs again
    utub_ids.append(utub_id_to_delete)

    # Go backwards
    for idx in range(len(utub_ids)):
        browser.back()
        utub_idx = -1 - idx
        utub_id = utub_ids[utub_idx]

        if utub_id == utub_id_to_delete:
            assert_no_utub_selected(browser)
            continue

        with app.app_context():
            utub: Utubs = Utubs.query.get(utub_id)
            wait_until_utub_name_appears(browser, utub.name)

        assert_utub_selected(browser, app, utub_id)
        assert_utub_icon(browser, app, user_id, utub_id)

    # Go back to the home page when no UTubs were selected
    browser.back()
    assert_no_utub_selected(browser)

    # Go forwards
    for utub_id in utub_ids:
        browser.forward()

        if utub_id == utub_id_to_delete:
            assert_no_utub_selected(browser)
            continue

        assert_utub_selected(browser, app, utub_id)
        assert_utub_icon(browser, app, user_id, utub_id)


def test_access_utub_id_via_url_logged_in(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    GIVEN a set of UTubs with URLs, member, and tags within that UTub, and the user has previously logged in
        and therefore has a session cookie
    WHEN the user accesses the URL with the given query parameter UTubID=X, where X is a given UTubID
    THEN verify that the UTub with the given UTubID is selected when the browser is shown
    """
    app = provide_app
    user_id = 1
    session_id = create_user_session_and_provide_session_id(app, user_id)
    login_user_with_cookie_from_session(browser, session_id)

    with app.app_context():
        utub_not_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator != user_id
        ).first()
        utub_id_to_select = utub_not_creator_of.id
        utub_name_to_select = utub_not_creator_of.name

    utub_url = f"{browser.current_url}?UTubID={utub_id_to_select}"
    browser.get(utub_url)
    wait_until_utub_name_appears(browser, utub_name_to_select)
    assert_utub_selected(browser, app, utub_id_to_select)


def test_access_utub_id_via_url_logged_out(
    browser: ChromeRemoteWebDriver, create_test_tags, provide_app: Flask
):
    """
    GIVEN a set of UTubs with URLs, member, and tags within that UTub, and the user has no session cookie
    WHEN the user accesses the URL with the given query parameter UTubID=X, where X is a given UTubID
    THEN verify that the UTub with the given UTubID is selected when the browser is shown after logging in
    """
    app = provide_app
    user_id = 1
    with app.app_context():
        utub_not_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator != user_id
        ).first()
        utub_id_to_select = utub_not_creator_of.id
        utub_name_to_select = utub_not_creator_of.name

    utub_url = f"{browser.current_url}home?UTubID={utub_id_to_select}"
    browser.get(utub_url)
    login_user_ui(browser)

    # Find submit button to login
    wait_then_click_element(browser, SPL.BUTTON_SUBMIT)
    wait_until_utub_name_appears(browser, utub_name_to_select)

    assert_utub_selected(browser, app, utub_id_to_select)


# TODO: test async addition of component by 2nd test user in a shared UTub, then confirm 1st test user can see the update upon refresh
