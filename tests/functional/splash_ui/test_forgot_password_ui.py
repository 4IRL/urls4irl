from datetime import datetime

from flask import Flask
import pytest
from playwright.sync_api import Page, expect

from backend import db
from backend.api_common.request_errors import INVALID_EMAIL_STR
from backend.models.forgot_passwords import Forgot_Passwords
from backend.utils.constants import USER_CONSTANTS
from backend.utils.datetime_utils import utc_now
from backend.utils.strings.html_identifiers import IDENTIFIERS
from backend.utils.strings.reset_password_strs import (
    EMAIL_SENT_MESSAGE,
    FORGOT_PASSWORD,
)
from backend.utils.strings.splash_form_strs import LOGIN_TITLE
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.locators import SplashPageLocators as SPL
from tests.functional.playwright_assert_utils import (
    assert_on_429_page,
    assert_visited_403_on_invalid_csrf_and_reload,
)
from tests.functional.playwright_utils import (
    add_forced_rate_limit_header,
    clear_then_send_keys,
    dismiss_modal_with_click_out,
    invalidate_csrf_token_in_form,
    wait_for_modal_hidden,
    wait_for_modal_ready,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_hidden,
    wait_until_visible_css_selector,
)
from tests.functional.splash_ui.playwright_assert_utils import (
    assert_forgot_password_modal_open,
    assert_forgot_password_submission,
)
from tests.functional.splash_ui.playwright_utils import open_forgot_password_modal

pytestmark = pytest.mark.splash_ui


def test_open_forgot_password_modal(page: Page):
    """
    Tests a user's ability to request a password reminder

    GIVEN a fresh load of the U4I Splash page
    WHEN user opens the login, clicks the 'Forgot Password' link, and enters their email
    THEN the modal responds with an affirmation of reminder sent
    """
    open_forgot_password_modal(page=page)
    assert_forgot_password_modal_open(page=page)

    email_input = wait_then_get_element(
        page=page, css_selector=SPL.FORGOT_PASSWORD_INPUT_EMAIL
    )
    clear_then_send_keys(locator=email_input, input_text=UTS.TEST_PASSWORD_1)

    wait_then_click_element(page=page, css_selector=SPL.FORGOT_PASSWORD_BUTTON_SUBMIT)

    expect(page.locator(SPL.FORGOT_PASSWORD_MODAL_ALERT).first).to_have_text(
        EMAIL_SENT_MESSAGE
    )
    expect(page.locator(SPL.FORGOT_PASSWORD_BUTTON_SUBMIT).first).to_be_disabled()


def test_open_forgot_password_modal_rate_limits(page: Page):
    """
    Tests a user's ability to request a password reminder but rate limited

    GIVEN a fresh load of the U4I Splash page
    WHEN user opens the forgot password modal and submits the form
    THEN the user is rate limited
    """
    open_forgot_password_modal(page=page)

    email_input = wait_then_get_element(
        page=page, css_selector=SPL.FORGOT_PASSWORD_INPUT_EMAIL
    )
    clear_then_send_keys(locator=email_input, input_text=UTS.TEST_PASSWORD_1)

    add_forced_rate_limit_header(page=page)
    wait_then_click_element(page=page, css_selector=SPL.FORGOT_PASSWORD_BUTTON_SUBMIT)
    assert_on_429_page(page=page)


def test_dismiss_forgot_password_modal_click(page: Page):
    """
    Tests a user's ability to close the splash page login modal by clicking outside of the modal

    GIVEN a fresh load of the U4I Splash page
    WHEN user opens the login, then clicks anywhere outside of the modal
    THEN the modal is closed
    """
    open_forgot_password_modal(page=page)
    dismiss_modal_with_click_out(page=page, modal_selector=SPL.FORGOT_PASSWORD_MODAL)
    wait_until_hidden(page=page, css_selector=SPL.FORGOT_PASSWORD_MODAL)


def test_dismiss_forgot_password_modal_x(page: Page):
    """
    Tests a user's ability to close the splash page login modal by clicking the 'x' button in the upper right hand corner

    GIVEN a fresh load of the U4I Splash page
    WHEN user opens the login, then clicks the 'x' of the modal
    THEN the modal is closed
    """
    open_forgot_password_modal(page=page)
    wait_until_visible_css_selector(
        page=page, css_selector=SPL.FORGOT_PASSWORD_BTN_CLOSE
    )
    wait_then_click_element(page=page, css_selector=SPL.FORGOT_PASSWORD_BTN_CLOSE)
    wait_until_hidden(page=page, css_selector=SPL.FORGOT_PASSWORD_MODAL)


def test_dismiss_forgot_password_modal_key(page: Page):
    """
    Tests a user's ability to close the splash page login modal by pressing the Esc key

    GIVEN a fresh load of the U4I Splash page
    WHEN user opens the login, then presses the Esc key
    THEN the modal is closed
    """
    open_forgot_password_modal(page=page)
    wait_then_get_element(page=page, css_selector=SPL.FORGOT_PASSWORD_MODAL)
    page.keyboard.press("Escape")
    wait_until_hidden(page=page, css_selector=SPL.FORGOT_PASSWORD_MODAL)


