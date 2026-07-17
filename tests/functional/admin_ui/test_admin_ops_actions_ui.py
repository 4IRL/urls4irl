from __future__ import annotations

import pytest
from flask import Flask
from playwright.sync_api import Page, expect

from backend.config import ConfigTestUI
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS
from tests.functional.admin_ui.playwright_utils import (
    login_admin_and_open_system_operations,
)
from tests.functional.locators import AdminPortalLocators as APL
from tests.functional.playwright_utils import (
    wait_then_get_element,
    wait_until_css_property,
)

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
    GIVEN a logged-in admin user on /admin/system-operations
    WHEN the admin clicks the Verify Tables ops button, types a reason into
         the confirm modal, and confirms
    THEN the confirm modal opens with the verify-tables title, the POST
         succeeds, and the inline result beneath the Verify button shows the
         all-tables-present message.
    """
    login_admin_and_open_system_operations(
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
        page=page, css_selector=APL.OPS_VERIFY_TABLES_RESULT
    )
    expect(result_region_locator).to_have_text(UI_TEST_STRINGS.ADMIN_OPS_VERIFY_OK)


def test_admin_ops_backup_trigger_button_renders(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
) -> None:
    """
    GIVEN a logged-in admin user on /admin/system-operations
    WHEN the Operations panel renders
    THEN the Trigger Backup ops button is present and visible. (The Daily
         Backup status card lives on /admin/health and is covered by the
         health UI suite.)
    """
    login_admin_and_open_system_operations(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
    )

    trigger_button_locator = wait_then_get_element(
        page=page, css_selector=APL.OPS_BACKUP_TRIGGER_BTN
    )
    expect(trigger_button_locator).to_be_visible()


def test_admin_ops_cards_render_descriptions(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
) -> None:
    """
    GIVEN a logged-in admin user on /admin/system-operations
    WHEN the Operations panel renders
    THEN each operation shows as a card with an always-visible one-line
         description (the Verify Tables description is asserted specifically).
    """
    login_admin_and_open_system_operations(
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

    verify_tables_desc_locator = page.locator(
        APL.OPS_CARD_DESC,
        has_text=UI_TEST_STRINGS.ADMIN_OPS_VERIFY_TABLES_DESC,
    )
    expect(verify_tables_desc_locator).to_be_visible()


def test_admin_ops_reason_required(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
) -> None:
    """
    GIVEN a logged-in admin user on /admin/system-operations
    WHEN the admin opens the Verify Tables modal and submits without a reason
    THEN the modal alert banner shows the reason-required message and no inline
         result is created (the ops POST never fired).
    """
    login_admin_and_open_system_operations(
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
    wait_then_get_element(page=page, css_selector=APL.ACTION_MODAL_TITLE)

    # Submit without providing a reason
    page.click(APL.ACTION_MODAL_SUBMIT)

    alert_banner = wait_then_get_element(
        page=page, css_selector=APL.ACTION_MODAL_ALERT_BANNER
    )
    expect(alert_banner).to_be_visible()
    expect(alert_banner).to_have_text(UI_TEST_STRINGS.ADMIN_ACTION_REASON_REQUIRED)
    expect(page.locator(APL.ACTION_INLINE_RESULT)).to_have_count(0)


def test_admin_ops_modal_dismiss_makes_no_request(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
) -> None:
    """
    GIVEN a logged-in admin user on /admin/system-operations with the verify-tables
          confirm modal open
    WHEN the admin dismisses the modal without confirming
    THEN no inline result is created — no ops POST was performed.
    """
    login_admin_and_open_system_operations(
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

    # Gate on the fade-in being fully settled (opacity 1) before dismissing:
    # clicking mid-transition makes Bootstrap drop the subsequent modal("hide"),
    # leaving the modal visible and racing the to_be_hidden check under load.
    wait_until_css_property(
        page=page,
        css_selector=APL.ACTION_CONFIRM_MODAL,
        css_property="opacity",
        expected_value="1",
    )
    page.click("#modalDismiss")

    expect(page.locator(APL.ACTION_CONFIRM_MODAL)).to_be_hidden()
    # No action ran, so no inline result was ever created.
    expect(page.locator(APL.ACTION_INLINE_RESULT)).to_have_count(0)
