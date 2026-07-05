"""Playwright UI tests for the Google OAuth login/register flow.

Mocking `oauth.google`'s Authlib calls is not feasible against a
Playwright-driven built server — there is no in-process patch boundary a test
can reach into. Instead, these tests exercise the real
button -> redirect -> callback -> login round trip against the test-only fake
OAuth provider (`backend/testing/fake_oauth_provider.py`), registered only
when `UI_TESTING` is set (see `ConfigTestUI` in `backend/config.py`).
"""

from __future__ import annotations

from flask import Flask
import pytest
from playwright.sync_api import Page, expect

from backend import db
from backend.models.user_oauth_identities import UserOAuthIdentity
from backend.models.users import Users
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.locators import SplashPageLocators as SPL
from tests.functional.playwright_assert_utils import assert_login_with_username
from tests.functional.playwright_utils import (
    clear_then_send_keys,
    login_with_google_ui,
    wait_for_modal_ready,
    wait_then_click_element,
    wait_then_get_element,
)
from tests.functional.splash_ui.playwright_assert_utils import (
    assert_forgot_password_submission,
)
from tests.functional.splash_ui.playwright_utils import open_forgot_password_modal

pytestmark = pytest.mark.splash_ui


def _seed_oauth_user(app: Flask, *, subject: str, email: str, username: str) -> None:
    """Creates and commits a password-less user with one linked google
    `UserOAuthIdentity`, matching `test_oauth_google.py`'s
    `_seed_existing_oauth_user` pattern."""
    with app.app_context():
        user = Users(username=username, email=email, plaintext_password=None)
        user.oauth_identities.append(
            UserOAuthIdentity(provider="google", provider_subject=subject)
        )
        user.email_validated = True
        db.session.add(user)
        db.session.commit()


def _seed_password_user(
    app: Flask, *, email: str, username: str, password: str
) -> None:
    """Creates and commits a plain password-based user with no linked OAuth
    identity, used to force the email-collision reject branch."""
    with app.app_context():
        user = Users(username=username, email=email, plaintext_password=password)
        user.email_validated = True
        db.session.add(user)
        db.session.commit()


def test_google_login_returning_user_from_login_modal(page: Page, provide_app: Flask):
    """
    GIVEN a Users row with a linked google UserOAuthIdentity
    WHEN the user clicks "Sign in with Google" from the Login modal and the
        fake provider returns a matching subject/email
    THEN the user is logged in and redirected home under their existing username
    """
    _seed_oauth_user(
        provide_app,
        subject=UTS.OAUTH_RETURNING_USER_SUBJECT,
        email=UTS.OAUTH_RETURNING_USER_EMAIL,
        username=UTS.OAUTH_RETURNING_USER_USERNAME,
    )

    wait_then_click_element(page=page, css_selector=SPL.BUTTON_LOGIN)
    wait_for_modal_ready(page=page, modal_selector=SPL.LOGIN_MODAL)
    google_button = wait_then_get_element(
        page=page, css_selector=SPL.LOGIN_BUTTON_GOOGLE_OAUTH
    )
    assert google_button is not None
    expect(google_button).to_have_text(UTS.GOOGLE_OAUTH_LOGIN_BUTTON_TEXT)

    login_with_google_ui(
        page=page,
        subject=UTS.OAUTH_RETURNING_USER_SUBJECT,
        email=UTS.OAUTH_RETURNING_USER_EMAIL,
        name=UTS.OAUTH_RETURNING_USER_NAME,
    )

    assert_login_with_username(page=page, username=UTS.OAUTH_RETURNING_USER_USERNAME)

    with provide_app.app_context():
        assert Users.query.count() == 1
        assert UserOAuthIdentity.query.count() == 1


