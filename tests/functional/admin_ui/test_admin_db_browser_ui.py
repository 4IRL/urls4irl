from __future__ import annotations

import pytest
from flask import Flask
from playwright.sync_api import Page, expect

from backend.config import ConfigTestUI
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS
from tests.functional.admin_ui.playwright_utils import (
    ADMIN_DB_BROWSER_USERS_PATH,
    login_admin_and_open_db_browser_users,
)
from tests.functional.playwright_utils import (
    create_user_session_and_provide_session_id,
    login_user_with_cookie_from_session,
)

pytestmark = pytest.mark.admin_ui

DEFAULT_ADMIN_USER_ID: int = 1
# `addmock users` promotes user 1 to ADMIN, so the non-admin path must use a
# different seeded user that never receives the role.
NON_ADMIN_USER_ID: int = 2

_EDIT_LINK_SELECTOR: str = "a[href*='/admin/db/users/edit/']"
_DELETE_FORM_SELECTOR: str = "form[action*='/admin/db/users/delete/']"
_PASSWORD_HEADER_SELECTOR: str = "table thead th:has-text('Password')"
_TABLE_BODY_ROWS_SELECTOR: str = "table tbody tr"
_TABLE_BODY_SELECTOR: str = "table tbody"


def test_admin_db_browser_users_list_renders_rows_and_excludes_password_column(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
) -> None:
    """
    GIVEN a logged-in admin user with seeded Users rows
    WHEN the admin opens /admin/db/users/
    THEN at least one table row is rendered containing the seeded admin username;
         no edit links appear in the table (can_edit=False);
         no delete form appears in the page (can_delete=False);
         and the "Password" column header is absent from the table (column excluded).
    """
    login_admin_and_open_db_browser_users(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
    )

    # At least one data row must be present and contain the admin's username.
    table_body_locator = page.locator(_TABLE_BODY_SELECTOR)
    expect(table_body_locator).to_contain_text(UI_TEST_STRINGS.TEST_USERNAME_1)
    assert page.locator(_TABLE_BODY_ROWS_SELECTOR).count() >= 1

    # Read-only enforcement: no edit links and no delete form in the rendered page.
    assert page.locator(_EDIT_LINK_SELECTOR).count() == 0
    assert page.locator(_DELETE_FORM_SELECTOR).count() == 0

    # Sensitive column exclusion: "Password" header must not appear in the
    # table header row (column_exclude_list = ["password"] on the Users view).
    assert page.locator(_PASSWORD_HEADER_SELECTOR).count() == 0


def test_admin_db_browser_users_list_returns_403_for_non_admin(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
) -> None:
    """
    GIVEN a logged-in non-admin user (no role promotion)
    WHEN the user navigates to /admin/db/users/
    THEN the HTTP response status is 403 Forbidden.
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
