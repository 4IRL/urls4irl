from flask import Flask
import pytest
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver

from src import db
from src.models.users import Users
from src.models.utub_members import Utub_Members
from src.models.utubs import Utubs
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from src.utils.strings.utub_strs import (
    UTUB_CREATE_MSG,
    UTUB_DELETE_WARNING,
    UTUB_SELECT,
)
from tests.functional.assert_utils import (
    assert_active_utub,
    assert_login_with_username,
    assert_visited_403_on_invalid_csrf_and_reload,
)
from tests.functional.db_utils import get_utub_this_user_created
from tests.functional.locators import ModalLocators as ML
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.login_utils import login_user_and_select_utub_by_name
from tests.functional.selenium_utils import (
    dismiss_modal_with_click_out,
    get_selected_utub_id,
    invalidate_csrf_token_on_page,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_hidden,
    wait_until_visible_css_selector,
)
from tests.functional.utubs_ui.assert_utils import (
    assert_elems_hidden_after_utub_deleted,
)
from tests.functional.utubs_ui.selenium_utils import delete_utub_as_creator

pytestmark = pytest.mark.utubs_ui


def test_open_delete_utub_modal(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a user on their Home page
    WHEN they select a UTub and click the Trash can icon
    THEN ensure the warning modal is shown
    """

    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app, browser, user_id_for_test, utub_user_created.name
    )

    utub_delete_btn = wait_then_get_element(browser, HPL.BUTTON_UTUB_DELETE, time=3)
    assert utub_delete_btn is not None
    assert utub_delete_btn.is_displayed()

    utub_delete_btn.click()

    warning_modal_body = wait_then_get_element(browser, HPL.BODY_MODAL, time=3)
    assert warning_modal_body is not None

    confirmation_modal_body_text = warning_modal_body.get_attribute("innerText")

    # Assert warning modal appears with appropriate text
    assert confirmation_modal_body_text == UTUB_DELETE_WARNING


def test_dismiss_delete_utub_modal_x(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a user on their Home page
    WHEN they select a UTub, click the Trash can icon, then clicks the 'x'
    THEN ensure the warning modal is hidden
    """

    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app, browser, user_id_for_test, utub_user_created.name
    )

    delete_utub_modal = browser.find_element(By.CSS_SELECTOR, HPL.HOME_MODAL)
    assert not delete_utub_modal.is_displayed()

    wait_then_click_element(browser, HPL.BUTTON_UTUB_DELETE, time=3)

    wait_then_click_element(browser, ML.BUTTON_X_MODAL_DISMISS, time=3)

    modal_element = wait_until_hidden(browser, HPL.HOME_MODAL, timeout=3)

    assert not modal_element.is_displayed()


def test_dismiss_delete_utub_modal_btn(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a user on their Home page
    WHEN they select a UTub, click the Trash can icon, then clicks the 'Nevermind...' button
    THEN ensure the warning modal is hidden
    """

    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app, browser, user_id_for_test, utub_user_created.name
    )

    delete_utub_modal = browser.find_element(By.CSS_SELECTOR, HPL.HOME_MODAL)
    assert not delete_utub_modal.is_displayed()

    wait_then_click_element(browser, HPL.BUTTON_UTUB_DELETE, time=3)

    wait_then_click_element(browser, ML.BUTTON_MODAL_DISMISS)

    modal_element = wait_until_hidden(browser, HPL.HOME_MODAL)

    assert not modal_element.is_displayed()


def test_dismiss_delete_utub_modal_key(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a user on their Home page
    WHEN they select a UTub, click the Trash can icon, then presses 'Esc'
    THEN ensure the warning modal is hidden
    """

    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app, browser, user_id_for_test, utub_user_created.name
    )

    with app.app_context():
        utub: Utubs = Utubs.query.filter(Utubs.name == UTS.TEST_UTUB_NAME_1).first()
        assert utub.utub_creator == user_id_for_test

    delete_utub_modal = browser.find_element(By.CSS_SELECTOR, HPL.HOME_MODAL)
    assert not delete_utub_modal.is_displayed()

    wait_then_click_element(browser, HPL.BUTTON_UTUB_DELETE, time=3)

    wait_until_visible_css_selector(browser, HPL.HOME_MODAL, timeout=3)

    browser.find_element(By.CSS_SELECTOR, HPL.HOME_MODAL).send_keys(Keys.ESCAPE)

    modal_element = wait_until_hidden(browser, HPL.HOME_MODAL)

    assert not modal_element.is_displayed()


