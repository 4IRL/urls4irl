from datetime import datetime

from flask import Flask
import pytest
from playwright.sync_api import Page, expect

from backend import db
from backend.api_common.request_errors import min_length_message
from backend.models.forgot_passwords import Forgot_Passwords
from backend.models.users import Users
from backend.utils.constants import CONSTANTS
from backend.utils.datetime_utils import utc_now
from backend.utils.strings.html_identifiers import IDENTIFIERS
from backend.utils.strings.json_strs import FAILURE_GENERAL
from backend.utils.strings.reset_password_strs import RESET_PASSWORD
from tests.functional.locators import SplashPageLocators as SPL
from tests.functional.playwright_assert_utils import (
    assert_on_404_page,
    assert_visited_403_on_invalid_csrf_and_reload,
)
from tests.functional.playwright_utils import (
    clear_then_send_keys,
    current_base_url,
    dismiss_modal_with_click_out,
    invalidate_csrf_token_in_form,
    wait_for_element_presence,
    wait_for_modal_ready,
    wait_for_page_complete_and_dom_stable,
    wait_then_click_element,
    wait_then_get_element,
    wait_then_get_elements,
    wait_until_hidden,
    wait_until_in_focus,
    wait_until_visible_css_selector,
)

pytestmark = pytest.mark.splash_ui


def test_password_reset_routes_user_properly(
    page: Page, create_user_resetting_password
):
    """
    Tests a user's ability to click a non-expired password reset URL

    GIVEN a valid user requesting to reset their password
    WHEN user clicks the URL generated for resetting their password
    THEN ensure the splash page opens and the reset password modal shows
    """
    reset_password_suffix = create_user_resetting_password
    reset_password_url = current_base_url(page=page) + reset_password_suffix

    page.goto(reset_password_url)

    expect(page.locator(SPL.INPUT_NEW_PASSWORD).first).to_be_visible()
    expect(page.locator(SPL.INPUT_CONFIRM_NEW_PASSWORD).first).to_be_visible()


def test_password_reset_dismiss_modal_click(page: Page, create_user_resetting_password):
    """
    Tests a user's ability to click a non-expired password reset URL

    GIVEN a valid user requesting to reset their password
    WHEN user clicks anywhere outside of the modal
    THEN ensure the modal is closed
    """
    reset_password_suffix = create_user_resetting_password
    reset_password_url = current_base_url(page=page) + reset_password_suffix

    page.goto(reset_password_url)

    expect(page.locator(SPL.INPUT_NEW_PASSWORD).first).to_be_visible()
    wait_for_modal_ready(page=page, modal_selector=SPL.SPLASH_MODAL)

    dismiss_modal_with_click_out(page=page, modal_selector=SPL.SPLASH_MODAL)
    wait_until_hidden(page=page, css_selector=SPL.SPLASH_MODAL)

    expected_url = current_base_url(page=page) + "/"
    expect(page).to_have_url(expected_url)


def test_password_reset_dismiss_modal_x(page: Page, create_user_resetting_password):
    """
    Tests a user's ability to click a non-expired password reset URL

    GIVEN a valid user requesting to reset their password
    WHEN user clicks the 'x' of the modal
    THEN ensure the modal is closed
    """
    reset_password_suffix = create_user_resetting_password
    reset_password_url = current_base_url(page=page) + reset_password_suffix

    page.goto(reset_password_url)

    expect(page.locator(SPL.INPUT_NEW_PASSWORD).first).to_be_visible()
    wait_for_modal_ready(page=page, modal_selector=SPL.SPLASH_MODAL)

    wait_then_click_element(page=page, css_selector=f"{SPL.SPLASH_MODAL} .btn-close")
    wait_until_hidden(page=page, css_selector=SPL.SPLASH_MODAL)

    expected_url = current_base_url(page=page) + "/"
    expect(page).to_have_url(expected_url)


