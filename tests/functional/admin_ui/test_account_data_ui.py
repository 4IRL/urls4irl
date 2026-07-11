"""Playwright UI tests for Phase 7 account-data admin actions.

Covers Erase Account, Mark Email Verified, and the OAuth unlink
last-credential guard on the user-detail page.
"""

from __future__ import annotations

import pytest
from flask import Flask
from playwright.sync_api import Page, expect

from backend import db
from backend.admin.account_data_service import TOMBSTONE_USERNAME_PREFIX
from backend.config import ConfigTestUI
from backend.models.user_oauth_identities import UserOAuthIdentity
from backend.models.users import Users
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS
from tests.functional.admin_ui.playwright_utils import login_admin_and_open_user_detail
from tests.functional.locators import AdminPortalLocators as APL
from tests.functional.playwright_utils import wait_then_get_element

pytestmark = pytest.mark.admin_ui

DEFAULT_ADMIN_USER_ID: int = 1
# User 2 is a non-admin account available in every create_test_utubs fixture run.
TARGET_USER_ID: int = 2

TEST_REASON_TEXT: str = "automated account data test"

_MOCK_PROVIDER: str = "google"
_MOCK_PROVIDER_SUBJECT: str = "google-sub-data-ui-test"


def _seed_oauth_only_user(app: Flask) -> int:
    """Create an OAuth-only user (no local password) with one linked identity.

    Returns the new user's database ID so callers can navigate to their
    detail page.
    """
    with app.app_context():
        oauth_user = Users(
            username="oauth_only_data_ui",
            email="oauth_only_data_ui@test.com",
        )
        oauth_user.email_validated = True
        db.session.add(oauth_user)
        db.session.flush()
        identity = UserOAuthIdentity(
            provider=_MOCK_PROVIDER,
            provider_subject=_MOCK_PROVIDER_SUBJECT,
        )
        oauth_user.oauth_identities.append(identity)
        db.session.commit()
        db.session.refresh(oauth_user)
        return oauth_user.id


def test_admin_account_erase_happy_path(
    page: Page,
    create_test_utubs,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
) -> None:
    """
    GIVEN an admin viewing a non-admin user's detail page with the account not erased
    WHEN the admin clicks Erase Account, enters a reason, and confirms
    THEN the page reloads, the Erased row shows "yes", the username cell shows the
         tombstone value, and the erase button is replaced by the erased-NA span.
    """
    login_admin_and_open_user_detail(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
        target_user_id=TARGET_USER_ID,
    )

    # Assert precondition: account is not erased before the action
    erased_cell = wait_then_get_element(page=page, css_selector=APL.USER_DETAIL_ERASED)
    expect(erased_cell).to_have_text("no")

    # The Erase Account button must be present
    erase_btn = wait_then_get_element(
        page=page, css_selector=APL.USER_DETAIL_ACCOUNT_ERASE_BTN
    )
    expect(erase_btn).to_be_visible()
    expect(erase_btn).to_have_text(UI_TEST_STRINGS.ADMIN_ACCOUNT_ERASE_LABEL)

    erase_btn.click()

    modal_title = wait_then_get_element(page=page, css_selector=APL.ACTION_MODAL_TITLE)
    expect(modal_title).to_have_text(UI_TEST_STRINGS.ADMIN_ACCOUNT_ERASE_CONFIRM_TITLE)

    reason_input = wait_then_get_element(
        page=page, css_selector=APL.ACTION_REASON_INPUT
    )
    reason_input.fill(TEST_REASON_TEXT)

    page.click(APL.ACTION_MODAL_SUBMIT)

    # data-reload-on-success triggers a full page reload; wait for it to settle
    page.wait_for_load_state("networkidle")

    # After reload the Erased row must read "yes"
    erased_cell_after = wait_then_get_element(
        page=page, css_selector=APL.USER_DETAIL_ERASED
    )
    expect(erased_cell_after).to_have_text("yes")

    # Username cell must show the tombstone value
    username_cell = wait_then_get_element(
        page=page, css_selector=APL.USER_DETAIL_USERNAME
    )
    expect(username_cell).to_have_text(f"{TOMBSTONE_USERNAME_PREFIX}{TARGET_USER_ID}")

    # The erased-NA span must be present; the Erase button must be gone
    erased_na = wait_then_get_element(
        page=page, css_selector=APL.USER_DETAIL_ACCOUNT_ERASED_NA
    )
    expect(erased_na).to_be_visible()
    expect(erased_na).to_have_text(UI_TEST_STRINGS.ADMIN_ACCOUNT_ERASED_NA)
    assert page.locator(APL.USER_DETAIL_ACCOUNT_ERASE_BTN).count() == 0

    # Verify DB state: username tombstoned
    with provide_app.app_context():
        target_user = Users.query.get(TARGET_USER_ID)
        assert target_user is not None
        assert target_user.username == f"{TOMBSTONE_USERNAME_PREFIX}{TARGET_USER_ID}"


