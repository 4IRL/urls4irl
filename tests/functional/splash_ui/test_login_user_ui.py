# Standard libraries

# External libraries
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver

# Internal libraries
from tests.functional.locators import ModalLocators as ML
from tests.functional.locators import SplashPageLocators as SPL
from tests.functional.utils_for_test import (
    assert_login,
    login_user,
    wait_then_click_element,
    wait_then_get_element,
    dismiss_modal_with_click_out,
    wait_until_hidden,
    wait_until_visible_css_selector,
)

pytestmark = pytest.mark.splash_ui


def test_example(browser: WebDriver):
    """
    The one test that will always work to make me feel good
    """
    # Check if the title contains "URLS4IRL"
    assert "URLS4IRL" in browser.title


def test_open_login_modal_center_btn(browser: WebDriver):
    """
    Tests a user's ability to open the Login modal using the center button.

    GIVEN a fresh load of the U4I Splash page
    WHEN user clicks the center login button
    THEN ensure the modal opens
    """
    wait_then_click_element(browser, SPL.BUTTON_LOGIN)
    modal_element = wait_then_get_element(browser, SPL.SPLASH_MODAL)
    assert modal_element is not None

    assert modal_element.is_displayed()

    modal_title = modal_element.find_element(By.CLASS_NAME, "modal-title")

    assert modal_title.text == "Login!"


def test_open_login_modal_RHS_btn(browser: WebDriver):
    """
    Tests a user's ability to open the Login modal using the RHS corner button

    GIVEN a fresh load of the U4I Splash page
    WHEN user clicks the RHS login button
    THEN ensure the modal opens
    """

    # Find and click login button to open modal
    navbar = wait_then_get_element(browser, SPL.SPLASH_NAVBAR)
    assert navbar is not None

    login_btn = navbar.find_element(By.CSS_SELECTOR, SPL.BUTTON_LOGIN)
    login_btn.click()

    modal_element = wait_then_get_element(browser, SPL.SPLASH_MODAL)
    assert modal_element is not None

    assert modal_element.is_displayed()

    modal_title = modal_element.find_element(By.CLASS_NAME, "modal-title")

    assert modal_title.text == "Login!"


def test_register_to_login_modal_btn(browser: WebDriver):
    """
    Tests a user's ability to change view from the Register modal to the Login modal

    GIVEN a fresh load of the U4I Splash page
    WHEN user opens Register modal and wants to change to Login
    THEN ensure the modal view changes
    """
    wait_then_click_element(browser, SPL.BUTTON_REGISTER)
    wait_then_click_element(browser, SPL.BUTTON_LOGIN_FROM_REGISTER)
    wait_until_visible_css_selector(browser, SPL.BUTTON_FORGOT_PASSWORD_MODAL)

    modal_element = wait_then_get_element(browser, SPL.SPLASH_MODAL)
    assert modal_element is not None

    modal_title = modal_element.find_element(By.CLASS_NAME, "modal-title")

    assert modal_title.text == "Login!"


def test_dismiss_login_modal_btn(browser: WebDriver):
    """
    Tests a user's ability to close the splash page login modal by clicking the upper RHS 'x' button

    GIVEN a fresh load of the U4I Splash page
    WHEN user opens the login, then clicks the 'x'
    THEN the modal is closed
    """
    wait_then_click_element(browser, SPL.BUTTON_LOGIN)

    wait_then_click_element(browser, ML.BUTTON_MODAL_DISMISS)

    modal_element = wait_until_hidden(browser, SPL.SPLASH_MODAL)

    assert not modal_element.is_displayed()


def test_dismiss_login_modal_click(browser: WebDriver):
    """
    Tests a user's ability to close the splash page login modal by clicking outside of the modal

    GIVEN a fresh load of the U4I Splash page
    WHEN user opens the login, then clicks anywhere outside of the modal
    THEN the modal is closed
    """
    wait_then_click_element(browser, SPL.BUTTON_LOGIN)

    dismiss_modal_with_click_out(browser)

    modal_element = wait_until_hidden(browser, SPL.SPLASH_MODAL)

    assert not modal_element.is_displayed()


def test_dismiss_login_modal_x(browser: WebDriver):
    """
    Tests a user's ability to close the splash page login modal by clicking the 'x' button in the upper right hand corner

    GIVEN a fresh load of the U4I Splash page
    WHEN user opens the login, then clicks the 'x' of the modal
    THEN the modal is closed
    """
    wait_then_click_element(browser, SPL.BUTTON_LOGIN)

    wait_then_click_element(browser, SPL.BUTTON_X_MODAL_DISMISS)

    modal_element = wait_until_hidden(browser, SPL.SPLASH_MODAL)

    assert not modal_element.is_displayed()


def test_dismiss_login_modal_key(browser: WebDriver):
    """
    Tests a user's ability to close the splash page login modal by pressing the Esc key

    GIVEN a fresh load of the U4I Splash page
    WHEN user opens the login modal, then presses 'Esc'
    THEN the modal is closed
    """
    wait_then_click_element(browser, SPL.BUTTON_LOGIN)

    splash_modal = wait_then_get_element(browser, SPL.SPLASH_MODAL)

    splash_modal.send_keys(Keys.ESCAPE)

    modal_element = wait_until_hidden(browser, SPL.SPLASH_MODAL)

    assert not modal_element.is_displayed()


def test_login_test_user_btn(browser: WebDriver, create_test_users):
    """
    Tests a user's ability to login using the splash page login modal

    GIVEN a fresh load of the U4I Splash page and validated user
    WHEN user initiates login sequence
    THEN U4I will login user and display the home page
    """

    login_user(browser)

    # Find submit button to login
    wait_then_click_element(browser, SPL.BUTTON_SUBMIT)

    assert_login(browser)


def test_login_test_user_key(browser: WebDriver, create_test_users):
    """
    Tests a user's ability to login using the splash page login modal

    GIVEN a fresh load of the U4I Splash page and validated user
    WHEN user initiates login sequence
    THEN U4I will login user and display the home page
    """

    password_input = login_user(browser)

    # Submit form
    password_input.send_keys(Keys.ENTER)

    assert_login(browser)