def test_password_reset_dismiss_modal_key(page: Page, create_user_resetting_password):
    """
    Tests a user's ability to click a non-expired password reset URL

    GIVEN a valid user requesting to reset their password
    WHEN user presses the escape key
    THEN ensure the modal is closed
    """
    reset_password_suffix = create_user_resetting_password
    reset_password_url = current_base_url(page=page) + reset_password_suffix

    page.goto(reset_password_url)

    expect(page.locator(SPL.INPUT_NEW_PASSWORD).first).to_be_visible()
    wait_for_modal_ready(page=page, modal_selector=SPL.SPLASH_MODAL)

    page.keyboard.press("Escape")
    wait_until_hidden(page=page, css_selector=SPL.SPLASH_MODAL)

    expected_url = current_base_url(page=page) + "/"
    expect(page).to_have_url(expected_url)


def test_password_reset_successful_reset_btn(
    page: Page, create_user_resetting_password, provide_app: Flask
):
    """
    Tests a user's ability to change their password using the form provided

    GIVEN a valid user requesting to reset their password
    WHEN user clicks the URL generated for resetting their password and changes their password by clicking submit
    THEN ensure the password shows as reset
    """
    NEW_PASSWORD = "ABCDEFGH1234568"

    app = provide_app
    reset_password_suffix = create_user_resetting_password
    reset_password_url = current_base_url(page=page) + reset_password_suffix

    page.goto(reset_password_url)

    # Under the n=8 UI parallelism cap, the splash.ts ES module can take
    # 200-800ms+ between DOMContentLoaded and `initResetPasswordForm`
    # finishing handler binding. Without this wait, the test can race that
    # gap: it fills inputs and clicks submit before the JS handler is bound,
    # triggering the default HTML form POST instead of the AJAX path.
    wait_for_element_presence(page=page, css_selector=SPL.RESET_PASSWORD_FORM_READY)

    new_password_input = wait_then_get_element(
        page=page, css_selector=SPL.INPUT_NEW_PASSWORD
    )
    confirm_new_password_input = wait_then_get_element(
        page=page, css_selector=SPL.INPUT_CONFIRM_NEW_PASSWORD
    )

    clear_then_send_keys(locator=new_password_input, input_text=NEW_PASSWORD)
    clear_then_send_keys(locator=confirm_new_password_input, input_text=NEW_PASSWORD)

    wait_then_click_element(page=page, css_selector=SPL.RESET_PASSWORD_BUTTON_SUBMIT)

    # Wait for handleUserChangedPassword to run, which changes the submit
    # button value to 'Close'.
    expect(page.locator(SPL.RESET_PASSWORD_BUTTON_SUBMIT).first).to_have_value("Close")

    confirm_alert = wait_then_get_element(
        page=page, css_selector=SPL.SPLASH_MODAL_ALERT
    )
    expect(confirm_alert).to_have_text(RESET_PASSWORD.PASSWORD_RESET)

    with app.app_context():
        user: Users = Users.query.first()
        assert user.is_password_correct(NEW_PASSWORD)


def test_password_reset_successful_reset_key(
    page: Page, create_user_resetting_password, provide_app: Flask
):
    """
    Tests a user's ability to change their password using the form provided

    GIVEN a valid user requesting to reset their password
    WHEN user clicks the URL generated for resetting their password and changes their password by pressing enter on last input
    THEN ensure the password shows as reset
    """
    NEW_PASSWORD = "ABCDEFGH1234568"

    app = provide_app
    reset_password_suffix = create_user_resetting_password
    reset_password_url = current_base_url(page=page) + reset_password_suffix

    page.goto(reset_password_url)

    # See `_btn` variant: wait for the form to advertise readiness so the
    # submit handler is bound before we dispatch ENTER.
    wait_for_element_presence(page=page, css_selector=SPL.RESET_PASSWORD_FORM_READY)

    new_password_input = wait_then_get_element(
        page=page, css_selector=SPL.INPUT_NEW_PASSWORD
    )
    confirm_new_password_input = wait_then_get_element(
        page=page, css_selector=SPL.INPUT_CONFIRM_NEW_PASSWORD
    )

    clear_then_send_keys(locator=new_password_input, input_text=NEW_PASSWORD)
    clear_then_send_keys(locator=confirm_new_password_input, input_text=NEW_PASSWORD)

    # Wait for keyboard focus on the confirm input before pressing Enter so
    # the submit event fires on the correct element.
    wait_until_in_focus(page=page, css_selector=SPL.INPUT_CONFIRM_NEW_PASSWORD)
    confirm_new_password_input.press("Enter")

    # Wait for handleUserChangedPassword to run, which changes the submit
    # button value to 'Close'.
    expect(page.locator(SPL.RESET_PASSWORD_BUTTON_SUBMIT).first).to_have_value("Close")

    confirm_alert = wait_then_get_element(
        page=page, css_selector=SPL.SPLASH_MODAL_ALERT
    )
    expect(confirm_alert).to_have_text(RESET_PASSWORD.PASSWORD_RESET)

    with app.app_context():
        user: Users = Users.query.first()
        assert user.is_password_correct(NEW_PASSWORD)