def test_dismiss_delete_utub_modal_click(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a user on their Home page
    WHEN they select a UTub, click the Trash can icon, then clicks anywhere outside of the modal
    THEN ensure the warning modal is hidden
    """

    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app, browser, user_id_for_test, utub_user_created.name
    )

    wait_then_click_element(browser, HPL.BUTTON_UTUB_DELETE, time=3)

    dismiss_modal_with_click_out(browser)

    modal_element = wait_until_hidden(browser, HPL.HOME_MODAL, timeout=3)

    assert not modal_element.is_displayed()


def test_delete_utub_btn(browser: WebDriver, create_test_utubs, provide_app: Flask):
    """
    GIVEN a user trying to delete one of the UTubs they created
    WHEN they try to delete the UTub
    THEN ensure the UTub selector is removed, and all relevant buttons are hidden
    """

    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app, browser, user_id_for_test, utub_user_created.name
    )

    utub_id = get_selected_utub_id(browser)
    css_selector = f'{HPL.SELECTORS_UTUB}[utubid="{utub_id}"]'

    assert browser.find_element(By.CSS_SELECTOR, css_selector)

    delete_utub_as_creator(browser, utub_user_created)

    # Assert UTub selector no longer exists
    with pytest.raises(NoSuchElementException):
        css_selector = f'{HPL.SELECTORS_UTUB}[utubid="{utub_id}"]'
        browser.find_element(By.CSS_SELECTOR, css_selector)

    # Assert that the no utub selected UI is shown
    assert_elems_hidden_after_utub_deleted(browser)


def test_delete_last_utub_no_urls_no_tags_no_members(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a user has one UTub with no URLs, tags, or member
    WHEN they delete the UTub
    THEN ensure the main page shows appropriate prompts to create a new UTub
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app, browser, user_id_for_test, utub_user_created.name
    )

    delete_utub_as_creator(browser, utub_user_created)

    # Make sure all relevant buttons and subheaders are hidden when no UTub selected
    assert_elems_hidden_after_utub_deleted(browser)

    assert (
        browser.find_element(By.CSS_SELECTOR, HPL.SUBHEADER_URL_DECK).text
        == UTUB_SELECT
    )
    assert (
        browser.find_element(By.CSS_SELECTOR, HPL.SUBHEADER_UTUB_DECK).text
        == UTUB_CREATE_MSG
    )


def test_delete_last_utub_with_urls_tags_members(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    GIVEN a user has one UTub with no URLs, tags, or member
    WHEN they delete the UTub
    THEN ensure the main page shows appropriate prompts to create a new UTub
    """
    app = provide_app
    user_id_for_test = 1

    utub_user_created = get_utub_this_user_created(app, user_id_for_test)

    with app.app_context():
        Utub_Members.query.filter(
            Utub_Members.user_id == user_id_for_test,
            Utub_Members.utub_id != utub_user_created.id,
        ).delete()
        db.session.commit()

    login_user_and_select_utub_by_name(
        app, browser, user_id_for_test, utub_user_created.name
    )

    delete_utub_as_creator(browser, utub_user_created)

    # Make sure all relevant buttons and subheaders are hidden when no UTub selected
    assert_elems_hidden_after_utub_deleted(browser)

    assert (
        browser.find_element(By.CSS_SELECTOR, HPL.SUBHEADER_URL_DECK).text
        == UTUB_SELECT
    )
    assert (
        browser.find_element(By.CSS_SELECTOR, HPL.SUBHEADER_UTUB_DECK).text
        == UTUB_CREATE_MSG
    )

    assert len(browser.find_elements(By.CSS_SELECTOR, HPL.SELECTORS_UTUB)) == 0
    assert len(browser.find_elements(By.CSS_SELECTOR, HPL.BADGES_MEMBERS)) == 0
    assert len(browser.find_elements(By.CSS_SELECTOR, HPL.TAG_FILTERS)) == 0
    assert len(browser.find_elements(By.CSS_SELECTOR, HPL.ROWS_URLS)) == 0


def test_delete_utub_invalid_csrf_token(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a user trying to delete one of the UTubs they created with an invalid CSRF token
    WHEN they try to delete the UTub with an invalid CSRF token
    THEN ensure U4I responds with a proper error message
    """

    app = provide_app
    user_id_for_test = 1
    with app.app_context():
        user: Users = Users.query.get(user_id_for_test)
        username = user.username
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app, browser, user_id_for_test, utub_user_created.name
    )

    utub_id = get_selected_utub_id(browser)
    css_selector = f'{HPL.SELECTORS_UTUB}[utubid="{utub_id}"]'

    assert browser.find_element(By.CSS_SELECTOR, css_selector)
    wait_then_click_element(browser, HPL.BUTTON_UTUB_DELETE, time=3)

    invalidate_csrf_token_on_page(browser)
    wait_then_click_element(browser, HPL.BUTTON_MODAL_SUBMIT, time=3)

    assert_visited_403_on_invalid_csrf_and_reload(browser)

    # Page reloads after user clicks button in CSRF 403 error page
    assert_login_with_username(browser, username)

    # Reload will bring user back to the UTub they were in before
    assert_active_utub(browser, utub_user_created.name)

    delete_utub_submit_btn_modal = wait_until_hidden(
        browser, HPL.BUTTON_MODAL_SUBMIT, timeout=3
    )
    assert not delete_utub_submit_btn_modal.is_displayed()