def test_submit_forgot_password_modal_btn(page: Page):
    """
    Tests a user's ability to request a password reminder

    GIVEN a fresh load of the U4I Splash page
    WHEN user opens the login, clicks the 'Forgot Password' link, and enters their email
    THEN the modal responds with an affirmation of reminder sent
    """
    open_forgot_password_modal(page=page)

    email_input = wait_then_get_element(
        page=page, css_selector=SPL.FORGOT_PASSWORD_INPUT_EMAIL
    )
    clear_then_send_keys(locator=email_input, input_text=UTS.TEST_PASSWORD_1)

    wait_then_click_element(page=page, css_selector=SPL.FORGOT_PASSWORD_BUTTON_SUBMIT)
    assert_forgot_password_submission(page=page)


def test_submit_forgot_password_modal_key(page: Page):
    """
    Tests a user's ability to request a password reminder

    GIVEN a fresh load of the U4I Splash page
    WHEN user opens the login, clicks the 'Forgot Password' link, and enters their email
    THEN the modal responds with an affirmation of reminder sent
    """
    open_forgot_password_modal(page=page)

    email_input = wait_then_get_element(
        page=page, css_selector=SPL.FORGOT_PASSWORD_INPUT_EMAIL
    )
    clear_then_send_keys(locator=email_input, input_text=UTS.TEST_PASSWORD_1)

    page.keyboard.press("Enter")
    assert_forgot_password_submission(page=page)


def test_forgot_password_to_login_modal_btn(page: Page):
    """
    Tests a user's ability to change view from the Forgot Password modal to the Login modal

    GIVEN a fresh load of the U4I Splash page
    WHEN user opens Login, then Forgot Password modal and wants to change back to Login
    THEN ensure the modal view changes appropriately
    """
    open_forgot_password_modal(page=page)
    wait_then_get_element(page=page, css_selector=SPL.FORGOT_PASSWORD_MODAL)

    wait_then_click_element(
        page=page, css_selector=SPL.BUTTON_LOGIN_FROM_FORGOT_PASSWORD
    )
    wait_for_modal_hidden(page=page, modal_selector=SPL.FORGOT_PASSWORD_MODAL)
    wait_for_modal_ready(page=page, modal_selector=SPL.LOGIN_MODAL)
    wait_until_visible_css_selector(
        page=page, css_selector=SPL.BUTTON_FORGOT_PASSWORD_MODAL
    )

    modal_element = wait_then_get_element(page=page, css_selector=SPL.LOGIN_MODAL)
    expect(modal_element.locator(".modal-title").first).to_have_text(LOGIN_TITLE)


def test_forgot_password_empty_field(page: Page):
    """
    Tests site response to an empty submission of the email field in the Forgot Password modal

    GIVEN a fresh load of the U4I Splash page
    WHEN user opens the login, clicks the 'Forgot Password' link, clicks submit with an empty form
    THEN the modal responds with a suggestion to try again
    """
    open_forgot_password_modal(page=page)
    wait_then_click_element(page=page, css_selector=SPL.FORGOT_PASSWORD_BUTTON_SUBMIT)

    feedback_elem = wait_then_get_element(
        page=page, css_selector=SPL.FORGOT_PASSWORD_INVALID_FEEDBACK
    )
    expect(feedback_elem).to_have_text(INVALID_EMAIL_STR)


def test_forgot_password_invalid_email(page: Page):
    """
    Tests site response to a non-email submission of the email field in the Forgot Password modal

    GIVEN a fresh load of the U4I Splash page
    WHEN user opens the login, clicks the 'Forgot Password' link, types a non-email format string and clicks submit
    THEN the modal responds with a suggestion to try again
    """
    open_forgot_password_modal(page=page)
    input_elem = wait_then_get_element(
        page=page, css_selector=SPL.FORGOT_PASSWORD_INPUT_EMAIL
    )
    clear_then_send_keys(locator=input_elem, input_text="abcdf")

    wait_then_click_element(page=page, css_selector=SPL.FORGOT_PASSWORD_BUTTON_SUBMIT)

    feedback_elem = wait_then_get_element(
        page=page, css_selector=SPL.FORGOT_PASSWORD_INVALID_FEEDBACK
    )
    expect(feedback_elem).to_have_text(INVALID_EMAIL_STR)


