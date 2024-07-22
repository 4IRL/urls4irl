# Standard library

# External libraries

# Internal libraries
from tests.functional.locators import SplashPageLocators as SPL
from tests.functional.utils_for_test import (
    wait_then_click_element,
    wait_then_get_element,
    clear_then_send_keys,
)


def register_user(browser, username, email, password):
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

    # Submit form
    wait_then_click_element(browser, SPL.BUTTON_SUBMIT)


def register_user_unconfirmed_email(browser, username, email, password):
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


def register_user_unconfirmed_password(browser, username, email, password):
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
