from __future__ import annotations

import pytest
from flask import Flask
from playwright.sync_api import Page, expect

from backend.admin.health_service import STATUS_UP
from backend.config import ConfigTestUI
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS
from tests.functional.admin_ui.playwright_utils import (
    ADMIN_HEALTH_PATH,
    login_admin_and_open_admin_health,
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


def test_admin_health_renders_title_and_grid_for_admin(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
) -> None:
    """
    GIVEN a logged-in admin user
    WHEN the admin opens /admin/health
    THEN the page renders the health title with the correct text and, after
         the health-monitor controller loads the snapshot fragment, the
         AdminHealthGrid is present and the database card displays "up".
    """
    login_admin_and_open_admin_health(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
    )

    title_locator = wait_then_get_element(page=page, css_selector=APL.HEALTH_TITLE)
    expect(title_locator).to_have_text(UI_TEST_STRINGS.ADMIN_HEALTH_TITLE)

    # Wait for the health-monitor controller to fetch and swap in the snapshot fragment.
    health_grid_locator = wait_then_get_element(page=page, css_selector=APL.HEALTH_GRID)
    expect(health_grid_locator).to_be_visible()

    database_card_locator = wait_then_get_element(
        page=page, css_selector=APL.HEALTH_DATABASE_CARD
    )
    expect(database_card_locator).to_contain_text(STATUS_UP)


def test_admin_health_returns_403_for_non_admin(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
) -> None:
    """
    GIVEN a logged-in non-admin user (no role promotion)
    WHEN the user navigates to /admin/health
    THEN the HTTP response status is 403 Forbidden and the health title
         element is absent from the rendered page.
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

    navigation_response = page.goto(f"{full_base_url}{ADMIN_HEALTH_PATH}")

    assert navigation_response is not None
    assert navigation_response.status == 403
    assert page.locator(APL.HEALTH_TITLE).count() == 0
