from urllib.parse import urlparse

import pytest
from flask import Flask, url_for
from playwright.sync_api import Page, expect

from backend import db
from backend.models.email_validations import Email_Validations
from backend.models.users import Users
from backend.utils.all_routes import ROUTES
from backend.utils.strings.email_validation_strs import EMAILS
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.locators import SplashPageLocators as SPL
from tests.functional.playwright_assert_utils import assert_login
from tests.functional.playwright_utils import (
    current_base_url,
    wait_for_element_presence,
    wait_for_modal_ready,
    wait_then_click_element,
    wait_then_get_element,
)

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


def _create_expired_validation_url(*, app: Flask, page: Page) -> str:
    """Creates an unvalidated user with an expired token and returns its link."""

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

    return current_base_url(page=page) + expired_url_suffix


def test_expired_email_validation_routes_user_properly(page: Page, provide_app: Flask):
    """
    Tests a user's ability to click a expired validation URL

    GIVEN a freshly registered but unvalidated email user
    WHEN user clicks the URL generated for email validation but the token is expired
    THEN ensure the splash page appears with appropriate error message
    """
    validation_url = _create_expired_validation_url(app=provide_app, page=page)

    page.goto(validation_url)

    alert_modal_banner = wait_then_get_element(
        page=page, css_selector=SPL.SPLASH_MODAL_ALERT
    )
    expect(alert_modal_banner).to_have_text(EMAILS.TOKEN_EXPIRED)


def test_expired_email_validation_resend_then_close_returns_to_anonymous_splash(
    page: Page, provide_app: Flask
):
    """
    GIVEN an unvalidated user who opens an expired validation link
    WHEN they click Resend, see the success banner, then close the modal
    THEN the page reloads to the anonymous splash and no /logout request is made
    """
    validation_url = _create_expired_validation_url(app=provide_app, page=page)
    requested_urls: list[str] = []
    page.on("request", lambda request: requested_urls.append(request.url))

    page.goto(validation_url)
    wait_for_modal_ready(page=page, modal_selector=SPL.CONFIRM_EMAIL_MODAL)
    expect(page.locator(SPL.SPLASH_MODAL_ALERT)).to_have_text(EMAILS.TOKEN_EXPIRED)
    expect(page.locator(SPL.BACK_TO_LOGIN_FROM_CONFIRM_EMAIL)).to_have_text("Close")

    wait_then_click_element(
        page=page, css_selector=SPL.RESEND_CONFIRMATION_EMAIL_BUTTON
    )
    expect(page.locator(SPL.SPLASH_MODAL_ALERT)).to_have_text(UTS.REGISTER_EMAIL_RESENT)

    wait_then_click_element(
        page=page, css_selector=SPL.BACK_TO_LOGIN_FROM_CONFIRM_EMAIL
    )
    wait_for_element_presence(page=page, css_selector=SPL.SPLASH_CONFIG_ANONYMOUS)
    # The reloaded anonymous splash only has the normal (hidden) inline modal
    expect(page.locator(SPL.CONFIRM_EMAIL_MODAL)).to_be_hidden()
    expect(page.locator("[data-resend-token]")).to_have_count(0)

    assert not any(
        urlparse(url).path.rstrip("/").endswith("/logout") for url in requested_urls
    )
