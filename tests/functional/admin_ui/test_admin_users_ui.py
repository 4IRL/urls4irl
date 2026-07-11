from __future__ import annotations

import re

import pytest
from flask import Flask
from playwright.sync_api import Page, expect

from backend.cli.mock_constants import USERNAME_BASE
from backend.config import ConfigTestUI
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS
from tests.functional.admin_ui.playwright_utils import (
    ADMIN_USERS_PATH,
    login_admin_and_open_admin_users,
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

# Derived from the mock-constants USERNAME_BASE so the constant stays in sync
# with the seeded data without duplicating the literal.
_SEARCH_TARGET_USERNAME: str = USERNAME_BASE + "2"
# User 2 is the second user created by `addmock users` and receives id=2 in
# a freshly cleared test database.
_SEARCH_TARGET_USER_ID: int = 2

_NO_MATCH_QUERY: str = "zzqxnomatch"
_USER_LINK_SELECTOR: str = "a.admin-user-link"


def test_admin_users_search_and_click_detail(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
) -> None:
    """
    GIVEN a logged-in admin user with five seeded test users in the database
    WHEN the admin opens /admin/users, types the second user's username into
         the search input, and clicks the resulting row link
    THEN the search result table shows exactly one row containing that
         username; after the click the URL becomes /admin/users/2 and the
         user detail page renders that username in #AdminUserDetailUsername.
    """
    login_admin_and_open_admin_users(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
    )

    # Wait for the user-search controller to populate the initial results.
    wait_then_get_element(page=page, css_selector=APL.USER_SEARCH_TABLE)

    # Type the search term into the input and wait for the debounced swap.
    page.fill(APL.USER_SEARCH_INPUT, _SEARCH_TARGET_USERNAME)

    search_row_locator = page.locator(APL.USER_SEARCH_ROW)
    expect(search_row_locator).to_have_count(1)
    expect(search_row_locator).to_contain_text(_SEARCH_TARGET_USERNAME)

    # Click the user link to navigate to the detail page.
    page.locator(_USER_LINK_SELECTOR).first.click()

    expect(page).to_have_url(re.compile(rf"/admin/users/{_SEARCH_TARGET_USER_ID}$"))

    detail_username_locator = wait_then_get_element(
        page=page, css_selector=APL.USER_DETAIL_USERNAME
    )
    expect(detail_username_locator).to_have_text(_SEARCH_TARGET_USERNAME)


def test_admin_users_search_no_results_shows_empty_state(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
) -> None:
    """
    GIVEN a logged-in admin user with five seeded test users in the database
    WHEN the admin opens /admin/users and types a query that matches no user
    THEN the #AdminUserSearchEmpty element is visible and contains the
         USERS_NO_RESULTS text from ADMIN_PORTAL_STRINGS.
    """
    login_admin_and_open_admin_users(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
    )

    # Wait for the user-search controller initial load before typing.
    wait_then_get_element(page=page, css_selector=APL.USER_SEARCH_TABLE)

    page.fill(APL.USER_SEARCH_INPUT, _NO_MATCH_QUERY)

    empty_state_locator = wait_then_get_element(
        page=page, css_selector=APL.USER_SEARCH_EMPTY
    )
    expect(empty_state_locator).to_be_visible()
    expect(empty_state_locator).to_contain_text(UI_TEST_STRINGS.ADMIN_USERS_NO_RESULTS)


def test_admin_users_returns_403_for_non_admin(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
) -> None:
    """
    GIVEN a logged-in non-admin user (no role promotion)
    WHEN the user navigates to /admin/users
    THEN the HTTP response status is 403 Forbidden and the users title
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

    navigation_response = page.goto(f"{full_base_url}{ADMIN_USERS_PATH}")

    assert navigation_response is not None
    assert navigation_response.status == 403
    assert page.locator(APL.USERS_TITLE).count() == 0
