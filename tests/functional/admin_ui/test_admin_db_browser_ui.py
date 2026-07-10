from __future__ import annotations

import pytest
from flask import Flask
from playwright.sync_api import Page, expect

from backend.config import ConfigTestUI
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS
from tests.functional.admin_ui.playwright_utils import (
    ADMIN_DB_BROWSER_USERS_PATH,
    login_admin_and_open_db_browser,
    login_admin_and_open_db_browser_table,
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

# A table seeded with no rows under `addmock users`, used for the empty-state
# assertion. Its token column is masked, but that only matters once rows exist.
_EMPTY_TABLE_NAME: str = "ApiRefreshTokens"

# Substrings that must never leak into the rendered Users grid — the password
# hash column is excluded, so neither its header nor the scrypt hash prefix of
# any seeded user may appear anywhere in the page body.
_PASSWORD_COLUMN_HEADER: str = "Password"
_SCRYPT_HASH_PREFIX: str = "scrypt:"


def test_admin_db_browser_overview_happy_path(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
) -> None:
    """
    GIVEN a logged-in admin user with seeded test users in the database
    WHEN the admin visits the native DB-browser overview at /admin/db
    THEN the DB-browser title renders the expected heading, the table-picker
         container is present, and at least one table card links into a grid.
    """
    login_admin_and_open_db_browser(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
    )

    title_locator = wait_then_get_element(page=page, css_selector=APL.DB_BROWSER_TITLE)
    expect(title_locator).to_be_visible()
    expect(title_locator).to_have_text(UI_TEST_STRINGS.ADMIN_PORTAL_DB_BROWSER_TITLE)

    expect(page.locator(APL.DB_TABLES)).to_be_visible()
    assert page.locator(APL.DB_TABLE_CARD).count() >= 1


def test_admin_db_browser_grid_happy_path_masks_password(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
) -> None:
    """
    GIVEN a logged-in admin user with seeded test users in the database
    WHEN the admin opens the Users grid at /admin/db/Users
    THEN the grid renders at least one row containing the first seeded
         username, no password column header or scrypt hash text leaks into the
         page, and the DB-browser nav link is marked active.
    """
    login_admin_and_open_db_browser_table(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
        table_name="Users",
    )

    grid_locator = wait_then_get_element(page=page, css_selector=APL.DB_TABLE_GRID)
    expect(grid_locator).to_be_visible()

    grid_row_locator = grid_locator.locator("tbody tr")
    expect(grid_row_locator.first).to_be_visible()
    assert grid_row_locator.count() >= 1
    expect(grid_locator).to_contain_text(UI_TEST_STRINGS.TEST_USERNAME_1)

    body_text: str = page.locator("body").inner_text()
    assert _PASSWORD_COLUMN_HEADER not in body_text
    assert _SCRYPT_HASH_PREFIX not in body_text

    db_browser_nav_link = page.locator(APL.NAV_DB_BROWSER)
    expect(db_browser_nav_link).to_have_class("admin-nav-link active")


def test_admin_db_browser_empty_table_shows_empty_state(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
) -> None:
    """
    GIVEN a logged-in admin user and a table seeded with no rows
    WHEN the admin opens that table's grid at /admin/db/ApiRefreshTokens
    THEN the empty-state panel renders the expected "no rows" message and the
         data grid is absent.
    """
    login_admin_and_open_db_browser_table(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
        table_name=_EMPTY_TABLE_NAME,
    )

    empty_locator = wait_then_get_element(page=page, css_selector=APL.DB_TABLE_EMPTY)
    expect(empty_locator).to_be_visible()
    expect(empty_locator).to_have_text(UI_TEST_STRINGS.ADMIN_PORTAL_DB_EMPTY_TABLE)
    assert page.locator(APL.DB_TABLE_GRID).count() == 0


def test_admin_db_browser_grid_returns_403_for_non_admin(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
) -> None:
    """
    GIVEN a logged-in non-admin user (no role promotion)
    WHEN the user navigates directly to the Users grid at /admin/db/Users
    THEN the HTTP response status is 403 Forbidden and the grid is absent.
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

    navigation_response = page.goto(f"{full_base_url}{ADMIN_DB_BROWSER_USERS_PATH}")

    assert navigation_response is not None
    assert navigation_response.status == 403
    assert page.locator(APL.DB_TABLE_GRID).count() == 0
