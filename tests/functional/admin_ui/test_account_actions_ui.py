"""Playwright UI tests for Phase 6 account-lifecycle admin actions.

Covers Suspend, Kill Sessions, and the self-view guard on the user-detail page.
"""

from __future__ import annotations

import pytest
from flask import Flask
from playwright.sync_api import Page, expect

from backend import db
from backend.config import ConfigTestUI
from backend.models.users import Users
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS
from tests.functional.admin_ui.playwright_utils import login_admin_and_open_user_detail
from tests.functional.locators import AdminPortalLocators as APL
from tests.functional.playwright_utils import wait_then_get_element

pytestmark = pytest.mark.admin_ui

DEFAULT_ADMIN_USER_ID: int = 1
# User 2 is a non-admin account available in every create_test_utubs fixture run.
TARGET_USER_ID: int = 2

TEST_REASON_TEXT: str = "automated account actions test"


def test_admin_account_suspend_happy_path(
    page: Page,
    create_test_utubs,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
) -> None:
    """
    GIVEN an admin viewing a non-admin user's detail page with the account not suspended
    WHEN the admin clicks Suspend, enters a reason, and confirms
    THEN the page reloads, the Suspended row shows "yes", and the Unsuspend button
         replaces the Suspend button in the Account Actions panel.
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

    # Assert precondition: user is not suspended before the action
    suspended_cell = wait_then_get_element(
        page=page, css_selector=APL.USER_DETAIL_SUSPENDED
    )
    expect(suspended_cell).to_have_text("no")

    # The Suspend button must be present (not yet suspended)
    suspend_btn = wait_then_get_element(
        page=page, css_selector=APL.USER_DETAIL_ACCOUNT_SUSPEND_BTN
    )
    expect(suspend_btn).to_be_visible()
    expect(suspend_btn).to_have_text(UI_TEST_STRINGS.ADMIN_ACCOUNT_SUSPEND_LABEL)

    suspend_btn.click()

    modal_title = wait_then_get_element(page=page, css_selector=APL.ACTION_MODAL_TITLE)
    expect(modal_title).to_have_text(
        UI_TEST_STRINGS.ADMIN_ACCOUNT_SUSPEND_CONFIRM_TITLE
    )

    reason_input = wait_then_get_element(
        page=page, css_selector=APL.ACTION_REASON_INPUT
    )
    reason_input.fill(TEST_REASON_TEXT)

    page.click(APL.ACTION_MODAL_SUBMIT)

    # data-reload-on-success triggers a full page reload; wait for it to settle
    page.wait_for_load_state("networkidle")

    # After reload the Suspended row must read "yes"
    suspended_cell_after = wait_then_get_element(
        page=page, css_selector=APL.USER_DETAIL_SUSPENDED
    )
    expect(suspended_cell_after).to_have_text("yes")

    # The Unsuspend button must be present; the Suspend button must be gone
    assert page.locator(APL.USER_DETAIL_ACCOUNT_UNSUSPEND_BTN).count() == 1
    assert page.locator(APL.USER_DETAIL_ACCOUNT_SUSPEND_BTN).count() == 0

    # Verify DB state reflects the suspension
    with provide_app.app_context():
        target_user = Users.query.get(TARGET_USER_ID)
        assert target_user is not None
        assert target_user.is_suspended is True


def test_admin_account_kill_sessions_happy_path(
    page: Page,
    create_test_utubs,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
) -> None:
    """
    GIVEN an admin viewing a non-admin user's detail page
    WHEN the admin clicks Kill Sessions, enters a reason, and confirms
    THEN the inline result beneath the Kill Sessions button becomes visible and
         contains the expected success substring (no page reload for kill-sessions).
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

    kill_sessions_btn = wait_then_get_element(
        page=page, css_selector=APL.USER_DETAIL_ACCOUNT_KILL_SESSIONS_BTN
    )
    expect(kill_sessions_btn).to_be_visible()
    expect(kill_sessions_btn).to_have_text(
        UI_TEST_STRINGS.ADMIN_ACCOUNT_KILL_SESSIONS_LABEL
    )

    kill_sessions_btn.click()

    modal_title = wait_then_get_element(page=page, css_selector=APL.ACTION_MODAL_TITLE)
    expect(modal_title).to_have_text(
        UI_TEST_STRINGS.ADMIN_ACCOUNT_KILL_SESSIONS_CONFIRM_TITLE
    )

    reason_input = wait_then_get_element(
        page=page, css_selector=APL.ACTION_REASON_INPUT
    )
    reason_input.fill(TEST_REASON_TEXT)

    page.click(APL.ACTION_MODAL_SUBMIT)

    # No reload-on-success for kill-sessions; success renders inline beneath the button
    result_region = wait_then_get_element(
        page=page, css_selector=APL.USER_DETAIL_ACCOUNT_KILL_SESSIONS_RESULT
    )
    expect(result_region).to_be_visible()
    expect(result_region).to_contain_text(
        UI_TEST_STRINGS.ADMIN_ACCOUNT_KILL_SESSIONS_SUCCESS_SUBSTRING
    )


