"""Playwright UI tests for the settings page's Connected Accounts section
(account-linking Phase 4): `backend/templates/pages/settings.html`'s
`#SettingsConnectedAccounts` block, driven by
`frontend/settings/connected-accounts.ts`.

Link flows that require a real OAuth round-trip ride the test-only fake
provider (`backend/testing/fake_oauth_provider.py`), the same convention as
`tests/functional/splash_ui/test_oauth_google_ui.py` /
`test_oauth_github_ui.py` — mocking Authlib in-process is not feasible
against a Playwright-driven built server.
"""

from __future__ import annotations

import re
from urllib.parse import urlencode, urlsplit, urlunsplit

from flask import Flask
import pytest
from playwright.sync_api import Page, expect

from backend import db
from backend.config import ConfigTestUI
from backend.models.user_oauth_identities import UserOAuthIdentity
from backend.models.users import Users
from backend.splash.services.forgot_password import provider_display_name
from backend.testing.fake_oauth_provider import _DEFAULT_IDENTITY
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.locators import SettingsPageLocators as SPL
from tests.functional.playwright_utils import (
    clear_then_send_keys,
    wait_then_click_element,
    wait_then_get_element,
)
from tests.functional.settings_ui.playwright_utils import login_user_and_open_settings

pytestmark = pytest.mark.settings_ui

DEFAULT_USER_ID: int = 1

_LINK_HAPPY_PATH_GITHUB_SUBJECT = "fake-github-subject-settings-link-happy"
_LINK_HAPPY_PATH_GITHUB_EMAIL = "settingslinkhappy@example.com"

_UNLINK_GITHUB_SUBJECT = "fake-github-subject-settings-unlink"
_UNLINK_GITHUB_EMAIL = "settingsunlink@example.com"

_OAUTH_ONLY_USERNAME = "settingsoauthonlyui"
_OAUTH_ONLY_EMAIL = "settingsoauthonlyui@example.com"
_OAUTH_ONLY_GOOGLE_SUBJECT = "fake-google-subject-settings-oauth-only"

_PROOF_MISMATCH_GOOGLE_SUBJECT = "fake-google-subject-settings-proof-mismatch"

_WRONG_PASSWORD = "TotallyWrongPassword!23"


def _seed_oauth_only_user(
    app: Flask, *, username: str, email: str, subject: str
) -> int:
    """Creates and commits a password-less user with one linked google
    `UserOAuthIdentity`, matching `test_oauth_google_ui.py`'s
    `_seed_oauth_user` pattern. Returns the new user's id."""
    with app.app_context():
        user = Users(username=username, email=email, plaintext_password=None)
        user.oauth_identities.append(
            UserOAuthIdentity(provider="google", provider_subject=subject)
        )
        user.email_validated = True
        db.session.add(user)
        db.session.commit()
        return user.id


def _stash_fake_identity_and_return(
    *, page: Page, subject: str, email: str, return_url: str
) -> None:
    """Stashes a fake-OAuth identity (consumed by the next
    `/fake-oauth/authorize` or `/fake-oauth/github/authorize` hit) via a
    same-origin navigation, then returns to `return_url`.

    Mirrors `login_with_google_ui`/`login_with_github_ui` in
    `tests/functional/playwright_utils.py`: the fake provider has no
    session-shared way to receive the identity other than this browser-driven
    side channel.
    """
    split_current_url = urlsplit(page.url)
    set_identity_url = urlunsplit(
        (
            split_current_url.scheme,
            split_current_url.netloc,
            "/fake-oauth/set-identity",
            urlencode({"subject": subject, "email": email}),
            "",
        )
    )
    page.goto(set_identity_url)
    page.goto(return_url)


