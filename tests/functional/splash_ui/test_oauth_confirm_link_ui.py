"""Playwright UI tests for the collision confirm-link page
(`backend/templates/components/splash/oauth_confirm_link.html`) — the shared
surface reached when an OAuth sign-in's email matches an existing local
account that has no linked identity for that provider yet.

Mirrors `test_oauth_github_ui.py`/`test_oauth_google_ui.py`'s pattern of
riding the real fake-provider dance (`backend/testing/fake_oauth_provider.py`)
rather than mocking Authlib in-process — there is no in-process patch
boundary a Playwright-driven built server can reach into.
"""

from __future__ import annotations

import re
from urllib.parse import urlencode, urlsplit, urlunsplit

from flask import Flask
import pytest
from playwright.sync_api import Page, expect

from backend import db
from backend.models.user_oauth_identities import UserOAuthIdentity
from backend.models.users import Users
from backend.splash.services.forgot_password import provider_display_name
from backend.utils.strings.oauth_strs import CONFIRM_LINK_CONTINUE_WITH_TEXT
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.locators import SplashPageLocators as SPL
from tests.functional.playwright_assert_utils import assert_login_with_username
from tests.functional.playwright_utils import (
    clear_then_send_keys,
    login_with_github_ui,
    wait_for_modal_ready,
    wait_then_click_element,
    wait_then_get_element,
)

pytestmark = pytest.mark.splash_ui

_PASSWORD_COLLISION_USERNAME = "confirmlinkpwuser"
_PASSWORD_COLLISION_EMAIL = "confirmlinkpwuser@example.com"
_PASSWORD_COLLISION_PASSWORD = "P@ssword123!"

_GITHUB_COLLISION_SUBJECT = "fake-github-subject-confirm-link"
_GITHUB_COLLISION_LOGIN = "confirmlinkgithublogin"

_OAUTH_ONLY_USERNAME = "confirmlinkoauthonly"
_OAUTH_ONLY_EMAIL = "confirmlinkoauthonly@example.com"
_OAUTH_ONLY_GOOGLE_SUBJECT = "fake-google-subject-confirm-link-oauth-only"

_WRONG_PASSWORD = "TotallyWrongPassword!23"


def _seed_password_user(
    app: Flask, *, email: str, username: str, password: str
) -> None:
    """Creates and commits a plain password-based user with no linked OAuth
    identity, matching `test_oauth_github_ui.py`'s `_seed_password_user`
    pattern."""
    with app.app_context():
        user = Users(username=username, email=email, plaintext_password=password)
        user.email_validated = True
        db.session.add(user)
        db.session.commit()


def _seed_oauth_only_user(
    app: Flask, *, username: str, email: str, subject: str
) -> None:
    """Creates and commits a password-less user with one linked google
    `UserOAuthIdentity`, matching `test_oauth_google_ui.py`'s
    `_seed_oauth_user` pattern."""
    with app.app_context():
        user = Users(username=username, email=email, plaintext_password=None)
        user.oauth_identities.append(
            UserOAuthIdentity(provider="google", provider_subject=subject)
        )
        user.email_validated = True
        db.session.add(user)
        db.session.commit()


def test_password_account_collision_completes_via_password(
    page: Page, provide_app: Flask
):
    """
    GIVEN a password-based Users row with no linked github identity
    WHEN the fake github provider returns that same email under a brand-new
        subject, and the confirm-link page is submitted with the correct
        password
    THEN the browser lands on the authenticated home page as that user, and a
        github UserOAuthIdentity row is created for them
    """
    _seed_password_user(
        provide_app,
        email=_PASSWORD_COLLISION_EMAIL,
        username=_PASSWORD_COLLISION_USERNAME,
        password=_PASSWORD_COLLISION_PASSWORD,
    )

    login_with_github_ui(
        page=page,
        subject=_GITHUB_COLLISION_SUBJECT,
        email=_PASSWORD_COLLISION_EMAIL,
        login=_GITHUB_COLLISION_LOGIN,
    )

    wait_for_modal_ready(page=page, modal_selector=SPL.SPLASH_MODAL)
    confirm_prompt = wait_then_get_element(
        page=page, css_selector=SPL.CONFIRM_LINK_PROMPT
    )
    expect(confirm_prompt).to_have_text(
        UTS.OAUTH_CONFIRM_LINK_PASSWORD_PROMPT.format(
            email=_PASSWORD_COLLISION_EMAIL,
            provider=provider_display_name("github"),
        )
    )

    password_input = wait_then_get_element(
        page=page, css_selector=SPL.CONFIRM_LINK_INPUT_PASSWORD
    )
    clear_then_send_keys(
        locator=password_input, input_text=_PASSWORD_COLLISION_PASSWORD
    )
    wait_then_click_element(page=page, css_selector=SPL.CONFIRM_LINK_BUTTON_SUBMIT)

    assert_login_with_username(page=page, username=_PASSWORD_COLLISION_USERNAME)
    expect(page).to_have_url(re.compile(r"/home$"))

    with provide_app.app_context():
        identity = UserOAuthIdentity.query.filter_by(
            provider="github", provider_subject=_GITHUB_COLLISION_SUBJECT
        ).first()
        assert identity is not None
        assert identity.user.email == _PASSWORD_COLLISION_EMAIL


