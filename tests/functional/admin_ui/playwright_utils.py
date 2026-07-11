from __future__ import annotations

from flask import Flask
from playwright.sync_api import BrowserContext, Page

from backend.config import ConfigTestUI
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS
from tests.functional.metrics_ui.playwright_utils import promote_user_to_admin
from tests.functional.playwright_utils import (
    create_user_session_and_provide_session_id,
    login_user_with_cookie_from_session,
)

ADMIN_PORTAL_PATH: str = "/admin"
ADMIN_HEALTH_PATH: str = "/admin/health"
ADMIN_DB_BROWSER_PATH: str = "/admin/db"
ADMIN_DB_BROWSER_USERS_PATH: str = "/admin/db/Users"
ADMIN_USERS_PATH: str = "/admin/users"
ADMIN_USER_DETAIL_PATH_PREFIX: str = "/admin/users/"
ADMIN_DB_ROW_PATH_PREFIX: str = "/admin/db/"
ADMIN_AUDIT_LOG_PATH: str = "/admin/audit-log"


def login_admin_and_open_admin_portal(
    *,
    app: Flask,
    context: BrowserContext,
    page: Page,
    port: int,
    user_id: int,
    config: ConfigTestUI,
) -> None:
    """Promote `user_id` to ADMIN, log them in via session cookie, then
    navigate the page directly to the admin portal landing page.

    Uses the same `create_user_session_and_provide_session_id` +
    `login_user_with_cookie_from_session` pair the other UI suites use
    so the Playwright context matches a logged-in browser exactly. The
    host portion of the URL is selected from the test config so the
    helper works both inside Docker (where the browser-server reaches Flask
    via `http://web:<port>`) and on the host (`http://127.0.0.1:<port>`).
    """
    promote_user_to_admin(app=app, user_id=user_id)
    session_id = create_user_session_and_provide_session_id(app=app, user_id=user_id)
    base_url = (
        UI_TEST_STRINGS.DOCKER_BASE_URL if config.DOCKER else UI_TEST_STRINGS.BASE_URL
    )
    login_user_with_cookie_from_session(
        context=context, session_id=session_id, base_url=f"{base_url}{port}"
    )
    page.goto(f"{base_url}{port}{ADMIN_PORTAL_PATH}")


def login_admin_and_open_db_browser(
    *,
    app: Flask,
    context: BrowserContext,
    page: Page,
    port: int,
    user_id: int,
    config: ConfigTestUI,
) -> None:
    """Promote `user_id` to ADMIN, log them in via session cookie, then
    navigate the page directly to the native DB-browser overview page.

    Mirrors ``login_admin_and_open_admin_portal`` exactly but targets
    ``ADMIN_DB_BROWSER_PATH`` so callers do not need to construct the URL.
    """
    promote_user_to_admin(app=app, user_id=user_id)
    session_id = create_user_session_and_provide_session_id(app=app, user_id=user_id)
    base_url = (
        UI_TEST_STRINGS.DOCKER_BASE_URL if config.DOCKER else UI_TEST_STRINGS.BASE_URL
    )
    login_user_with_cookie_from_session(
        context=context, session_id=session_id, base_url=f"{base_url}{port}"
    )
    page.goto(f"{base_url}{port}{ADMIN_DB_BROWSER_PATH}")


def login_admin_and_open_db_browser_table(
    *,
    app: Flask,
    context: BrowserContext,
    page: Page,
    port: int,
    user_id: int,
    config: ConfigTestUI,
    table_name: str,
) -> None:
    """Promote `user_id` to ADMIN, log them in via session cookie, then
    navigate the page directly to the native DB-browser grid for
    ``table_name``.

    Mirrors ``login_admin_and_open_admin_portal`` exactly but targets the
    per-table grid path so callers do not need to construct the URL.
    """
    promote_user_to_admin(app=app, user_id=user_id)
    session_id = create_user_session_and_provide_session_id(app=app, user_id=user_id)
    base_url = (
        UI_TEST_STRINGS.DOCKER_BASE_URL if config.DOCKER else UI_TEST_STRINGS.BASE_URL
    )
    login_user_with_cookie_from_session(
        context=context, session_id=session_id, base_url=f"{base_url}{port}"
    )
    page.goto(f"{base_url}{port}{ADMIN_DB_BROWSER_PATH}/{table_name}")


def login_admin_and_open_admin_users(
    *,
    app: Flask,
    context: BrowserContext,
    page: Page,
    port: int,
    user_id: int,
    config: ConfigTestUI,
) -> None:
    """Promote `user_id` to ADMIN, log them in via session cookie, then
    navigate the page directly to the admin users search page.

    Mirrors ``login_admin_and_open_admin_portal`` exactly but targets
    ``ADMIN_USERS_PATH`` so callers do not need to construct the URL.
    """
    promote_user_to_admin(app=app, user_id=user_id)
    session_id = create_user_session_and_provide_session_id(app=app, user_id=user_id)
    base_url = (
        UI_TEST_STRINGS.DOCKER_BASE_URL if config.DOCKER else UI_TEST_STRINGS.BASE_URL
    )
    login_user_with_cookie_from_session(
        context=context, session_id=session_id, base_url=f"{base_url}{port}"
    )
    page.goto(f"{base_url}{port}{ADMIN_USERS_PATH}")


