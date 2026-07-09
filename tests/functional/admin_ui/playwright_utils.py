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