def test_password_account_collision_wrong_password_then_retry_succeeds(
    page: Page, provide_app: Flask
):
    """
    GIVEN the same password-account collision as above
    WHEN the confirm-link form is submitted with the WRONG password
    THEN the splash modal alert banner shows the invalid-password message,
        the browser stays on the confirm page, the user is not logged in, and
        no identity row is created — retrying with the correct password on
        the same page then succeeds
    """
    _seed_password_user(
        provide_app,
        email=_PASSWORD_COLLISION_EMAIL,
        username=_PASSWORD_COLLISION_USERNAME,
        password=_PASSWORD_COLLISION_PASSWORD,
    )

    login_with_github_ui(
        page=page,
        subject=_GITHUB_COLLISION_SUBJECT,
        email=_PASSWORD_COLLISION_EMAIL,
        login=_GITHUB_COLLISION_LOGIN,
    )

    wait_for_modal_ready(page=page, modal_selector=SPL.SPLASH_MODAL)
    wait_then_get_element(page=page, css_selector=SPL.CONFIRM_LINK_PROMPT)

    password_input = wait_then_get_element(
        page=page, css_selector=SPL.CONFIRM_LINK_INPUT_PASSWORD
    )
    clear_then_send_keys(locator=password_input, input_text=_WRONG_PASSWORD)
    wait_then_click_element(page=page, css_selector=SPL.CONFIRM_LINK_BUTTON_SUBMIT)

    banner = page.locator(SPL.SPLASH_MODAL_ALERT)
    expect(banner).to_have_text(UTS.OAUTH_LINK_INVALID_PASSWORD_MESSAGE)
    expect(page.locator(SPL.CONFIRM_LINK_PROMPT)).to_be_visible()
    expect(page).not_to_have_url(re.compile(r"/home$"))

    with provide_app.app_context():
        assert (
            UserOAuthIdentity.query.filter_by(
                provider="github", provider_subject=_GITHUB_COLLISION_SUBJECT
            ).first()
            is None
        )

    password_input = wait_then_get_element(
        page=page, css_selector=SPL.CONFIRM_LINK_INPUT_PASSWORD
    )
    clear_then_send_keys(
        locator=password_input, input_text=_PASSWORD_COLLISION_PASSWORD
    )
    wait_then_click_element(page=page, css_selector=SPL.CONFIRM_LINK_BUTTON_SUBMIT)

    assert_login_with_username(page=page, username=_PASSWORD_COLLISION_USERNAME)

    with provide_app.app_context():
        identity = UserOAuthIdentity.query.filter_by(
            provider="github", provider_subject=_GITHUB_COLLISION_SUBJECT
        ).first()
        assert identity is not None


def test_oauth_only_collision_completes_via_google_continue(
    page: Page, provide_app: Flask
):
    """
    GIVEN a password-less user with only a linked google identity
    WHEN a github sign-in collides with that user's email, the confirm page
        shows the OAuth-only prompt and a "Continue with Google" anchor, and
        the user re-proves ownership by signing in again with their EXISTING
        google identity
    THEN the browser lands on the authenticated home page as that user, and a
        github UserOAuthIdentity row is auto-created under the collision
        subject
    """
    _seed_oauth_only_user(
        provide_app,
        username=_OAUTH_ONLY_USERNAME,
        email=_OAUTH_ONLY_EMAIL,
        subject=_OAUTH_ONLY_GOOGLE_SUBJECT,
    )

    login_with_github_ui(
        page=page,
        subject=_GITHUB_COLLISION_SUBJECT,
        email=_OAUTH_ONLY_EMAIL,
        login=_GITHUB_COLLISION_LOGIN,
    )

    wait_for_modal_ready(page=page, modal_selector=SPL.SPLASH_MODAL)
    confirm_prompt = wait_then_get_element(
        page=page, css_selector=SPL.CONFIRM_LINK_PROMPT
    )
    expect(confirm_prompt).to_have_text(
        UTS.OAUTH_CONFIRM_LINK_OAUTH_ONLY_PROMPT.format(
            email=_OAUTH_ONLY_EMAIL,
            provider=provider_display_name("github"),
        )
    )
    continue_with_google = wait_then_get_element(
        page=page, css_selector=SPL.CONFIRM_LINK_CONTINUE_WITH_GOOGLE
    )
    expect(continue_with_google).to_have_text(
        CONFIRM_LINK_CONTINUE_WITH_TEXT.format(provider=provider_display_name("google"))
    )

    # Re-stash the user's EXISTING google subject (the proof identity) via a
    # same-origin navigation, then return to the confirm page — the pending
    # github collision survives in the session (a bare GET re-render never
    # pops it), so clicking "Continue with Google" completes the link.
    confirm_link_url = page.url
    split_confirm_link_url = urlsplit(confirm_link_url)
    set_identity_url = urlunsplit(
        (
            split_confirm_link_url.scheme,
            split_confirm_link_url.netloc,
            "/fake-oauth/set-identity",
            urlencode(
                {"subject": _OAUTH_ONLY_GOOGLE_SUBJECT, "email": _OAUTH_ONLY_EMAIL}
            ),
            "",
        )
    )
    page.goto(set_identity_url)
    page.goto(confirm_link_url)

    wait_for_modal_ready(page=page, modal_selector=SPL.SPLASH_MODAL)
    wait_then_click_element(
        page=page, css_selector=SPL.CONFIRM_LINK_CONTINUE_WITH_GOOGLE
    )

    assert_login_with_username(page=page, username=_OAUTH_ONLY_USERNAME)
    expect(page).to_have_url(re.compile(r"/home$"))

    with provide_app.app_context():
        identity = UserOAuthIdentity.query.filter_by(
            provider="github", provider_subject=_GITHUB_COLLISION_SUBJECT
        ).first()
        assert identity is not None
        assert identity.user.email == _OAUTH_ONLY_EMAIL
