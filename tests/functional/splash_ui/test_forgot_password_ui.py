from datetime import datetime

from flask import Flask
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver

from src import db
from src.models.forgot_passwords import Forgot_Passwords
from src.utils.constants import USER_CONSTANTS
from src.utils.datetime_utils import utc_now
from src.utils.strings.email_validation_strs import EMAILS_FAILURE
from src.utils.strings.json_strs import FAILURE_GENERAL
from src.utils.strings.reset_password_strs import FORGOT_PASSWORD
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

    wait_then_click_element(browser, ML.BUTTON_X_MODAL_DISMISS, time=3)

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

    splash_modal = wait_then_get_element(browser, SPL.SPLASH_MODAL, time=3)
    assert splash_modal is not None

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


def test_forgot_password_empty_field(browser: WebDriver):
    """
    Tests site response to an empty submission of the email field in the Forgot Password modal

    GIVEN a fresh load of the U4I Splash page
    WHEN user opens the login, clicks the 'Forgot Password' link, clicks submit with an empty form
    THEN the modal responds with a suggestion to try again
    """
    open_forgot_password_modal(browser)

    wait_then_click_element(browser, SPL.BUTTON_SUBMIT, 3)

    feedback_elem = wait_then_get_element(browser, SPL.SUBHEADER_INVALID_FEEDBACK, 3)
    assert feedback_elem is not None
    assert feedback_elem.text == FAILURE_GENERAL.FIELD_REQUIRED_STR


def test_forgot_password_invalid_email(browser: WebDriver):
    """
    Tests site response to a non-email submission of the email field in the Forgot Password modal

    GIVEN a fresh load of the U4I Splash page
    WHEN user opens the login, clicks the 'Forgot Password' link, types a non-email format string and clicks submit
    THEN the modal responds with a suggestion to try again
    """
    open_forgot_password_modal(browser)
    input_elem = wait_then_get_element(browser, SPL.INPUT_EMAIL, 3)
    assert input_elem is not None
    input_elem.send_keys("abcdf")

    wait_then_click_element(browser, SPL.BUTTON_SUBMIT, 3)

    feedback_elem = wait_then_get_element(browser, SPL.SUBHEADER_INVALID_FEEDBACK, 3)
    assert feedback_elem is not None
    assert feedback_elem.text == EMAILS_FAILURE.INVALID_EMAIL_INPUT


def test_forgot_password_unconfirmed_email(
    browser: WebDriver, create_user_unconfirmed_email
):
    """
    Tests site response to a non-email submission of the email field in the Forgot Password modal

    GIVEN a fresh load of the U4I Splash page
    WHEN user opens the login, clicks the 'Forgot Password' link, types an email that hasn't been confirmed and hits submit
    THEN the modal responds with a success message
    """

    open_forgot_password_modal(browser)
    input_elem = wait_then_get_element(browser, SPL.INPUT_EMAIL, 3)
    assert input_elem is not None
    input_elem.send_keys(UTS.TEST_PASSWORD_1)

    wait_then_click_element(browser, SPL.BUTTON_SUBMIT, 3)
    alert_banner = wait_then_get_element(browser, SPL.SPLASH_MODAL_ALERT, 3)
    assert alert_banner is not None

    assert alert_banner.text == FORGOT_PASSWORD.EMAIL_SENT_MESSAGE


def test_forgot_password_nonexistent_email(browser: WebDriver):
    """
    Tests site response to a non-email submission of the email field in the Forgot Password modal

    GIVEN a fresh load of the U4I Splash page
    WHEN user opens the login, clicks the 'Forgot Password' link, types an email that isn't in the database and hits submit
    THEN the modal responds with a success message
    """

    open_forgot_password_modal(browser)
    input_elem = wait_then_get_element(browser, SPL.INPUT_EMAIL, 3)
    assert input_elem is not None
    input_elem.send_keys(UTS.TEST_PASSWORD_1)

    wait_then_click_element(browser, SPL.BUTTON_SUBMIT, 3)
    alert_banner = wait_then_get_element(browser, SPL.SPLASH_MODAL_ALERT, 3)
    assert alert_banner is not None

    assert alert_banner.text == FORGOT_PASSWORD.EMAIL_SENT_MESSAGE


def test_forgot_password_two_per_minute_rate_limit(
    browser: WebDriver, create_user_resetting_password, provide_app: Flask
):
    """
    Tests site response to user indicating forgot password more than twice per minute

    GIVEN a valid user requesting that they forgot their password
    WHEN user clicks the submit button on forgot password form after having done it twice already
    THEN ensure U4I responds with appropriate error message
    """
    open_forgot_password_modal(browser)
    input_elem = wait_then_get_element(browser, SPL.INPUT_EMAIL, 3)
    assert input_elem is not None
    input_elem.send_keys(UTS.TEST_PASSWORD_1)

    app = provide_app
    with app.app_context():
        forgot_password: Forgot_Passwords = Forgot_Passwords.query.first()
        forgot_password.last_attempt = datetime.fromtimestamp(
            int(datetime.timestamp(utc_now()))
        )
        initial_attempts = forgot_password.attempts
        db.session.commit()

    wait_then_click_element(browser, SPL.BUTTON_SUBMIT, 3)

    with app.app_context():
        forgot_password: Forgot_Passwords = Forgot_Passwords.query.first()
        assert initial_attempts == forgot_password.attempts


def test_forgot_password_five_per_hour_rate_limit(
    browser: WebDriver, create_user_resetting_password, provide_app: Flask
):
    """
    Tests site response to user indicating forgot password more than five times in one hour

    GIVEN a valid user requesting that they forgot their password
    WHEN user clicks the submit button on forgot password form after having done it five times in one hour
    THEN ensure U4I responds with appropriate error message
    """
    open_forgot_password_modal(browser)
    input_elem = wait_then_get_element(browser, SPL.INPUT_EMAIL, 3)
    assert input_elem is not None
    input_elem.send_keys(UTS.TEST_PASSWORD_1)

    app = provide_app
    with app.app_context():
        forgot_password: Forgot_Passwords = Forgot_Passwords.query.first()
        forgot_password.attempts = USER_CONSTANTS.PASSWORD_RESET_ATTEMPTS
        initial_attempts = forgot_password.attempts
        db.session.commit()

    wait_then_click_element(browser, SPL.BUTTON_SUBMIT, 3)

    with app.app_context():
        forgot_password: Forgot_Passwords = Forgot_Passwords.query.first()
        assert initial_attempts == forgot_password.attempts