def test_password_reset_with_hour_old_token(
    page: Page, create_user_resetting_password, provide_app: Flask
):
    """
    Tests U4I response for user clicking on reset password URL with more than hour old token

    GIVEN a valid user wanting to reset their password
    WHEN user clicks the URL generated for resetting their password but URL contains token that is more than an hour old
    THEN ensure 404 page is shown
    """
    app = provide_app
    with app.app_context():
        forgot_password: Forgot_Passwords = Forgot_Passwords.query.first()
        forgot_password.initial_attempt = datetime.fromtimestamp(
            int(datetime.timestamp(utc_now()))
            - (CONSTANTS.USERS.WAIT_TO_RETRY_FORGOT_PASSWORD_MAX + 5)
        )
        db.session.commit()

    reset_password_suffix = create_user_resetting_password
    reset_password_url = current_base_url(page=page) + reset_password_suffix

    page.goto(reset_password_url)
    assert_on_404_page(page=page)


def test_password_reset_with_expired_token(
    page: Page, create_user_resetting_password, provide_app: Flask
):
    """
    Tests U4I response for user clicking on reset password URL with expired token

    GIVEN a valid user wanting to reset their password
    WHEN user clicks the URL generated for resetting their password but URL contains expired token
    THEN ensure 404 page is shown
    """
    app = provide_app
    with app.app_context():
        user: Users = Users.query.first()
        expired_token = user.get_password_reset_token(expires_in=0)
        forgot_password: Forgot_Passwords = Forgot_Passwords.query.first()
        forgot_password.reset_token = expired_token
        db.session.commit()

    reset_password_suffix = create_user_resetting_password
    reset_password_url = current_base_url(page=page) + reset_password_suffix

    page.goto(reset_password_url)
    assert_on_404_page(page=page)


def test_password_reset_with_invalid_token(page: Page, create_user_resetting_password):
    """
    Tests U4I response for user clicking on reset password URL with invalid token

    GIVEN a valid user wanting to reset their password
    WHEN user clicks the URL generated for resetting their password but URL contains invalid token
    THEN ensure 404 page is shown
    """
    INVALID_TOKEN = "abcdefghijklmnop"

    reset_password_url = (
        current_base_url(page=page) + "/reset-password/" + INVALID_TOKEN
    )
    page.goto(reset_password_url)
    assert_on_404_page(page=page)


def test_password_reset_with_unconfirmed_email(
    page: Page, create_user_resetting_password, provide_app: Flask
):
    """
    Tests U4I response for user clicking on reset password URL with an unconfirmed email

    GIVEN a valid user wanting to reset their password
    WHEN user clicks the URL generated for resetting their password but haven't confirmed their email
    THEN ensure 404 page is shown
    """
    app = provide_app
    with app.app_context():
        user: Users = Users.query.first()
        user.email_validated = False
        db.session.commit()

    reset_password_suffix = create_user_resetting_password
    reset_password_url = current_base_url(page=page) + reset_password_suffix

    page.goto(reset_password_url)
    assert_on_404_page(page=page)