def test_connected_accounts_section_renders_for_password_user(
    page: Page,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN a logged-in password user with no linked OAuth identities
    WHEN the user opens /settings
    THEN the Connected Accounts section renders both provider rows as "Not
        connected" with enabled Connect buttons.
    """
    login_user_and_open_settings(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_USER_ID,
        config=provide_config,
    )

    expect(page.locator(SPL.CONNECTED_ACCOUNTS_TITLE)).to_have_text(
        UTS.SETTINGS_CONNECTED_ACCOUNTS_TITLE
    )

    for row_selector in (SPL.ROW_GOOGLE, SPL.ROW_GITHUB):
        row = page.locator(row_selector)
        expect(row.locator(SPL.ROW_STATUS)).to_have_text(
            UTS.SETTINGS_CONNECTED_STATUS_NOT_CONNECTED
        )
        expect(row.locator(SPL.ROW_LINK_BTN)).to_have_text(
            UTS.SETTINGS_CONNECT_BUTTON_TEXT
        )
        expect(row.locator(SPL.ROW_LINK_BTN)).to_be_enabled()


def test_link_password_user_happy_path_to_github(
    page: Page,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN a logged-in password user with no linked github identity
    WHEN the user stashes a fresh github identity, clicks Connect, enters the
        correct password, and continues
    THEN the browser lands back on /settings?linked=github with a success
        banner, the GitHub row shows Connected, and a UserOAuthIdentity row
        is created
    """
    login_user_and_open_settings(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_USER_ID,
        config=provide_config,
    )
    settings_url = page.url

    _stash_fake_identity_and_return(
        page=page,
        subject=_LINK_HAPPY_PATH_GITHUB_SUBJECT,
        email=_LINK_HAPPY_PATH_GITHUB_EMAIL,
        return_url=settings_url,
    )

    wait_then_click_element(
        page=page, css_selector=f"{SPL.ROW_GITHUB} {SPL.ROW_LINK_BTN}"
    )

    password_input = wait_then_get_element(
        page=page, css_selector=SPL.ROW_PASSWORD_INPUT_GITHUB
    )
    clear_then_send_keys(locator=password_input, input_text=UTS.TEST_PASSWORD_1)

    wait_then_click_element(
        page=page, css_selector=f"{SPL.ROW_GITHUB} {SPL.ROW_PASSWORD_CONTINUE_BTN}"
    )

    expect(page).to_have_url(re.compile(r"/settings\?linked=github"))
    expect(page.locator(SPL.LINK_STATUS_BANNER)).to_have_text(
        UTS.OAUTH_LINK_SUCCESS_MESSAGE.format(provider=provider_display_name("github"))
    )
    expect(page.locator(SPL.ROW_GITHUB).locator(SPL.ROW_STATUS)).to_have_text(
        UTS.SETTINGS_CONNECTED_STATUS_CONNECTED.format(
            email=_LINK_HAPPY_PATH_GITHUB_EMAIL
        )
    )

    with provide_app.app_context():
        identity = UserOAuthIdentity.query.filter_by(
            provider="github", provider_subject=_LINK_HAPPY_PATH_GITHUB_SUBJECT
        ).first()
        assert identity is not None
        assert identity.user_id == DEFAULT_USER_ID


def test_link_password_user_wrong_password_shows_error_and_no_row(
    page: Page,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN a logged-in password user
    WHEN the user clicks Connect on the GitHub row, enters an incorrect
        password, and continues
    THEN a danger banner shows the invalid-password message, the browser
        stays on /settings, and no identity row is created
    """
    login_user_and_open_settings(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_USER_ID,
        config=provide_config,
    )

    wait_then_click_element(
        page=page, css_selector=f"{SPL.ROW_GITHUB} {SPL.ROW_LINK_BTN}"
    )
    password_input = wait_then_get_element(
        page=page, css_selector=SPL.ROW_PASSWORD_INPUT_GITHUB
    )
    clear_then_send_keys(locator=password_input, input_text=_WRONG_PASSWORD)

    wait_then_click_element(
        page=page, css_selector=f"{SPL.ROW_GITHUB} {SPL.ROW_PASSWORD_CONTINUE_BTN}"
    )

    banner = page.locator(SPL.LINK_STATUS_BANNER)
    expect(banner).to_have_text(UTS.OAUTH_LINK_INVALID_PASSWORD_MESSAGE)
    expect(banner).to_have_class(re.compile(r"alert-danger"))
    expect(page).to_have_url(re.compile(r"/settings$"))

    with provide_app.app_context():
        assert (
            UserOAuthIdentity.query.filter_by(
                user_id=DEFAULT_USER_ID, provider="github"
            ).first()
            is None
        )


def test_cancel_hides_password_row_and_clears_input(
    page: Page,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN the GitHub row's password-confirm block revealed with typed text
    WHEN the user clicks Cancel
    THEN the password-confirm block hides again and the input is cleared
    """
    login_user_and_open_settings(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_USER_ID,
        config=provide_config,
    )

    wait_then_click_element(
        page=page, css_selector=f"{SPL.ROW_GITHUB} {SPL.ROW_LINK_BTN}"
    )
    password_input = wait_then_get_element(
        page=page, css_selector=SPL.ROW_PASSWORD_INPUT_GITHUB
    )
    clear_then_send_keys(locator=password_input, input_text="SomeTypedPassword!1")

    wait_then_click_element(
        page=page, css_selector=f"{SPL.ROW_GITHUB} {SPL.ROW_PASSWORD_CANCEL_BTN}"
    )

    expect(
        page.locator(SPL.ROW_GITHUB).locator(SPL.ROW_PASSWORD_CONFIRM)
    ).to_be_hidden()
    expect(page.locator(SPL.ROW_PASSWORD_INPUT_GITHUB)).to_have_value("")


def test_unlink_happy_path_removes_identity(
    page: Page,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN a password user with a directly-seeded github identity
    WHEN the user opens /settings and clicks Disconnect on the GitHub row
    THEN the page reloads showing "Not connected" and the identity row is
        deleted from the database
    """
    with provide_app.app_context():
        user = Users.query.get(DEFAULT_USER_ID)
        user.oauth_identities.append(
            UserOAuthIdentity(
                provider="github",
                provider_subject=_UNLINK_GITHUB_SUBJECT,
                email=_UNLINK_GITHUB_EMAIL,
            )
        )
        db.session.commit()

    login_user_and_open_settings(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_USER_ID,
        config=provide_config,
    )

    github_row = page.locator(SPL.ROW_GITHUB)
    expect(github_row.locator(SPL.ROW_STATUS)).to_have_text(
        UTS.SETTINGS_CONNECTED_STATUS_CONNECTED.format(email=_UNLINK_GITHUB_EMAIL)
    )
    unlink_btn = github_row.locator(SPL.ROW_UNLINK_BTN)
    expect(unlink_btn).to_be_enabled()

    unlink_btn.click()

    expect(page.locator(SPL.ROW_GITHUB).locator(SPL.ROW_STATUS)).to_have_text(
        UTS.SETTINGS_CONNECTED_STATUS_NOT_CONNECTED
    )

    with provide_app.app_context():
        assert (
            UserOAuthIdentity.query.filter_by(
                user_id=DEFAULT_USER_ID, provider="github"
            ).first()
            is None
        )


def test_oauth_only_user_last_method_guard(
    page: Page,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN a password-less user with only a linked google identity
    WHEN the user opens /settings
    THEN the Google row shows the last-method note and a DISABLED Disconnect
        button
    """
    oauth_only_user_id = _seed_oauth_only_user(
        provide_app,
        username=_OAUTH_ONLY_USERNAME,
        email=_OAUTH_ONLY_EMAIL,
        subject=_OAUTH_ONLY_GOOGLE_SUBJECT,
    )

    login_user_and_open_settings(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=oauth_only_user_id,
        config=provide_config,
    )

    google_row = page.locator(SPL.ROW_GOOGLE)
    expect(google_row.locator(SPL.ROW_LAST_METHOD_NOTE)).to_have_text(
        UTS.SETTINGS_CONNECTED_LAST_METHOD_NOTE
    )
    expect(google_row.locator(SPL.ROW_UNLINK_BTN)).to_be_disabled()


def test_oauth_only_user_proof_link_to_github(
    page: Page,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN a password-less user with only a linked google identity
    WHEN the user stashes their EXISTING google subject and clicks Connect on
        the GitHub row (no password row — immediate navigation)
    THEN the browser chains a google proof dance and a github link dance in
        one navigation sequence, landing back on /settings?linked=github with
        a github identity created under the fake provider's default subject
        (the proof dance consumes the stash; the chained github dance falls
        back to `_DEFAULT_IDENTITY`)
    """
    oauth_only_user_id = _seed_oauth_only_user(
        provide_app,
        username=_OAUTH_ONLY_USERNAME,
        email=_OAUTH_ONLY_EMAIL,
        subject=_OAUTH_ONLY_GOOGLE_SUBJECT,
    )

    login_user_and_open_settings(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=oauth_only_user_id,
        config=provide_config,
    )
    settings_url = page.url

    _stash_fake_identity_and_return(
        page=page,
        subject=_OAUTH_ONLY_GOOGLE_SUBJECT,
        email=_OAUTH_ONLY_EMAIL,
        return_url=settings_url,
    )

    wait_then_click_element(
        page=page, css_selector=f"{SPL.ROW_GITHUB} {SPL.ROW_LINK_BTN}"
    )

    expect(page).to_have_url(re.compile(r"/settings\?linked=github"))
    expect(page.locator(SPL.LINK_STATUS_BANNER)).to_have_text(
        UTS.OAUTH_LINK_SUCCESS_MESSAGE.format(provider=provider_display_name("github"))
    )

    with provide_app.app_context():
        identity = UserOAuthIdentity.query.filter_by(
            user_id=oauth_only_user_id, provider="github"
        ).first()
        assert identity is not None
        assert identity.provider_subject == _DEFAULT_IDENTITY["sub"]


def test_oauth_only_user_proof_mismatch_shows_error(
    page: Page,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN a password-less user with only a linked google identity
    WHEN the user stashes a DIFFERENT google subject before clicking Connect
        on the GitHub row
    THEN the browser lands on /settings?link_error=proof_mismatch with the
        proof-mismatch banner, and no github identity row is created
    """
    oauth_only_user_id = _seed_oauth_only_user(
        provide_app,
        username=_OAUTH_ONLY_USERNAME,
        email=_OAUTH_ONLY_EMAIL,
        subject=_OAUTH_ONLY_GOOGLE_SUBJECT,
    )

    login_user_and_open_settings(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=oauth_only_user_id,
        config=provide_config,
    )
    settings_url = page.url

    _stash_fake_identity_and_return(
        page=page,
        subject=_PROOF_MISMATCH_GOOGLE_SUBJECT,
        email=_OAUTH_ONLY_EMAIL,
        return_url=settings_url,
    )

    wait_then_click_element(
        page=page, css_selector=f"{SPL.ROW_GITHUB} {SPL.ROW_LINK_BTN}"
    )

    expect(page).to_have_url(re.compile(r"/settings\?link_error=proof_mismatch"))
    expect(page.locator(SPL.LINK_STATUS_BANNER)).to_have_text(
        UTS.OAUTH_LINK_PROOF_MISMATCH_MESSAGE
    )

    with provide_app.app_context():
        assert (
            UserOAuthIdentity.query.filter_by(
                user_id=oauth_only_user_id, provider="github"
            ).first()
            is None
        )
