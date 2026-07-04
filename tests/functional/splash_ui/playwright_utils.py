from playwright.sync_api import Page

from tests.functional.locators import SplashPageLocators as SPL
from tests.functional.playwright_utils import (
    clear_then_send_keys,
    wait_for_element_presence,
    wait_for_modal_hidden,
    wait_for_modal_ready,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_visible_css_selector,
)


def register_user_ui(
    *,
    page: Page,
    username: str,
    email: str,
    password: str,
    email_confirm: str | None = None,
    pass_confirm: str | None = None,
) -> None:
    """Open the Register modal and fill in all five input fields.

    Args:
        page: Playwright Page open to the U4I Splash page.
        username: Username to register with.
        email: Email address to register with.
        password: Password for the new account.
        email_confirm: Confirmation email. Defaults to email.
        pass_confirm: Confirmation password. Defaults to password.
    """
    if email_confirm is None:
        email_confirm = email

    if pass_confirm is None:
        pass_confirm = password

    # Longer timeout: first click after page load is sensitive to resource
    # contention at n=8.
    wait_then_click_element(page=page, css_selector=SPL.BUTTON_REGISTER)
    wait_for_modal_ready(page=page, modal_selector=SPL.REGISTER_MODAL)

    wait_for_element_presence(page=page, css_selector=SPL.REGISTER_INPUT_USERNAME)
    wait_until_visible_css_selector(page=page, css_selector=SPL.REGISTER_INPUT_USERNAME)

    username_input = wait_then_get_element(
        page=page, css_selector=SPL.REGISTER_INPUT_USERNAME
    )
    clear_then_send_keys(locator=username_input, input_text=username)

    email_input = wait_then_get_element(
        page=page, css_selector=SPL.REGISTER_INPUT_EMAIL
    )
    clear_then_send_keys(locator=email_input, input_text=email)

    confirm_email_input = wait_then_get_element(
        page=page, css_selector=SPL.REGISTER_INPUT_EMAIL_CONFIRM
    )
    clear_then_send_keys(locator=confirm_email_input, input_text=email_confirm)

    password_input = wait_then_get_element(
        page=page, css_selector=SPL.REGISTER_INPUT_PASSWORD
    )
    clear_then_send_keys(locator=password_input, input_text=password)

    confirm_password_input = wait_then_get_element(
        page=page, css_selector=SPL.REGISTER_INPUT_PASSWORD_CONFIRM
    )
    clear_then_send_keys(locator=confirm_password_input, input_text=pass_confirm)


def open_forgot_password_modal(*, page: Page) -> None:
    """Open the Forgot Password modal starting from the Splash page.

    Clicks Login → waits for Login modal → clicks the forgot-password link →
    waits for Login modal to hide → waits for Forgot Password modal to be
    ready → waits for the email input to be visible.

    Args:
        page: Playwright Page open to the U4I Splash page.
    """
    # Longer timeout: first click after page load is sensitive to resource
    # contention at n=8.
    wait_then_click_element(page=page, css_selector=SPL.BUTTON_LOGIN)
    wait_for_modal_ready(page=page, modal_selector=SPL.LOGIN_MODAL)
    wait_then_click_element(page=page, css_selector=SPL.BUTTON_FORGOT_PASSWORD_MODAL)
    wait_for_modal_hidden(page=page, modal_selector=SPL.LOGIN_MODAL)
    wait_for_modal_ready(page=page, modal_selector=SPL.FORGOT_PASSWORD_MODAL)
    wait_until_visible_css_selector(
        page=page, css_selector=SPL.FORGOT_PASSWORD_INPUT_EMAIL
    )