def test_google_register_new_user_from_register_modal(page: Page, provide_app: Flask):
    """
    GIVEN no existing Users/UserOAuthIdentity row for the fake provider's
        deterministic new-user subject/email
    WHEN the user clicks "Sign up with Google" from the Register modal
    THEN a new Users row and linked UserOAuthIdentity row are created, and the
        new user is logged in and redirected home under the derived username
    """
    with provide_app.app_context():
        assert Users.query.count() == 0
        assert UserOAuthIdentity.query.count() == 0

    wait_then_click_element(page=page, css_selector=SPL.BUTTON_REGISTER)
    wait_for_modal_ready(page=page, modal_selector=SPL.REGISTER_MODAL)
    google_button = wait_then_get_element(
        page=page, css_selector=SPL.REGISTER_BUTTON_GOOGLE_OAUTH
    )
    assert google_button is not None
    expect(google_button).to_have_text(UTS.GOOGLE_OAUTH_REGISTER_BUTTON_TEXT)

    login_with_google_ui(
        page=page,
        subject=UTS.OAUTH_NEW_USER_SUBJECT,
        email=UTS.OAUTH_NEW_USER_EMAIL,
        name=UTS.OAUTH_NEW_USER_NAME,
        from_register=True,
    )

    assert_login_with_username(page=page, username=UTS.OAUTH_NEW_USER_NAME)

    with provide_app.app_context():
        assert Users.query.count() == 1
        assert UserOAuthIdentity.query.count() == 1
        created_identity = UserOAuthIdentity.query.filter_by(
            provider_subject=UTS.OAUTH_NEW_USER_SUBJECT
        ).first()
        assert created_identity is not None
        assert created_identity.user.email == UTS.OAUTH_NEW_USER_EMAIL


def test_google_login_email_collision_shows_reject_message(
    page: Page, provide_app: Flask
):
    """
    GIVEN a password-based Users row with no linked UserOAuthIdentity
    WHEN the fake provider returns that same email under a brand-new subject
    THEN the reject-page banner shows the email-collision message and the
        user is NOT logged in, with no new rows created
    """
    _seed_password_user(
        provide_app,
        email=UTS.OAUTH_COLLISION_EMAIL,
        username=UTS.OAUTH_COLLISION_USERNAME,
        password=UTS.OAUTH_COLLISION_PASSWORD,
    )

    login_with_google_ui(
        page=page,
        subject=UTS.OAUTH_COLLISION_SUBJECT,
        email=UTS.OAUTH_COLLISION_EMAIL,
        name=UTS.OAUTH_COLLISION_NAME,
    )

    modal_alert = wait_then_get_element(page=page, css_selector=SPL.SPLASH_MODAL_ALERT)
    assert modal_alert is not None
    expect(modal_alert).to_have_text(UTS.OAUTH_EMAIL_COLLISION_MESSAGE)

    with provide_app.app_context():
        assert Users.query.count() == 1
        assert UserOAuthIdentity.query.count() == 0


def test_forgot_password_for_google_only_account_shows_generic_success(
    page: Page, provide_app: Flask
):
    """
    GIVEN a Google-only (password-less) Users row
    WHEN the user submits that email through the Forgot Password modal
    THEN the UI shows the same generic "email sent" success message as any
        other forgot-password request, with no branch revealing the account
        is OAuth-only
    """
    _seed_oauth_user(
        provide_app,
        subject=UTS.OAUTH_FORGOT_PASSWORD_SUBJECT,
        email=UTS.OAUTH_FORGOT_PASSWORD_EMAIL,
        username=UTS.OAUTH_FORGOT_PASSWORD_USERNAME,
    )

    open_forgot_password_modal(page=page)
    email_input = wait_then_get_element(
        page=page, css_selector=SPL.FORGOT_PASSWORD_INPUT_EMAIL
    )
    assert email_input is not None
    clear_then_send_keys(
        locator=email_input, input_text=UTS.OAUTH_FORGOT_PASSWORD_EMAIL
    )

    wait_then_click_element(page=page, css_selector=SPL.FORGOT_PASSWORD_BUTTON_SUBMIT)

    assert_forgot_password_submission(page=page)

    with provide_app.app_context():
        oauth_only_user = Users.query.filter_by(
            email=UTS.OAUTH_FORGOT_PASSWORD_EMAIL
        ).first()
        assert oauth_only_user is not None
        assert oauth_only_user.forgot_password is None
