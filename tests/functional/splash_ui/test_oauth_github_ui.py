"""Playwright UI tests for the GitHub OAuth login/register flow.

Mocking `oauth.github`'s Authlib calls is not feasible against a
Playwright-driven built server — there is no in-process patch boundary a test
can reach into. Instead, these tests exercise the real
button -> redirect -> callback -> login round trip against the test-only fake
OAuth provider (`backend/testing/fake_oauth_provider.py`), registered only
when `UI_TESTING` is set (see `ConfigTestUI` in `backend/config.py`).

The provider-agnostic forgot-password UI test lives in
`test_oauth_google_ui.py` and is intentionally not duplicated here.
"""

from __future__ import annotations

from flask import Flask
import pytest
from playwright.sync_api import Page, expect

from backend import db
from backend.models.user_oauth_identities import UserOAuthIdentity
from backend.models.users import Users
from backend.splash.services.forgot_password import provider_display_name
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.locators import SplashPageLocators as SPL
from tests.functional.playwright_assert_utils import assert_login_with_username
from tests.functional.playwright_utils import (
    login_with_github_ui,
    wait_for_modal_ready,
    wait_then_click_element,
    wait_then_get_element,
)

pytestmark = pytest.mark.splash_ui


def _seed_oauth_user(app: Flask, *, subject: str, email: str, username: str) -> None:
    """Creates and commits a password-less user with one linked github
    `UserOAuthIdentity`, matching `test_oauth_google_ui.py`'s
    `_seed_oauth_user` pattern."""
    with app.app_context():
        user = Users(username=username, email=email, plaintext_password=None)
        user.oauth_identities.append(
            UserOAuthIdentity(provider="github", provider_subject=subject)
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


def test_github_login_returning_user_from_login_modal(page: Page, provide_app: Flask):
    """
    GIVEN a Users row with a linked github UserOAuthIdentity
    WHEN the user clicks "Sign in with GitHub" from the Login modal and the
        fake provider returns a matching subject/email
    THEN the user is logged in and redirected home under their existing username
    """
    _seed_oauth_user(
        provide_app,
        subject=UTS.OAUTH_GITHUB_RETURNING_USER_SUBJECT,
        email=UTS.OAUTH_GITHUB_RETURNING_USER_EMAIL,
        username=UTS.OAUTH_GITHUB_RETURNING_USER_USERNAME,
    )

    wait_then_click_element(page=page, css_selector=SPL.BUTTON_LOGIN)
    wait_for_modal_ready(page=page, modal_selector=SPL.LOGIN_MODAL)
    github_button = wait_then_get_element(
        page=page, css_selector=SPL.LOGIN_BUTTON_GITHUB_OAUTH
    )
    assert github_button is not None
    expect(github_button).to_have_text(UTS.GITHUB_OAUTH_LOGIN_BUTTON_TEXT)

    login_with_github_ui(
        page=page,
        subject=UTS.OAUTH_GITHUB_RETURNING_USER_SUBJECT,
        email=UTS.OAUTH_GITHUB_RETURNING_USER_EMAIL,
        login=UTS.OAUTH_GITHUB_RETURNING_USER_LOGIN,
    )

    assert_login_with_username(
        page=page, username=UTS.OAUTH_GITHUB_RETURNING_USER_USERNAME
    )

    with provide_app.app_context():
        assert Users.query.count() == 1
        assert UserOAuthIdentity.query.count() == 1


def test_github_register_new_user_from_register_modal(page: Page, provide_app: Flask):
    """
    GIVEN no existing Users/UserOAuthIdentity row for the fake provider's
        deterministic new-user subject/email
    WHEN the user clicks "Sign up with GitHub" from the Register modal
    THEN a new Users row and linked UserOAuthIdentity row are created, and the
        new user is logged in and redirected home under the username derived
        from the `login` field
    """
    with provide_app.app_context():
        assert Users.query.count() == 0
        assert UserOAuthIdentity.query.count() == 0

    wait_then_click_element(page=page, css_selector=SPL.BUTTON_REGISTER)
    wait_for_modal_ready(page=page, modal_selector=SPL.REGISTER_MODAL)
    github_button = wait_then_get_element(
        page=page, css_selector=SPL.REGISTER_BUTTON_GITHUB_OAUTH
    )
    assert github_button is not None
    expect(github_button).to_have_text(UTS.GITHUB_OAUTH_REGISTER_BUTTON_TEXT)

    login_with_github_ui(
        page=page,
        subject=UTS.OAUTH_GITHUB_NEW_USER_SUBJECT,
        email=UTS.OAUTH_GITHUB_NEW_USER_EMAIL,
        login=UTS.OAUTH_GITHUB_NEW_USER_LOGIN,
        from_register=True,
    )

    assert_login_with_username(page=page, username=UTS.OAUTH_GITHUB_NEW_USER_LOGIN)

    with provide_app.app_context():
        assert Users.query.count() == 1
        assert UserOAuthIdentity.query.count() == 1
        created_identity = UserOAuthIdentity.query.filter_by(
            provider_subject=UTS.OAUTH_GITHUB_NEW_USER_SUBJECT
        ).first()
        assert created_identity is not None
        assert created_identity.user.email == UTS.OAUTH_GITHUB_NEW_USER_EMAIL


def test_github_login_email_collision_shows_confirm_link_page(
    page: Page, provide_app: Flask
):
    """
    GIVEN a password-based Users row with no linked UserOAuthIdentity
    WHEN the fake provider returns that same email under a brand-new subject
    THEN the browser lands on the confirm-link page showing the password
        re-auth prompt, the user is NOT logged in, and no rows were created
    """
    _seed_password_user(
        provide_app,
        email=UTS.OAUTH_GITHUB_COLLISION_EMAIL,
        username=UTS.OAUTH_GITHUB_COLLISION_USERNAME,
        password=UTS.OAUTH_GITHUB_COLLISION_PASSWORD,
    )

    login_with_github_ui(
        page=page,
        subject=UTS.OAUTH_GITHUB_COLLISION_SUBJECT,
        email=UTS.OAUTH_GITHUB_COLLISION_EMAIL,
        login=UTS.OAUTH_GITHUB_COLLISION_LOGIN,
    )

    confirm_prompt = wait_then_get_element(
        page=page, css_selector=SPL.CONFIRM_LINK_PROMPT
    )
    assert confirm_prompt is not None
    expect(confirm_prompt).to_have_text(
        UTS.OAUTH_CONFIRM_LINK_PASSWORD_PROMPT.format(
            email=UTS.OAUTH_GITHUB_COLLISION_EMAIL,
            provider=provider_display_name("github"),
        )
    )

    with provide_app.app_context():
        assert Users.query.count() == 1
        assert UserOAuthIdentity.query.count() == 0