def login_admin_and_open_audit_log(
    *,
    app: Flask,
    context: BrowserContext,
    page: Page,
    port: int,
    user_id: int,
    config: ConfigTestUI,
) -> None:
    """Promote `user_id` to ADMIN, log them in via session cookie, then
    navigate the page directly to the audit-log viewer page.

    Mirrors ``login_admin_and_open_admin_portal`` exactly but targets
    ``ADMIN_AUDIT_LOG_PATH`` so callers do not need to construct the URL.
    """
    promote_user_to_admin(app=app, user_id=user_id)
    session_id = create_user_session_and_provide_session_id(app=app, user_id=user_id)
    base_url = (
        UI_TEST_STRINGS.DOCKER_BASE_URL if config.DOCKER else UI_TEST_STRINGS.BASE_URL
    )
    login_user_with_cookie_from_session(
        context=context, session_id=session_id, base_url=f"{base_url}{port}"
    )
    page.goto(f"{base_url}{port}{ADMIN_AUDIT_LOG_PATH}")


def login_admin_and_open_admin_health(
    *,
    app: Flask,
    context: BrowserContext,
    page: Page,
    port: int,
    user_id: int,
    config: ConfigTestUI,
) -> None:
    """Promote `user_id` to ADMIN, log them in via session cookie, then
    navigate the page directly to the admin health dashboard page.

    Mirrors ``login_admin_and_open_admin_portal`` exactly but targets
    ``ADMIN_HEALTH_PATH`` so callers do not need to construct the URL.
    """
    promote_user_to_admin(app=app, user_id=user_id)
    session_id = create_user_session_and_provide_session_id(app=app, user_id=user_id)
    base_url = (
        UI_TEST_STRINGS.DOCKER_BASE_URL if config.DOCKER else UI_TEST_STRINGS.BASE_URL
    )
    login_user_with_cookie_from_session(
        context=context, session_id=session_id, base_url=f"{base_url}{port}"
    )
    page.goto(f"{base_url}{port}{ADMIN_HEALTH_PATH}")


def login_admin_and_open_user_detail(
    *,
    app: Flask,
    context: BrowserContext,
    page: Page,
    port: int,
    user_id: int,
    config: ConfigTestUI,
    target_user_id: int,
) -> None:
    """Promote `user_id` to ADMIN, log them in via session cookie, then
    navigate the page directly to a specific user's detail page.

    Mirrors ``login_admin_and_open_admin_portal`` exactly but targets
    ``ADMIN_USER_DETAIL_PATH_PREFIX/<target_user_id>`` so callers can
    open any seeded user's detail page without constructing the URL.
    """
    promote_user_to_admin(app=app, user_id=user_id)
    session_id = create_user_session_and_provide_session_id(app=app, user_id=user_id)
    base_url = (
        UI_TEST_STRINGS.DOCKER_BASE_URL if config.DOCKER else UI_TEST_STRINGS.BASE_URL
    )
    login_user_with_cookie_from_session(
        context=context, session_id=session_id, base_url=f"{base_url}{port}"
    )
    page.goto(f"{base_url}{port}{ADMIN_USER_DETAIL_PATH_PREFIX}{target_user_id}")


def login_admin_and_open_db_row(
    *,
    app: Flask,
    context: BrowserContext,
    page: Page,
    port: int,
    user_id: int,
    config: ConfigTestUI,
    table_name: str,
    row_pk: int | str,
) -> None:
    """Promote `user_id` to ADMIN, log them in via session cookie, then
    navigate the page directly to a DB-browser row-detail page.

    Mirrors ``login_admin_and_open_admin_portal`` exactly but targets
    ``ADMIN_DB_ROW_PATH_PREFIX/<table_name>/<row_pk>`` so callers can
    open any table's row-detail page without constructing the URL.
    """
    promote_user_to_admin(app=app, user_id=user_id)
    session_id = create_user_session_and_provide_session_id(app=app, user_id=user_id)
    base_url = (
        UI_TEST_STRINGS.DOCKER_BASE_URL if config.DOCKER else UI_TEST_STRINGS.BASE_URL
    )
    login_user_with_cookie_from_session(
        context=context, session_id=session_id, base_url=f"{base_url}{port}"
    )
    page.goto(f"{base_url}{port}{ADMIN_DB_ROW_PATH_PREFIX}{table_name}/{row_pk}")
