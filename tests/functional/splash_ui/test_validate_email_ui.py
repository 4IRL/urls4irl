from flask import Flask, url_for
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

from src import db
from src.models.email_validations import Email_Validations
from src.models.users import Users
from src.utils.all_routes import ROUTES
from src.utils.strings.email_validation_strs import EMAILS, EMAILS_FAILURE
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.locators import SplashPageLocators as SPL
from tests.functional.splash_ui.utils_for_test_splash_ui import register_user_ui
from tests.functional.utils_for_test import (
    assert_login,
    wait_then_click_element,
    wait_then_get_element,
)

pytestmark = pytest.mark.splash_ui


def test_email_validation_routes_user_properly(
    browser: WebDriver, create_user_unconfirmed_email, provide_app: Flask
):
    """
    Tests a user's ability to click a non-expired validation URL

    GIVEN a freshly registered but unvalidated email user
    WHEN user clicks the URL generated for email validation
    THEN ensure the home page opens
    """
    app = provide_app
    validation_url_suffix = create_user_unconfirmed_email
    validation_url = browser.current_url + validation_url_suffix

    browser.get(validation_url)

    assert_login(browser)

    with app.app_context():
        user: Users = Users.query.filter(Users.username == UTS.TEST_USERNAME_1).first()
        assert user.is_email_authenticated()


def test_expired_email_validation_routes_user_properly(
    browser: WebDriver, provide_app: Flask
):
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

    validation_url = browser.current_url + expired_url_suffix

    browser.get(validation_url)

    alert_modal_banner = wait_then_get_element(browser, SPL.SPLASH_MODAL_ALERT, time=5)
    assert alert_modal_banner is not None

    assert alert_modal_banner.text == EMAILS.TOKEN_EXPIRED


def test_email_validation_rate_limits(browser: WebDriver):
    """
    Tests that the email validation service appropriately rate limits a user

    GIVEN a freshly registered but unvalidated email user
    WHEN user clicks the validation email button twice in a row
    THEN ensure a rate limiting message appears to the user
    """
    register_user_ui(
        browser, UTS.TEST_USERNAME_1, UTS.TEST_PASSWORD_1, UTS.TEST_PASSWORD_1
    )

    # Submit form
    wait_then_click_element(browser, SPL.BUTTON_SUBMIT)

    # Await response
    modal_title = wait_then_get_element(browser, SPL.HEADER_VALIDATE_EMAIL, time=3)
    assert modal_title is not None

    # 'Email sent!' is shown when the modal loads
    alert_modal_banner = wait_then_get_element(browser, SPL.SPLASH_MODAL_ALERT, time=3)
    assert alert_modal_banner is not None
    assert alert_modal_banner.text == EMAILS.EMAIL_SENT

    # Clicking within 60 seconds will rate limit
    browser.find_element(By.CSS_SELECTOR, SPL.BUTTON_SUBMIT).click()
    alert_modal_banner = wait_then_get_element(browser, SPL.SPLASH_MODAL_ALERT, time=3)
    assert alert_modal_banner is not None
    assert alert_modal_banner.text == "4" + EMAILS_FAILURE.TOO_MANY_ATTEMPTS
