from flask import Flask, url_for
import pytest
from playwright.sync_api import Page, expect

from backend import db
from backend.models.email_validations import Email_Validations
from backend.models.users import Users
from backend.utils.all_routes import ROUTES
from backend.utils.strings.email_validation_strs import EMAILS, EMAILS_FAILURE
from backend.utils.strings.html_identifiers import IDENTIFIERS
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.locators import SplashPageLocators as SPL
from tests.functional.playwright_assert_utils import assert_login
from tests.functional.playwright_utils import (
    current_base_url,
    login_user_ui,
    wait_for_element_presence,
    wait_for_modal_ready,
    wait_then_click_element,
    wait_then_get_element,
)
from tests.functional.splash_ui.playwright_utils import register_user_ui

pytestmark = pytest.mark.splash_ui


def test_email_validation_routes_user_properly(
    page: Page, create_user_unconfirmed_email, provide_app: Flask
):
    """
    Tests a user's ability to click a non-expired validation URL

    GIVEN a freshly registered but unvalidated email user
    WHEN user clicks the URL generated for email validation
    THEN ensure the home page opens
    """
    app = provide_app
    validation_url_suffix = create_user_unconfirmed_email
    validation_url = current_base_url(page=page) + validation_url_suffix

    page.goto(validation_url)

    assert_login(page=page)

    with app.app_context():
        user: Users = Users.query.filter(Users.username == UTS.TEST_USERNAME_1).first()
        assert user.email_validated


def test_expired_email_validation_routes_user_properly(page: Page, provide_app: Flask):
    """
    Tests a user's ability to click a expired validation URL

    GIVEN a freshly registered but unvalidated email user
    WHEN user clicks the URL generated for email validation but the token is expired
    THEN ensure the splash page appears with appropriate error message
    """
    app = provide_app

    with app.app_context():
        new_user = Users(
            username=UTS.TEST_USERNAME_1,
            email=UTS.TEST_PASSWORD_1,
            plaintext_password=UTS.TEST_PASSWORD_1,
        )

        new_email_validation = Email_Validations(
            validation_token=new_user.get_email_validation_token(expires_in=0)
        )
        new_email_validation.is_validated = False
        new_user.email_confirm = new_email_validation
        expired_token = new_email_validation.validation_token

        db.session.add(new_user)
        db.session.commit()

        with app.test_request_context():
            expired_url_suffix = url_for(
                ROUTES.SPLASH.VALIDATE_EMAIL, token=expired_token
            )

    validation_url = current_base_url(page=page) + expired_url_suffix

    page.goto(validation_url)

    alert_modal_banner = wait_then_get_element(
        page=page, css_selector=SPL.SPLASH_MODAL_ALERT
    )
    expect(alert_modal_banner).to_have_text(EMAILS.TOKEN_EXPIRED)


def test_email_validation_rate_limits(page: Page):
    """
    Tests that the email validation service appropriately rate limits a user

    GIVEN a freshly registered but unvalidated email user
    WHEN user clicks the validation email button twice in a row
    THEN ensure a rate limiting message appears to the user
    """
    register_user_ui(
        page=page,
        username=UTS.TEST_USERNAME_1,
        email=UTS.TEST_PASSWORD_1,
        password=UTS.TEST_PASSWORD_1,
    )

    wait_then_click_element(page=page, css_selector=SPL.REGISTER_BUTTON_SUBMIT)

    modal_title = wait_then_get_element(
        page=page, css_selector=SPL.HEADER_VALIDATE_EMAIL
    )
    assert modal_title is not None

    # 'Email sent!' is shown when the modal loads
    alert_modal_banner = wait_then_get_element(
        page=page, css_selector=SPL.EMAIL_VALIDATION_MODAL_ALERT
    )
    expect(alert_modal_banner).to_have_text(EMAILS.EMAIL_SENT)

    # Clicking within 60 seconds will rate limit
    wait_then_click_element(page=page, css_selector=SPL.EMAIL_VALIDATION_BUTTON_SUBMIT)
    alert_modal_banner = wait_then_get_element(
        page=page, css_selector=SPL.EMAIL_VALIDATION_MODAL_ALERT
    )
    expect(alert_modal_banner).to_have_text("4" + EMAILS_FAILURE.TOO_MANY_ATTEMPTS)


def test_authenticated_not_validated_user_sees_email_validation_modal(
    page: Page, create_user_unconfirmed_email
):
    """
    Tests that an authenticated but not email-validated user sees the email validation modal.

    GIVEN a registered but not email-validated user
    WHEN the user logs in and navigates to the splash page
    THEN the EmailValidationModal is auto-shown, and closing it triggers logout
    """
    # Login with unvalidated user — this authenticates the session even though
    # the server returns 401 for unvalidated email
    login_user_ui(
        page=page,
        username=UTS.TEST_USERNAME_1,
        password=UTS.TEST_PASSWORD_1,
    )
    wait_then_click_element(page=page, css_selector=SPL.LOGIN_BUTTON_SUBMIT)

    # Wait for the login modal alert showing unconfirmed email error
    login_alert = wait_then_get_element(page=page, css_selector=SPL.LOGIN_MODAL_ALERT)
    expect(login_alert).to_be_visible()

    # Navigate to splash page — user is authenticated but not validated,
    # so the email validation modal should auto-show
    page.goto(page.url.split("?")[0])
    wait_for_modal_ready(page=page, modal_selector=SPL.EMAIL_VALIDATION_MODAL)

    # Assert the email validation modal is visible
    modal_element = wait_then_get_element(
        page=page, css_selector=SPL.EMAIL_VALIDATION_MODAL
    )
    expect(modal_element).to_be_visible()

    # Close the modal — this should trigger logout via logoutOnExit
    email_validation_btn_close = f"{SPL.EMAIL_VALIDATION_MODAL} .btn-close"
    wait_then_click_element(page=page, css_selector=email_validation_btn_close)

    # The btn-close fires Bootstrap's modal-hide AND logoutOnExit's async logout
    # AJAX, which then runs window.location.replace("/"). Wait for the deterministic
    # positive signal that the logout + redirect completed: the reloaded anonymous
    # splash renders #splashConfig with data-show-email-validation="false".
    splash_config = wait_for_element_presence(
        page=page, css_selector=SPL.SPLASH_CONFIG_ANONYMOUS
    )
    assert splash_config is not None

    # The redirect having landed, the modal is hidden on the fresh anonymous
    # splash page (it is still present in the DOM but not shown).
    expect(modal_element).to_be_hidden()

    # After logout, user should be redirected to splash page as anonymous
    welcome_text = wait_then_get_element(page=page, css_selector=SPL.WELCOME_TEXT)
    expect(welcome_text).to_have_text(IDENTIFIERS.SPLASH_PAGE)
