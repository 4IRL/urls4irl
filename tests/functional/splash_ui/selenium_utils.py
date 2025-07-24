from selenium.webdriver.remote.webdriver import WebDriver

from tests.functional.locators import SplashPageLocators as SPL
from tests.functional.selenium_utils import (
    ChromeRemoteWebDriver,
    wait_for_element_presence,
    wait_for_modal_ready,
    wait_then_click_element,
    wait_then_get_element,
    clear_then_send_keys,
    wait_until_visible_css_selector,
)


def register_user_ui(
    browser: ChromeRemoteWebDriver,
    username: str,
    email: str,
    password: str,
    email_confirm: str | None = None,
    pass_confirm: str | None = None,
):
    """
    Args:
        WebDriver open to U4I Splash Page

    Returns:
        WebDriver handoff to register tests
    """
    if email_confirm is None:
        email_confirm = email

    if pass_confirm is None:
        pass_confirm = password

    # Identify and load register modal
    wait_then_click_element(browser, SPL.BUTTON_REGISTER)

    wait_for_modal_ready(browser, SPL.SPLASH_MODAL)

    wait_for_element_presence(browser, SPL.INPUT_USERNAME)
    wait_until_visible_css_selector(browser, SPL.INPUT_USERNAME)

    # Input register user details
    username_input = wait_then_get_element(browser, SPL.INPUT_USERNAME)
    assert username_input is not None
    clear_then_send_keys(username_input, username)

    email_input = wait_then_get_element(browser, SPL.INPUT_EMAIL)
    assert email_input is not None
    clear_then_send_keys(email_input, email)

    confirm_email_input = wait_then_get_element(browser, SPL.INPUT_EMAIL_CONFIRM)
    assert confirm_email_input is not None
    clear_then_send_keys(confirm_email_input, email_confirm)

    password_input = wait_then_get_element(browser, SPL.INPUT_PASSWORD)
    assert password_input is not None
    clear_then_send_keys(password_input, password)

    confirm_password_input = wait_then_get_element(browser, SPL.INPUT_PASSWORD_CONFIRM)
    assert confirm_password_input is not None
    clear_then_send_keys(confirm_password_input, pass_confirm)


def open_forgot_password_modal(browser: WebDriver):
    wait_then_click_element(browser, SPL.BUTTON_LOGIN, time=5)
    wait_then_click_element(browser, SPL.BUTTON_FORGOT_PASSWORD_MODAL, time=5)
    wait_until_visible_css_selector(browser, SPL.INPUT_EMAIL, timeout=5)
