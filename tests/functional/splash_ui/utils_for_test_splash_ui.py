# Standard library

# External libraries
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

# Internal libraries
from tests.functional.locators import SplashPageLocators as SPL
from tests.functional.utils_for_test import (
    wait_then_click_element,
    wait_then_get_element,
    clear_then_send_keys,
)


def register_user(browser: WebDriver, username, email, password):
    """
    Args:
        WebDriver open to U4I Splash Page

    Returns:
        WebDriver handoff to register tests
    """

    # Identify and load register modal
    wait_then_click_element(browser, SPL.BUTTON_REGISTER)

    # Input register user details
    username_input = wait_then_get_element(browser, SPL.INPUT_USERNAME)
    clear_then_send_keys(username_input, username)

    email_input = wait_then_get_element(browser, SPL.INPUT_EMAIL)
    clear_then_send_keys(email_input, email)

    confirm_email_input = wait_then_get_element(browser, SPL.INPUT_EMAIL_CONFIRM)
    clear_then_send_keys(confirm_email_input, email)

    password_input = wait_then_get_element(browser, SPL.INPUT_PASSWORD)
    clear_then_send_keys(password_input, password)

    confirm_password_input = wait_then_get_element(browser, SPL.INPUT_PASSWORD_CONFIRM)
    clear_then_send_keys(confirm_password_input, password)


def register_user_unconfirmed_email(browser: WebDriver, username, email, password):
    """
    Args:
        WebDriver open to U4I Splash Page

    Returns:
        WebDriver handoff to register tests
    """

    # Identify and load register modal
    wait_then_click_element(browser, SPL.BUTTON_REGISTER)

    # Input register user details
    username_input = wait_then_get_element(browser, SPL.INPUT_USERNAME)
    clear_then_send_keys(username_input, username)

    email_input = wait_then_get_element(browser, SPL.INPUT_EMAIL)
    clear_then_send_keys(email_input, email)

    confirm_email_input = wait_then_get_element(
        browser, SPL.INPUT_EMAIL_CONFIRM + "error"
    )
    clear_then_send_keys(confirm_email_input, email)

    password_input = wait_then_get_element(browser, SPL.INPUT_PASSWORD)
    clear_then_send_keys(password_input, password)

    confirm_password_input = wait_then_get_element(browser, SPL.INPUT_PASSWORD_CONFIRM)
    clear_then_send_keys(confirm_password_input, password)

    # Submit form
    wait_then_click_element(browser, SPL.BUTTON_SUBMIT)


def register_user_unconfirmed_password(browser: WebDriver, username, email, password):
    """
    Args:
        WebDriver open to U4I Splash Page

    Returns:
        WebDriver handoff to register tests
    """

    # Identify and load register modal
    wait_then_click_element(browser, SPL.BUTTON_REGISTER)

    # Input register user details
    username_input = wait_then_get_element(browser, SPL.INPUT_USERNAME)
    clear_then_send_keys(username_input, username)

    email_input = wait_then_get_element(browser, SPL.INPUT_EMAIL)
    clear_then_send_keys(email_input, email)

    confirm_email_input = wait_then_get_element(browser, SPL.INPUT_EMAIL_CONFIRM)
    clear_then_send_keys(confirm_email_input, email)

    password_input = wait_then_get_element(browser, SPL.INPUT_PASSWORD)
    clear_then_send_keys(password_input, password)

    confirm_password_input = wait_then_get_element(
        browser, SPL.INPUT_PASSWORD_CONFIRM + "error"
    )
    clear_then_send_keys(confirm_password_input, password)

    # Submit form
    wait_then_click_element(browser, SPL.BUTTON_SUBMIT)


def open_forgot_password_modal(browser: WebDriver):
    wait_then_click_element(browser, SPL.BUTTON_LOGIN)
    wait_then_click_element(browser, SPL.BUTTON_FORGOT_PASSWORD_MODAL)


def assert_forgot_password_modal_open(browser: WebDriver):
    modal_element = wait_then_get_element(browser, SPL.SPLASH_MODAL)
    assert modal_element is not None

    assert modal_element.is_displayed()

    modal_title = modal_element.find_element(By.CLASS_NAME, "modal-title")

    assert modal_title.text == "Forgot your password?"


def assert_forgot_password_submission(browser: WebDriver):
    modal_alert = wait_then_get_element(browser, SPL.SPLASH_MODAL_ALERT)
    assert modal_alert is not None

    assert (
        modal_alert.text
        == "If you entered a valid email, you should receive a reset password link soon."
    )

    submit_btn = wait_then_get_element(browser, SPL.BUTTON_SUBMIT)
    assert submit_btn is not None

    assert submit_btn.get_attribute("disabled")
