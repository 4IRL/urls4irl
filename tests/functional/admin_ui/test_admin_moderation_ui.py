"""Playwright UI tests for Phase 4 content-moderation admin actions.

Covers the Lock/Unlock UTub controls on the user-detail page and the
URL-purge control on the DB-browser Urls row-detail page.
"""

from __future__ import annotations

import pytest
from flask import Flask
from playwright.sync_api import Page, expect

from backend.config import ConfigTestUI
from backend.models.urls import Urls
from backend.models.utub_urls import Utub_Urls
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS
from tests.functional.admin_ui.playwright_utils import (
    login_admin_and_open_db_row,
    login_admin_and_open_user_detail,
)
from tests.functional.locators import AdminPortalLocators as APL
from tests.functional.playwright_utils import wait_then_get_element

pytestmark = pytest.mark.admin_ui

DEFAULT_ADMIN_USER_ID: int = 1
# User 2 owns UTub 2 (as CREATOR) after `addmock utubs`; user 1 is promoted to
# ADMIN so we view user 2's detail page to avoid self-action restrictions.
TARGET_USER_ID: int = 2

TEST_REASON_TEXT: str = "automated moderation test"


def test_admin_mod_utub_lock_happy_path(
    page: Page,
    create_test_utubs,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
) -> None:
    """
    GIVEN an admin viewing user 2's detail page with one unlocked UTub membership
    WHEN the admin clicks the Lock button, enters a reason, and confirms
    THEN the page reloads, the UTub name cell shows a locked badge, and the
         Unlock button replaces the Lock button in the Moderation column.
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

    memberships_table = wait_then_get_element(
        page=page, css_selector=APL.USER_DETAIL_MEMBERSHIPS_TABLE
    )
    expect(memberships_table).to_be_visible()

    # Assert no locked badge before the action
    assert page.locator(APL.USER_DETAIL_LOCKED_BADGE).count() == 0

    # Click the Lock button
    lock_btn = wait_then_get_element(
        page=page, css_selector=APL.USER_DETAIL_MOD_LOCK_BTN
    )
    lock_btn.click()

    modal_title = wait_then_get_element(page=page, css_selector=APL.ACTION_MODAL_TITLE)
    expect(modal_title).to_have_text(UI_TEST_STRINGS.ADMIN_MOD_UTUB_LOCK_CONFIRM_TITLE)

    reason_input = wait_then_get_element(
        page=page, css_selector=APL.ACTION_REASON_INPUT
    )
    reason_input.fill(TEST_REASON_TEXT)

    page.click(APL.ACTION_MODAL_SUBMIT)

    # data-reload-on-success triggers a full page reload; wait for it to settle
    page.wait_for_load_state("networkidle")

    # After reload the locked badge must be visible in the memberships table
    locked_badge = wait_then_get_element(
        page=page, css_selector=APL.USER_DETAIL_LOCKED_BADGE
    )
    expect(locked_badge).to_be_visible()
    expect(locked_badge).to_have_text(UI_TEST_STRINGS.ADMIN_MOD_LOCKED_BADGE)

    # The Unlock button should now be present and Lock button absent
    assert page.locator(APL.USER_DETAIL_MOD_UNLOCK_BTN).count() == 1
    assert page.locator(APL.USER_DETAIL_MOD_LOCK_BTN).count() == 0


def test_admin_mod_utub_lock_reason_required(
    page: Page,
    create_test_utubs,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
) -> None:
    """
    GIVEN an admin viewing user 2's detail page with one unlocked UTub membership
    WHEN the admin opens the Lock modal and submits without entering a reason
    THEN the modal alert banner shows the reason-required message and the UTub
         remains unlocked (no locked badge appears on the page).
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

    wait_then_get_element(page=page, css_selector=APL.USER_DETAIL_MEMBERSHIPS_TABLE)

    lock_btn = wait_then_get_element(
        page=page, css_selector=APL.USER_DETAIL_MOD_LOCK_BTN
    )
    lock_btn.click()

    wait_then_get_element(page=page, css_selector=APL.ACTION_MODAL_TITLE)

    # Submit without providing a reason
    page.click(APL.ACTION_MODAL_SUBMIT)

    # The modal alert banner must appear with the reason-required message
    alert_banner = wait_then_get_element(
        page=page, css_selector=APL.ACTION_MODAL_ALERT_BANNER
    )
    expect(alert_banner).to_be_visible()
    expect(alert_banner).to_have_text(UI_TEST_STRINGS.ADMIN_ACTION_REASON_REQUIRED)

    # Modal stays open; no reload has occurred so the locked badge must be absent
    assert page.locator(APL.USER_DETAIL_LOCKED_BADGE).count() == 0


def test_admin_mod_url_purge_control_and_happy_path(
    page: Page,
    create_test_urls,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
) -> None:
    """
    GIVEN an admin viewing the Urls row-detail page for a seeded URL that
         exists in at least one UTub
    WHEN the purge button is present and the admin clicks it, enters a reason,
         and confirms
    THEN the #AdminActionResult region shows a success message containing
         "URL purged from" and the DB contains no UtubUrls rows for that URL.
    """
    # Retrieve the first seeded URL's id within the app context
    with provide_app.app_context():
        first_url = Urls.query.order_by(Urls.id.asc()).first()
        assert first_url is not None, "No URLs seeded — fixture may have failed"
        url_id = first_url.id

    login_admin_and_open_db_row(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
        table_name="Urls",
        row_pk=url_id,
    )

    # The row-detail table must be visible
    wait_then_get_element(page=page, css_selector=APL.DB_ROW_DETAIL)

    # The moderation section and purge button must render for the Urls table
    mod_section = wait_then_get_element(page=page, css_selector=APL.DB_ROW_MOD_SECTION)
    expect(mod_section).to_be_visible()

    purge_btn = wait_then_get_element(
        page=page, css_selector=APL.DB_ROW_MOD_URL_PURGE_BTN
    )
    expect(purge_btn).to_be_visible()
    expect(purge_btn).to_have_text(UI_TEST_STRINGS.ADMIN_MOD_URL_PURGE_LABEL)

    # Click the purge button, fill reason, confirm
    purge_btn.click()

    modal_title = wait_then_get_element(page=page, css_selector=APL.ACTION_MODAL_TITLE)
    expect(modal_title).to_have_text(UI_TEST_STRINGS.ADMIN_MOD_URL_PURGE_CONFIRM_TITLE)

    reason_input = wait_then_get_element(
        page=page, css_selector=APL.ACTION_REASON_INPUT
    )
    reason_input.fill(TEST_REASON_TEXT)

    page.click(APL.ACTION_MODAL_SUBMIT)

    # No reload-on-success for url-purge; success renders in #AdminActionResult
    result_region = wait_then_get_element(
        page=page, css_selector=APL.ACTION_RESULT_REGION
    )
    expect(result_region).to_be_visible()
    expect(result_region).to_contain_text(
        UI_TEST_STRINGS.ADMIN_MOD_URL_PURGE_SUCCESS_PREFIX
    )

    # Verify via DB that no UtubUrls rows remain for this URL
    with provide_app.app_context():
        remaining_associations = Utub_Urls.query.filter_by(url_id=url_id).count()
    assert remaining_associations == 0, (
        f"Expected 0 UtubUrls rows for url_id={url_id} after purge, "
        f"found {remaining_associations}"
    )
