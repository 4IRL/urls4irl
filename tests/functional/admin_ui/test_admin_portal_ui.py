from __future__ import annotations

import pytest
from flask import Flask
from playwright.sync_api import Page, expect

from backend.config import ConfigTestUI
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS
from tests.functional.admin_ui.playwright_utils import (
    ADMIN_PORTAL_PATH,
    login_admin_and_open_admin_portal,
)
from tests.functional.locators import AdminPortalLocators as APL
from tests.functional.playwright_utils import (
    create_user_session_and_provide_session_id,
    login_user_with_cookie_from_session,
    wait_then_get_element,
)

pytestmark = pytest.mark.admin_ui

DEFAULT_ADMIN_USER_ID: int = 1
# `addmock users` promotes user 1 to ADMIN, so the non-admin path must use a
# different seeded user that never receives the role.
NON_ADMIN_USER_ID: int = 2


def test_admin_portal_renders_title_and_nav_for_admin(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
) -> None:
    """
    GIVEN a logged-in admin user
    WHEN the admin opens /admin
    THEN the page renders the portal title with the correct text and all
         expected nav links are visible with their correct text labels.
    """
    login_admin_and_open_admin_portal(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
    )

    title_locator = wait_then_get_element(page=page, css_selector=APL.PORTAL_TITLE)
    expect(title_locator).to_have_text(UI_TEST_STRINGS.ADMIN_PORTAL_TITLE)

    expect(page.locator(APL.NAV)).to_be_visible()

    nav_health = wait_then_get_element(page=page, css_selector=APL.NAV_HEALTH)
    expect(nav_health).to_be_visible()
    expect(nav_health).to_have_text(UI_TEST_STRINGS.ADMIN_PORTAL_NAV_HEALTH)

    nav_db_browser = wait_then_get_element(page=page, css_selector=APL.NAV_DB_BROWSER)
    expect(nav_db_browser).to_be_visible()
    expect(nav_db_browser).to_have_text(UI_TEST_STRINGS.ADMIN_PORTAL_NAV_DB_BROWSER)

    nav_users = wait_then_get_element(page=page, css_selector=APL.NAV_USERS)
    expect(nav_users).to_be_visible()
    expect(nav_users).to_have_text(UI_TEST_STRINGS.ADMIN_PORTAL_NAV_USERS)

    nav_audit_log = wait_then_get_element(page=page, css_selector=APL.NAV_AUDIT_LOG)
    expect(nav_audit_log).to_be_visible()
    expect(nav_audit_log).to_have_text(UI_TEST_STRINGS.ADMIN_PORTAL_NAV_AUDIT_LOG)

    nav_metrics = wait_then_get_element(page=page, css_selector=APL.NAV_METRICS)
    expect(nav_metrics).to_be_visible()
    expect(nav_metrics).to_have_text(UI_TEST_STRINGS.ADMIN_PORTAL_NAV_METRICS)


def test_admin_portal_returns_403_for_non_admin(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
) -> None:
    """
    GIVEN a logged-in non-admin user (no role promotion)
    WHEN the user navigates to /admin
    THEN the HTTP response status is 403 Forbidden and the admin portal
         title element is absent from the rendered page.
    """
    base_url = (
        UI_TEST_STRINGS.DOCKER_BASE_URL
        if provide_config.DOCKER
        else UI_TEST_STRINGS.BASE_URL
    )
    full_base_url = f"{base_url}{provide_port}"

    session_id = create_user_session_and_provide_session_id(
        app=provide_app, user_id=NON_ADMIN_USER_ID
    )
    login_user_with_cookie_from_session(
        context=page.context, session_id=session_id, base_url=full_base_url
    )

    navigation_response = page.goto(f"{full_base_url}{ADMIN_PORTAL_PATH}")

    assert navigation_response is not None
    assert navigation_response.status == 403
    assert page.locator(APL.PORTAL_TITLE).count() == 0
