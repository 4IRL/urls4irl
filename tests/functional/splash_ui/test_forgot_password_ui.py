# Standard libraries
from time import sleep

# External libraries
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver

# Internal libraries
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.locators import ModalLocators as ML
from tests.functional.locators import SplashPageLocators as SPL
from tests.functional.splash_ui.utils_for_test_splash_ui import (
    assert_forgot_password_modal_open,
    assert_forgot_password_submission,
    open_forgot_password_modal,
)
from tests.functional.utils_for_test import (
    clear_then_send_keys,
    wait_then_click_element,
    wait_then_get_element,
    dismiss_modal_with_click_out,
    wait_until_hidden,
)

pytestmark = pytest.mark.splash_ui


def test_open_forgot_password_modal(browser: WebDriver):
    """
    Tests a user's ability to request a password reminder

    GIVEN a fresh load of the U4I Splash page
    WHEN user opens the login, clicks the 'Forgot Password' link, and enters their email
    THEN the modal responds with an affirmation of reminder sent
    """
    open_forgot_password_modal(browser)

    assert_forgot_password_modal_open(browser)

    email_input = wait_then_get_element(browser, SPL.INPUT_EMAIL)
    assert email_input is not None
    clear_then_send_keys(email_input, UTS.TEST_PASSWORD_1)

    wait_then_click_element(browser, SPL.BUTTON_SUBMIT)

    modal_alert = wait_then_get_element(browser, SPL.SPLASH_MODAL_ALERT)
    assert modal_alert is not None

    assert (
        modal_alert.text
        == "If you entered a valid email, you should receive a reset password link soon."
    )

    submit_btn = wait_then_get_element(browser, SPL.BUTTON_SUBMIT)
    assert submit_btn is not None

    assert submit_btn.get_attribute("disabled")


def test_dismiss_forgot_password_modal_click(browser: WebDriver):
    """
    Tests a user's ability to close the splash page login modal by clicking outside of the modal

    GIVEN a fresh load of the U4I Splash page
    WHEN user opens the login, then clicks anywhere outside of the modal
    THEN the modal is closed
    """
    open_forgot_password_modal(browser)

    dismiss_modal_with_click_out(browser)

    modal_element = wait_until_hidden(browser, SPL.SPLASH_MODAL)

    assert not modal_element.is_displayed()


def test_dismiss_forgot_password_modal_x(browser: WebDriver):
    """
    Tests a user's ability to close the splash page login modal by clicking the 'x' button in the upper right hand corner

    GIVEN a fresh load of the U4I Splash page
    WHEN user opens the login, then clicks the 'x' of the modal
    THEN the modal is closed
    """
    open_forgot_password_modal(browser)

    sleep(2)

    wait_then_click_element(browser, ML.BUTTON_X_MODAL_DISMISS)

    modal_element = wait_until_hidden(browser, SPL.SPLASH_MODAL)

    assert not modal_element.is_displayed()


def test_dismiss_forgot_password_modal_key(browser: WebDriver):
    """
    Tests a user's ability to close the splash page login modal by pressing the Esc key

    GIVEN a fresh load of the U4I Splash page
    WHEN user opens the login, then presses the Esc key
    THEN the modal is closed
    """
    open_forgot_password_modal(browser)

    sleep(2)

    splash_modal = wait_then_get_element(browser, SPL.SPLASH_MODAL)

    splash_modal.send_keys(Keys.ESCAPE)

    modal_element = wait_until_hidden(browser, SPL.SPLASH_MODAL)

    assert not modal_element.is_displayed()


def test_submit_forgot_password_modal_btn(browser: WebDriver):
    """
    Tests a user's ability to request a password reminder

    GIVEN a fresh load of the U4I Splash page
    WHEN user opens the login, clicks the 'Forgot Password' link, and enters their email
    THEN the modal responds with an affirmation of reminder sent
    """
    open_forgot_password_modal(browser)

    email_input = wait_then_get_element(browser, SPL.INPUT_EMAIL)
    assert email_input is not None
    clear_then_send_keys(email_input, UTS.TEST_PASSWORD_1)

    wait_then_click_element(browser, SPL.BUTTON_SUBMIT)

    assert_forgot_password_submission(browser)


def test_submit_forgot_password_modal_key(browser: WebDriver):
    """
    Tests a user's ability to request a password reminder

    GIVEN a fresh load of the U4I Splash page
    WHEN user opens the login, clicks the 'Forgot Password' link, and enters their email
    THEN the modal responds with an affirmation of reminder sent
    """
    open_forgot_password_modal(browser)

    email_input = wait_then_get_element(browser, SPL.INPUT_EMAIL)
    assert email_input is not None
    clear_then_send_keys(email_input, UTS.TEST_PASSWORD_1)

    browser.switch_to.active_element.send_keys(Keys.ENTER)

    assert_forgot_password_submission(browser)


# @pytest.mark.skip(reason="Not yet implemented on frontend.")
def test_forgot_password_to_login_modal_btn(browser: WebDriver):
    """
    Tests a user's ability to change view from the Forgot Password modal to the Login modal

    GIVEN a fresh load of the U4I Splash page
    WHEN user opens Login, then Frogot Password modal and wants to change back to Login
    THEN ensure the modal view changes appropriately
    """
    open_forgot_password_modal(browser)

    wait_then_click_element(browser, SPL.BUTTON_LOGIN_FROM_FORGOT_PASSWORD)

    modal_element = wait_then_get_element(browser, SPL.SPLASH_MODAL)
    assert modal_element is not None

    modal_title = modal_element.find_element(By.CLASS_NAME, "modal-title")

    assert modal_title.text == "Login!"


@pytest.mark.skip(reason="Not happy path.")
def test_forgot_password_empty_field(browser: WebDriver):
    """
    Tests site response to an empty submission of the email field in the Forgot Password modal

    GIVEN a fresh load of the U4I Splash page
    WHEN user opens the login, clicks the 'Forgot Password' link, clicks submit
    THEN the modal responds with a suggestion to try again
    """
    open_forgot_password_modal(browser)

    wait_then_click_element(browser, SPL.BUTTON_SUBMIT, 5)

    modal_element = wait_then_get_element(browser, SPL.SPLASH_MODAL)
    assert modal_element is not None

    error = modal_element.find_element(By.CLASS_NAME, "invalid-feedback")

    assert error.text == "This field is required."


@pytest.mark.skip(reason="Not happy path.")
def test_forgot_password_invalid_email(browser: WebDriver):
    """
    Tests site response to a non-email submission of the email field in the Forgot Password modal

    GIVEN a fresh load of the U4I Splash page
    WHEN user opens the login, clicks the 'Forgot Password' link, types a non-email format string and clicks submit
    THEN the modal responds with a suggestion to try again
    """
    open_forgot_password_modal(browser)

    wait_then_click_element(browser, SPL.BUTTON_SUBMIT, 5)

    modal_element = wait_then_get_element(browser, SPL.SPLASH_MODAL)
    assert modal_element is not None

    error = modal_element.find_element(By.CLASS_NAME, "invalid-feedback")

    assert error.text == "Invalid email address."
