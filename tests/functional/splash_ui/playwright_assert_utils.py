from playwright.sync_api import Page, expect

from backend.utils.strings.reset_password_strs import EMAIL_SENT_MESSAGE
from backend.utils.strings.splash_form_strs import FORGOT_YOUR_PASSWORD
from tests.functional.locators import SplashPageLocators as SPL


def assert_forgot_password_modal_open(*, page: Page) -> None:
    """Assert the Forgot Password modal is visible with the correct title."""
    modal_element = page.locator(SPL.FORGOT_PASSWORD_MODAL).first
    expect(modal_element).to_be_visible()
    expect(modal_element.locator(".modal-title").first).to_have_text(
        FORGOT_YOUR_PASSWORD
    )


def assert_forgot_password_submission(*, page: Page) -> None:
    """Assert the Forgot Password modal shows the email-sent message and the
    submit button is disabled."""
    expect(page.locator(SPL.FORGOT_PASSWORD_MODAL_ALERT).first).to_have_text(
        EMAIL_SENT_MESSAGE
    )
    expect(page.locator(SPL.FORGOT_PASSWORD_BUTTON_SUBMIT).first).to_be_disabled()
