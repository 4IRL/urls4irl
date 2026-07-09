from __future__ import annotations

import pytest
from flask import Flask
from playwright.sync_api import Page, expect

from backend.config import ConfigTestUI
from backend.utils.strings.admin_portal_strs import ADMIN_AUDIT_ACTIONS
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS
from tests.functional.admin_ui.playwright_utils import (
    ADMIN_AUDIT_LOG_PATH,
    ADMIN_USERS_PATH,
    login_admin_and_open_audit_log,
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

# The metadata key emitted by the admin_users_search route for every search.
# Defined here as a module constant so the test is self-contained — it matches
# the dict key in backend/admin/routes.py admin_users_search() metadata kwarg.
_USER_SEARCH_METADATA_KEY: str = "result_count"

# Action substring used to filter admin.user.search rows in the happy-path test.
_USER_SEARCH_ACTION_SUBSTRING: str = "user.search"


def test_admin_audit_log_happy_path_filter_and_metadata_expand(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
) -> None:
    """
    GIVEN a logged-in admin user with seeded test users in the database
    WHEN the admin first visits /admin/users (producing at least one
         admin.user.search audit row from the htmx load-triggered fragment),
         then navigates to /admin/audit-log
    THEN the audit log table loads (the page-view itself adds an
         admin.audit_log.view row, so ≥1 row always exists); after typing
         "user.search" into the action filter input and waiting for the htmx
         debounce swap, only admin.user.search rows are visible; expanding a
         metadata <details> element reveals a <pre> block containing the
         "result_count" key.
    """
    base_url = (
        UI_TEST_STRINGS.DOCKER_BASE_URL
        if provide_config.DOCKER
        else UI_TEST_STRINGS.BASE_URL
    )
    full_base_url = f"{base_url}{provide_port}"

    # Promote and log in via session cookie, then seed an audit row by hitting
    # the users page (which auto-fires the load-triggered search fragment).
    login_admin_and_open_audit_log(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
    )

    # Before filtering: navigate to /admin/users first to ensure at least one
    # admin.user.search audit row exists in the log (from the auto-fired
    # htmx fragment on that page). Use goto so the session cookie is already
    # set by login_admin_and_open_audit_log above.
    page.goto(f"{full_base_url}{ADMIN_USERS_PATH}")

    # Return to the audit-log page. The page view itself records AUDIT_LOG_VIEW.
    page.goto(f"{full_base_url}{ADMIN_AUDIT_LOG_PATH}")

    # Wait for the htmx load-triggered swap to populate #AdminAuditLogTable.
    audit_table_locator = wait_then_get_element(
        page=page, css_selector=APL.AUDIT_LOG_TABLE
    )
    expect(audit_table_locator).to_be_visible()

    # The table must have at least one row (audit_log.view was just recorded).
    audit_rows_locator = page.locator(APL.AUDIT_LOG_ROW)
    expect(audit_rows_locator.first).to_be_visible()

    # Type into the action filter to narrow results to admin.user.search rows.
    action_filter_locator = page.locator(APL.AUDIT_FILTER_ACTION)
    action_filter_locator.fill(_USER_SEARCH_ACTION_SUBSTRING)

    # Wait for the debounced htmx swap deterministically: the unfiltered
    # table always contains this page visit's own admin.audit_log.view row,
    # which the "user.search" filter excludes — so its disappearance proves
    # the filtered fragment replaced the initial one. expect() auto-retries.
    audit_results_region = page.locator(APL.AUDIT_LOG_RESULTS)
    expect(audit_results_region).not_to_contain_text(ADMIN_AUDIT_ACTIONS.AUDIT_LOG_VIEW)
    expect(audit_rows_locator.first).to_be_visible()

    # Every visible row's text must contain the filtered action substring.
    row_count: int = audit_rows_locator.count()
    assert row_count >= 1
    for row_index in range(row_count):
        row_text: str = audit_rows_locator.nth(row_index).inner_text()
        assert _USER_SEARCH_ACTION_SUBSTRING in row_text, (
            f"Row {row_index} text does not contain '{_USER_SEARCH_ACTION_SUBSTRING}': "
            f"{row_text!r}"
        )

    # Expand the first metadata <details> element and assert the <pre> content.
    first_metadata_details = page.locator(APL.AUDIT_METADATA_DETAILS).first
    first_metadata_details.locator("summary").click()
    metadata_pre = first_metadata_details.locator("pre")
    expect(metadata_pre).to_contain_text(_USER_SEARCH_METADATA_KEY)


def test_admin_audit_log_returns_403_for_non_admin(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
) -> None:
    """
    GIVEN a logged-in non-admin user (no role promotion)
    WHEN the user navigates to /admin/audit-log
    THEN the HTTP response status is 403 Forbidden and the audit-log title
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

    navigation_response = page.goto(f"{full_base_url}{ADMIN_AUDIT_LOG_PATH}")

    assert navigation_response is not None
    assert navigation_response.status == 403
    assert page.locator(APL.AUDIT_LOG_TITLE).count() == 0