def test_password_reset_unequal_password_fields(
    page: Page, create_user_resetting_password
):
    """
    Tests a user's ability to change their password using the form provided

    GIVEN a valid user requesting to reset their password
    WHEN user clicks the URL generated for resetting their password and a confirm password that is not
    equal to the new password
    THEN ensure U4I responds with appropriate error message
    """
    NEW_PASSWORD = "ABCDEFGH1234568"

    reset_password_suffix = create_user_resetting_password
    reset_password_url = current_base_url(page=page) + reset_password_suffix

    page.goto(reset_password_url)

    # See `_btn` variant: wait for the form to advertise readiness so the
    # AJAX submit path is wired before we click.
    wait_for_element_presence(page=page, css_selector=SPL.RESET_PASSWORD_FORM_READY)

    new_password_input = wait_then_get_element(
        page=page, css_selector=SPL.INPUT_NEW_PASSWORD
    )
    confirm_new_password_input = wait_then_get_element(
        page=page, css_selector=SPL.INPUT_CONFIRM_NEW_PASSWORD
    )

    clear_then_send_keys(locator=new_password_input, input_text=NEW_PASSWORD)
    clear_then_send_keys(
        locator=confirm_new_password_input, input_text=NEW_PASSWORD + "a"
    )

    wait_for_page_complete_and_dom_stable(page=page)
    wait_then_click_element(page=page, css_selector=SPL.RESET_PASSWORD_BUTTON_SUBMIT)
    wait_for_page_complete_and_dom_stable(page=page)

    invalid_field = wait_then_get_element(
        page=page, css_selector=SPL.RESET_PASSWORD_INVALID_FEEDBACK
    )
    expect(invalid_field).to_have_text(RESET_PASSWORD.PASSWORDS_NOT_IDENTICAL)


def test_password_reset_missing_fields(page: Page, create_user_resetting_password):
    """
    Tests a user's ability to change their password using the form provided

    GIVEN a valid user requesting to reset their password
    WHEN user clicks the URL generated for resetting their password and submits with empty fields
    THEN ensure U4I responds with appropriate error message
    """
    reset_password_suffix = create_user_resetting_password
    reset_password_url = current_base_url(page=page) + reset_password_suffix

    page.goto(reset_password_url)

    wait_for_element_presence(page=page, css_selector=SPL.RESET_PASSWORD_FORM_READY)

    wait_until_visible_css_selector(
        page=page, css_selector=SPL.RESET_PASSWORD_BUTTON_SUBMIT
    )
    wait_then_click_element(page=page, css_selector=SPL.RESET_PASSWORD_BUTTON_SUBMIT)

    wait_until_visible_css_selector(
        page=page, css_selector=SPL.RESET_PASSWORD_INVALID_FEEDBACK
    )
    invalid_fields = wait_then_get_elements(
        page=page, css_selector=SPL.RESET_PASSWORD_INVALID_FEEDBACK
    )
    assert len(invalid_fields) == 2
    expect(invalid_fields[0]).to_have_text(min_length_message(12))
    expect(invalid_fields[1]).to_have_text(FAILURE_GENERAL.FIELD_REQUIRED_STR)


def test_password_reset_invalid_csrf_token(page: Page, create_user_resetting_password):
    """
    Tests a user's ability to attempt to submit password reset with invalid CSRF token

    GIVEN a valid user requesting to reset their password
    WHEN user clicks the URL generated for resetting their password and submits with an invalid CSRF token
    THEN browser redirects user to error page, where user can refresh
    """
    reset_password_suffix = create_user_resetting_password
    reset_password_url = current_base_url(page=page) + reset_password_suffix

    page.goto(reset_password_url)

    wait_for_element_presence(page=page, css_selector=SPL.RESET_PASSWORD_FORM_READY)

    expect(page.locator(SPL.INPUT_NEW_PASSWORD).first).to_be_visible()
    expect(page.locator(SPL.INPUT_CONFIRM_NEW_PASSWORD).first).to_be_visible()
    wait_for_page_complete_and_dom_stable(page=page)

    invalidate_csrf_token_in_form(page=page)
    wait_for_page_complete_and_dom_stable(page=page)
    wait_then_click_element(page=page, css_selector=SPL.RESET_PASSWORD_BUTTON_SUBMIT)

    assert_visited_403_on_invalid_csrf_and_reload(page=page)

    welcome_text = wait_then_get_element(page=page, css_selector=SPL.WELCOME_TEXT)
    expect(welcome_text).to_have_text(IDENTIFIERS.SPLASH_PAGE)