def test_forgot_password_unconfirmed_email(page: Page, create_user_unconfirmed_email):
    """
    Tests site response to a non-email submission of the email field in the Forgot Password modal

    GIVEN a fresh load of the U4I Splash page
    WHEN user opens the login, clicks the 'Forgot Password' link, types an email that hasn't been confirmed and hits submit
    THEN the modal responds with a success message
    """
    open_forgot_password_modal(page=page)
    input_elem = wait_then_get_element(
        page=page, css_selector=SPL.FORGOT_PASSWORD_INPUT_EMAIL
    )
    clear_then_send_keys(locator=input_elem, input_text=UTS.TEST_PASSWORD_1)

    wait_then_click_element(page=page, css_selector=SPL.FORGOT_PASSWORD_BUTTON_SUBMIT)

    alert_banner = wait_then_get_element(
        page=page, css_selector=SPL.FORGOT_PASSWORD_MODAL_ALERT
    )
    expect(alert_banner).to_have_text(FORGOT_PASSWORD.EMAIL_SENT_MESSAGE)


def test_forgot_password_nonexistent_email(page: Page):
    """
    Tests site response to a non-email submission of the email field in the Forgot Password modal

    GIVEN a fresh load of the U4I Splash page
    WHEN user opens the login, clicks the 'Forgot Password' link, types an email that isn't in the database and hits submit
    THEN the modal responds with a success message
    """
    open_forgot_password_modal(page=page)
    input_elem = wait_then_get_element(
        page=page, css_selector=SPL.FORGOT_PASSWORD_INPUT_EMAIL
    )
    clear_then_send_keys(locator=input_elem, input_text=UTS.TEST_PASSWORD_1)

    wait_then_click_element(page=page, css_selector=SPL.FORGOT_PASSWORD_BUTTON_SUBMIT)

    alert_banner = wait_then_get_element(
        page=page, css_selector=SPL.FORGOT_PASSWORD_MODAL_ALERT
    )
    expect(alert_banner).to_have_text(FORGOT_PASSWORD.EMAIL_SENT_MESSAGE)


def test_forgot_password_two_per_minute_rate_limit(
    page: Page, create_user_resetting_password, provide_app: Flask
):
    """
    Tests site response to user indicating forgot password more than twice per minute

    GIVEN a valid user requesting that they forgot their password
    WHEN user clicks the submit button on forgot password form after having done it twice already
    THEN ensure U4I responds with appropriate error message
    """
    open_forgot_password_modal(page=page)
    input_elem = wait_then_get_element(
        page=page, css_selector=SPL.FORGOT_PASSWORD_INPUT_EMAIL
    )
    clear_then_send_keys(locator=input_elem, input_text=UTS.TEST_PASSWORD_1)

    app = provide_app
    with app.app_context():
        forgot_password: Forgot_Passwords = Forgot_Passwords.query.first()
        forgot_password.last_attempt = datetime.fromtimestamp(
            int(datetime.timestamp(utc_now()))
        )
        initial_attempts = forgot_password.attempts
        db.session.commit()

    wait_then_click_element(page=page, css_selector=SPL.FORGOT_PASSWORD_BUTTON_SUBMIT)

    with app.app_context():
        forgot_password = Forgot_Passwords.query.first()
        assert initial_attempts == forgot_password.attempts


def test_forgot_password_five_per_hour_rate_limit(
    page: Page, create_user_resetting_password, provide_app: Flask
):
    """
    Tests site response to user indicating forgot password more than five times in one hour

    GIVEN a valid user requesting that they forgot their password
    WHEN user clicks the submit button on forgot password form after having done it five times in one hour
    THEN ensure U4I responds with appropriate error message
    """
    open_forgot_password_modal(page=page)
    input_elem = wait_then_get_element(
        page=page, css_selector=SPL.FORGOT_PASSWORD_INPUT_EMAIL
    )
    clear_then_send_keys(locator=input_elem, input_text=UTS.TEST_PASSWORD_1)

    app = provide_app
    with app.app_context():
        forgot_password: Forgot_Passwords = Forgot_Passwords.query.first()
        forgot_password.attempts = USER_CONSTANTS.PASSWORD_RESET_ATTEMPTS
        initial_attempts = forgot_password.attempts
        db.session.commit()

    wait_then_click_element(page=page, css_selector=SPL.FORGOT_PASSWORD_BUTTON_SUBMIT)

    with app.app_context():
        forgot_password = Forgot_Passwords.query.first()
        assert initial_attempts == forgot_password.attempts


def test_forgot_password_invalid_csrf(page: Page):
    """
    Tests site response to user indicating forgot password more than five times in one hour

    GIVEN a valid user requesting that they forgot their password
    WHEN user clicks the submit button on forgot password form with an invalid CSRF token
    THEN browser redirects user to error page, where user can refresh
    """
    open_forgot_password_modal(page=page)
    input_elem = wait_then_get_element(
        page=page, css_selector=SPL.FORGOT_PASSWORD_INPUT_EMAIL
    )
    expect(input_elem).to_be_visible()

    invalidate_csrf_token_in_form(page=page)
    wait_then_click_element(page=page, css_selector=SPL.FORGOT_PASSWORD_BUTTON_SUBMIT)

    assert_visited_403_on_invalid_csrf_and_reload(page=page)

    welcome_text = wait_then_get_element(page=page, css_selector=SPL.WELCOME_TEXT)
    expect(welcome_text).to_have_text(IDENTIFIERS.SPLASH_PAGE)