def test_admin_account_email_verify_happy_path(
    page: Page,
    create_test_utubs,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
) -> None:
    """
    GIVEN an admin viewing a user's detail page with email_validated False
    WHEN the admin clicks Mark Email Verified, enters a reason, and confirms
    THEN the page reloads, the Email Validated row shows "yes", and the
         email-verified-NA span replaces the email-verify and email-resend buttons.
    """
    # Pre-set email_validated to False so the verify button renders
    with provide_app.app_context():
        target_user_to_unverify: Users = Users.query.get(TARGET_USER_ID)
        assert target_user_to_unverify is not None
        target_user_to_unverify.email_validated = False
        db.session.commit()

    login_admin_and_open_user_detail(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
        target_user_id=TARGET_USER_ID,
    )

    # Assert precondition: email is not validated before the action
    email_validated_cell = wait_then_get_element(
        page=page, css_selector=APL.USER_DETAIL_EMAIL_VALIDATED
    )
    expect(email_validated_cell).to_have_text("no")

    # The Mark Email Verified button must be present
    email_verify_btn = wait_then_get_element(
        page=page, css_selector=APL.USER_DETAIL_ACCOUNT_EMAIL_VERIFY_BTN
    )
    expect(email_verify_btn).to_be_visible()
    expect(email_verify_btn).to_have_text(
        UI_TEST_STRINGS.ADMIN_ACCOUNT_EMAIL_VERIFY_LABEL
    )

    email_verify_btn.click()

    modal_title = wait_then_get_element(page=page, css_selector=APL.ACTION_MODAL_TITLE)
    expect(modal_title).to_have_text(
        UI_TEST_STRINGS.ADMIN_ACCOUNT_EMAIL_VERIFY_CONFIRM_TITLE
    )

    reason_input = wait_then_get_element(
        page=page, css_selector=APL.ACTION_REASON_INPUT
    )
    reason_input.fill(TEST_REASON_TEXT)

    page.click(APL.ACTION_MODAL_SUBMIT)

    # data-reload-on-success triggers a full page reload; wait for it to settle
    page.wait_for_load_state("networkidle")

    # After reload the Email Validated row must read "yes"
    email_validated_cell_after = wait_then_get_element(
        page=page, css_selector=APL.USER_DETAIL_EMAIL_VALIDATED
    )
    expect(email_validated_cell_after).to_have_text("yes")

    # The email-verified-NA span must be present; verify and resend buttons must be gone
    email_verified_na = wait_then_get_element(
        page=page, css_selector=APL.USER_DETAIL_ACCOUNT_EMAIL_VERIFIED_NA
    )
    expect(email_verified_na).to_be_visible()
    expect(email_verified_na).to_have_text(
        UI_TEST_STRINGS.ADMIN_ACCOUNT_EMAIL_VERIFIED_NA
    )
    assert page.locator(APL.USER_DETAIL_ACCOUNT_EMAIL_VERIFY_BTN).count() == 0
    assert page.locator(APL.USER_DETAIL_ACCOUNT_EMAIL_RESEND_BTN).count() == 0

    # Verify DB state: email_validated is True
    with provide_app.app_context():
        target_user_after: Users = Users.query.get(TARGET_USER_ID)
        assert target_user_after is not None
        assert target_user_after.email_validated


def test_admin_account_oauth_unlink_last_credential_shows_na(
    page: Page,
    create_test_utubs,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
) -> None:
    """
    GIVEN an admin viewing a user's detail page where the account has no local
         password and exactly one OAuth identity
    WHEN the OAuth Identities panel renders
    THEN the identity row shows the ACCOUNT_UNLINK_NA muted span and no Unlink button.
    """
    # Seed an OAuth-only user (no local password, one OAuth identity)
    oauth_user_id = _seed_oauth_only_user(app=provide_app)

    login_admin_and_open_user_detail(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
        target_user_id=oauth_user_id,
    )

    # The OAuth identities panel must be present and show the table
    oauth_panel = wait_then_get_element(
        page=page, css_selector=APL.USER_DETAIL_OAUTH_PANEL
    )
    expect(oauth_panel).to_be_visible()

    oauth_table = wait_then_get_element(
        page=page, css_selector=APL.USER_DETAIL_OAUTH_TABLE
    )
    expect(oauth_table).to_be_visible()

    # The last-credential NA span must be present; the Unlink button must be absent
    unlink_na = wait_then_get_element(
        page=page, css_selector=APL.USER_DETAIL_OAUTH_UNLINK_NA
    )
    expect(unlink_na).to_be_visible()
    expect(unlink_na).to_have_text(UI_TEST_STRINGS.ADMIN_ACCOUNT_UNLINK_NA)
    assert page.locator(APL.USER_DETAIL_OAUTH_UNLINK_BTN).count() == 0
