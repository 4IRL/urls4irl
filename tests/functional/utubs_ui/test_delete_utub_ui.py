# Standard library
from time import sleep

# External libraries
import pytest
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver

# Internal libraries
from src.mocks.mock_constants import MOCK_UTUB_NAME_BASE
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.locators import ModalLocators as ML
from tests.functional.locators import MainPageLocators as MPL
from tests.functional.urls_ui.utils_for_test_url_ui import get_selected_utub_id
from tests.functional.utils_for_test import (
    dismiss_modal_with_click_out,
    get_all_utub_selector_names,
    login_user,
    login_utub,
    select_utub_by_name,
    user_is_selected_utub_owner,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_hidden,
)

pytestmark = pytest.mark.utubs_ui


def test_open_delete_utub_modal(browser: WebDriver, create_test_utubs):
    """
    GIVEN a user on their Home page
    WHEN they select a UTub and click the Trash can icon
    THEN ensure the warning modal is shown
    """

    login_utub(browser)

    if user_is_selected_utub_owner(browser):
        wait_then_click_element(browser, MPL.BUTTON_UTUB_DELETE)

    warning_modal_body = wait_then_get_element(browser, MPL.BODY_MODAL)
    confirmation_modal_body_text = warning_modal_body.get_attribute("innerText")

    # Assert warning modal appears with appropriate text
    assert confirmation_modal_body_text == UTS.BODY_MODAL_UTUB_DELETE


def test_dismiss_delete_utub_modal_x(browser: WebDriver, create_test_utubs):
    """
    GIVEN a user on their Home page
    WHEN they select a UTub, click the Trash can icon, then clicks the 'x'
    THEN ensure the warning modal is hidden
    """

    login_utub(browser)

    if user_is_selected_utub_owner(browser):
        wait_then_click_element(browser, MPL.BUTTON_UTUB_DELETE)

    wait_then_click_element(browser, ML.BUTTON_X_MODAL_DISMISS)

    modal_element = wait_until_hidden(browser, MPL.HOME_MODAL)

    assert not modal_element.is_displayed()


def test_dismiss_delete_utub_modal_btn(browser: WebDriver, create_test_utubs):
    """
    GIVEN a user on their Home page
    WHEN they select a UTub, click the Trash can icon, then clicks the 'Nevermind...' button
    THEN ensure the warning modal is hidden
    """

    login_utub(browser)

    if user_is_selected_utub_owner(browser):
        wait_then_click_element(browser, MPL.BUTTON_UTUB_DELETE)

    wait_then_click_element(browser, ML.BUTTON_MODAL_DISMISS)

    modal_element = wait_until_hidden(browser, MPL.HOME_MODAL)

    assert not modal_element.is_displayed()


def test_dismiss_delete_utub_modal_key(browser: WebDriver, create_test_utubs):
    """
    GIVEN a user on their Home page
    WHEN they select a UTub, click the Trash can icon, then presses 'Esc'
    THEN ensure the warning modal is hidden
    """

    login_utub(browser)

    if not user_is_selected_utub_owner(browser):
        utub_selector_names = get_all_utub_selector_names(browser)
        select_utub_by_name(browser, utub_selector_names[0])

    wait_then_click_element(browser, MPL.BUTTON_UTUB_DELETE)

    sleep(4)

    browser.find_element(By.CSS_SELECTOR, MPL.HOME_MODAL).send_keys(Keys.ESCAPE)

    modal_element = wait_until_hidden(browser, MPL.HOME_MODAL)

    assert not modal_element.is_displayed()


def test_dismiss_delete_utub_modal_click(browser: WebDriver, create_test_utubs):
    """
    GIVEN a user on their Home page
    WHEN they select a UTub, click the Trash can icon, then clicks anywhere outside of the modal
    THEN ensure the warning modal is hidden
    """

    login_utub(browser)

    if user_is_selected_utub_owner(browser):
        wait_then_click_element(browser, MPL.BUTTON_UTUB_DELETE)

    dismiss_modal_with_click_out(browser)

    modal_element = wait_until_hidden(browser, MPL.HOME_MODAL)

    assert not modal_element.is_displayed()


# @pytest.mark.skip(reason="Testing another in isolation")
def test_delete_utub_btn(browser: WebDriver, create_test_utubs):
    """
    GIVEN a user trying to add a new UTub
    WHEN they submit the addUTub form
    THEN ensure the appropriate input field is shown and in focus
    """

    login_utub(browser)

    assert user_is_selected_utub_owner(browser)
    utub_id = get_selected_utub_id(browser)
    css_selector = f'{MPL.SELECTORS_UTUB}[utubid="{utub_id}"]'
    assert browser.find_element(By.CSS_SELECTOR, css_selector)
    wait_then_click_element(browser, MPL.BUTTON_UTUB_DELETE)

    wait_then_click_element(browser, MPL.BUTTON_MODAL_SUBMIT)

    # Wait for DELETE request
    sleep(4)

    # Assert UTub selector no longer exists
    with pytest.raises(NoSuchElementException):
        css_selector = f'{MPL.SELECTORS_UTUB}[utubid="{utub_id}"]'
        assert browser.find_element(By.CSS_SELECTOR, css_selector)


@pytest.mark.skip(reason="Test not yet implemented")
def test_delete_last_utub(browser: WebDriver, create_test_utubs):
    """
    GIVEN a user has one UTub
    WHEN they delete the UTub
    THEN ensure the main page shows appropriate prompts to create a new UTub
    """

    login_user(browser)

    # Extract confirming result
    selector_UTub1 = wait_then_get_element(browser, MPL.SELECTOR_SELECTED_UTUB)

    # Assert new UTub selector was created with input UTub Name
    assert selector_UTub1.text == MOCK_UTUB_NAME_BASE + "1"
    # Assert new UTub is now active and displayed to user
    assert "active" in selector_UTub1.get_attribute("class")
