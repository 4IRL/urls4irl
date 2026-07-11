from __future__ import annotations

import pytest
from flask import Flask
from playwright.sync_api import Page, expect

from backend.config import ConfigTestUI
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS
from tests.functional.admin_ui.playwright_utils import (
    login_admin_and_open_admin_health,
)
from tests.functional.locators import AdminPortalLocators as APL
from tests.functional.playwright_utils import wait_then_get_element

pytestmark = pytest.mark.admin_ui

DEFAULT_ADMIN_USER_ID: int = 1
TEST_REASON_TEXT: str = "routine maintenance check"


def test_admin_ops_verify_tables_happy_path(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
) -> None:
    """
    GIVEN a logged-in admin user on /admin/health
    WHEN the admin clicks the Verify Tables ops button, types a reason into
         the confirm modal, and confirms
    THEN the confirm modal opens with the verify-tables title, the POST
         succeeds, and the result region shows the all-tables-present message.
    """
    login_admin_and_open_admin_health(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
    )

    ops_section_locator = wait_then_get_element(page=page, css_selector=APL.OPS_SECTION)
    expect(ops_section_locator).to_be_visible()

    page.click(APL.OPS_VERIFY_TABLES_BTN)

    modal_title_locator = wait_then_get_element(
        page=page, css_selector=APL.ACTION_MODAL_TITLE
    )
    expect(modal_title_locator).to_have_text(
        UI_TEST_STRINGS.ADMIN_OPS_VERIFY_TABLES_CONFIRM_TITLE
    )

    reason_input_locator = wait_then_get_element(
        page=page, css_selector=APL.ACTION_REASON_INPUT
    )
    reason_input_locator.fill(TEST_REASON_TEXT)

    page.click(APL.ACTION_MODAL_SUBMIT)

    result_region_locator = wait_then_get_element(
        page=page, css_selector=APL.ACTION_RESULT_REGION
    )
    expect(result_region_locator).to_have_text(UI_TEST_STRINGS.ADMIN_OPS_VERIFY_OK)


def test_admin_health_backup_card_and_trigger_button_render(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
) -> None:
    """
    GIVEN a logged-in admin user on /admin/health
    WHEN the health snapshot fragment loads
    THEN the Daily Backup status card renders (showing "never" when no backup
         has been stamped) and the Trigger Backup ops button is present.
    """
    login_admin_and_open_admin_health(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
    )

    backup_card_locator = wait_then_get_element(
        page=page, css_selector=APL.HEALTH_BACKUP_CARD
    )
    expect(backup_card_locator).to_be_visible()

    trigger_button_locator = wait_then_get_element(
        page=page, css_selector=APL.OPS_BACKUP_TRIGGER_BTN
    )
    expect(trigger_button_locator).to_be_visible()


def test_admin_ops_modal_dismiss_makes_no_request(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
) -> None:
    """
    GIVEN a logged-in admin user on /admin/health with the verify-tables
          confirm modal open
    WHEN the admin dismisses the modal without confirming
    THEN the result region stays empty — no ops POST was performed.
    """
    login_admin_and_open_admin_health(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
    )

    expect(
        wait_then_get_element(page=page, css_selector=APL.OPS_SECTION)
    ).to_be_visible()

    page.click(APL.OPS_VERIFY_TABLES_BTN)
    expect(
        wait_then_get_element(page=page, css_selector=APL.ACTION_MODAL_TITLE)
    ).to_have_text(UI_TEST_STRINGS.ADMIN_OPS_VERIFY_TABLES_CONFIRM_TITLE)

    page.click("#modalDismiss")

    expect(page.locator(APL.ACTION_CONFIRM_MODAL)).to_be_hidden()
    expect(page.locator(APL.ACTION_RESULT_REGION)).to_have_text("")