def test_admin_account_self_view_shows_note_no_buttons(
    page: Page,
    create_test_utubs,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
) -> None:
    """
    GIVEN an admin viewing their OWN user detail page
    WHEN the Account Actions panel renders
    THEN only the self-actions note is shown and no account action buttons are present.
    """
    login_admin_and_open_user_detail(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
        target_user_id=DEFAULT_ADMIN_USER_ID,
    )

    # The Account Actions panel must be present
    account_actions_panel = wait_then_get_element(
        page=page, css_selector=APL.USER_DETAIL_ACCOUNT_ACTIONS
    )
    expect(account_actions_panel).to_be_visible()

    # The self-actions note must be visible
    self_note = wait_then_get_element(
        page=page, css_selector=APL.USER_DETAIL_SELF_ACTIONS_NOTE
    )
    expect(self_note).to_be_visible()
    expect(self_note).to_have_text(UI_TEST_STRINGS.ADMIN_ACCOUNT_SELF_ACTIONS_NA)

    # No account action buttons must appear
    assert page.locator(APL.USER_DETAIL_ACCOUNT_SUSPEND_BTN).count() == 0
    assert page.locator(APL.USER_DETAIL_ACCOUNT_UNSUSPEND_BTN).count() == 0
    assert page.locator(APL.USER_DETAIL_ACCOUNT_KILL_SESSIONS_BTN).count() == 0
    assert page.locator(APL.USER_DETAIL_ACCOUNT_FORCE_RESET_BTN).count() == 0


def test_admin_account_unsuspend_happy_path(
    page: Page,
    create_test_utubs,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
) -> None:
    """
    GIVEN an admin viewing a suspended user's detail page
    WHEN the admin clicks Unsuspend, enters a reason, and confirms
    THEN the page reloads, the Suspended row shows "no", and the Suspend button
         replaces the Unsuspend button in the Account Actions panel.
    """
    # Pre-suspend the target user directly in the DB before navigating to the page
    with provide_app.app_context():
        target_user_to_suspend: Users = Users.query.get(TARGET_USER_ID)
        assert target_user_to_suspend is not None
        target_user_to_suspend.is_suspended = True
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

    # Assert precondition: user is suspended before the action
    suspended_cell = wait_then_get_element(
        page=page, css_selector=APL.USER_DETAIL_SUSPENDED
    )
    expect(suspended_cell).to_have_text("yes")

    # The Unsuspend button must be present
    unsuspend_btn = wait_then_get_element(
        page=page, css_selector=APL.USER_DETAIL_ACCOUNT_UNSUSPEND_BTN
    )
    expect(unsuspend_btn).to_be_visible()
    expect(unsuspend_btn).to_have_text(UI_TEST_STRINGS.ADMIN_ACCOUNT_UNSUSPEND_LABEL)

    unsuspend_btn.click()

    modal_title = wait_then_get_element(page=page, css_selector=APL.ACTION_MODAL_TITLE)
    expect(modal_title).to_have_text(
        UI_TEST_STRINGS.ADMIN_ACCOUNT_UNSUSPEND_CONFIRM_TITLE
    )

    reason_input = wait_then_get_element(
        page=page, css_selector=APL.ACTION_REASON_INPUT
    )
    reason_input.fill(TEST_REASON_TEXT)

    page.click(APL.ACTION_MODAL_SUBMIT)

    # data-reload-on-success triggers a full page reload; wait for it to settle
    page.wait_for_load_state("networkidle")

    # After reload the Suspended row must read "no"
    suspended_cell_after = wait_then_get_element(
        page=page, css_selector=APL.USER_DETAIL_SUSPENDED
    )
    expect(suspended_cell_after).to_have_text("no")

    # The Suspend button must be present; the Unsuspend button must be gone
    assert page.locator(APL.USER_DETAIL_ACCOUNT_SUSPEND_BTN).count() == 1
    assert page.locator(APL.USER_DETAIL_ACCOUNT_UNSUSPEND_BTN).count() == 0

    # Verify DB state reflects the unsuspension
    with provide_app.app_context():
        target_user_after: Users = Users.query.get(TARGET_USER_ID)
        assert target_user_after is not None
        assert not target_user_after.is_suspended


def test_admin_account_force_password_reset_happy_path(
    page: Page,
    create_test_utubs,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
) -> None:
    """
    GIVEN an admin viewing a non-OAuth user's detail page with no existing
         Forgot_Passwords row
    WHEN the admin clicks Force Password Reset, enters a reason, and confirms
    THEN the inline result beneath the Force Password Reset button becomes visible
         with the success message and a Forgot_Passwords row is created for the
         target user in the DB.
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

    force_reset_btn = wait_then_get_element(
        page=page, css_selector=APL.USER_DETAIL_ACCOUNT_FORCE_RESET_BTN
    )
    expect(force_reset_btn).to_be_visible()
    expect(force_reset_btn).to_have_text(
        UI_TEST_STRINGS.ADMIN_ACCOUNT_FORCE_RESET_LABEL
    )

    force_reset_btn.click()

    modal_title = wait_then_get_element(page=page, css_selector=APL.ACTION_MODAL_TITLE)
    expect(modal_title).to_have_text(
        UI_TEST_STRINGS.ADMIN_ACCOUNT_FORCE_RESET_CONFIRM_TITLE
    )

    reason_input = wait_then_get_element(
        page=page, css_selector=APL.ACTION_REASON_INPUT
    )
    reason_input.fill(TEST_REASON_TEXT)

    page.click(APL.ACTION_MODAL_SUBMIT)

    # No reload-on-success for force-reset; success renders inline beneath the button
    result_region = wait_then_get_element(
        page=page, css_selector=APL.USER_DETAIL_ACCOUNT_FORCE_RESET_RESULT
    )
    expect(result_region).to_be_visible()
    expect(result_region).to_contain_text(
        UI_TEST_STRINGS.ADMIN_ACCOUNT_FORCE_RESET_SUCCESS
    )

    # Verify DB state: Forgot_Passwords row created for the target user
    with provide_app.app_context():
        target_user_after: Users = Users.query.get(TARGET_USER_ID)
        assert target_user_after is not None
        assert target_user_after.forgot_password is not None
