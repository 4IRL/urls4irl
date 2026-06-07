from __future__ import annotations

from flask import Flask
from selenium.webdriver.remote.webdriver import WebDriver

from backend import db
from backend.config import ConfigTestUI
from backend.models.users import User_Role, Users
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS
from tests.functional.login_utils import (
    create_user_session_and_provide_session_id,
    login_user_with_cookie_from_session,
)

ADMIN_METRICS_DASHBOARD_PATH: str = "/admin/metrics"


def promote_user_to_admin(*, app: Flask, user_id: int) -> None:
    """Promote a Users row to the ADMIN role so the user can access
    `/admin/metrics`.

    Mirrors the integration test fixture pattern — opens an app context,
    fetches the user by id, mutates the `role` column, and commits.
    """
    with app.app_context():
        user_to_promote: Users = Users.query.get(user_id)
        user_to_promote.role = User_Role.ADMIN
        db.session.commit()


def login_admin_and_open_metrics_dashboard(
    *,
    app: Flask,
    browser: WebDriver,
    port: int,
    user_id: int,
    config: ConfigTestUI,
) -> None:
    """Promote `user_id` to ADMIN, log them in via session cookie, then
    navigate the browser directly to the admin metrics dashboard.

    Uses the same `create_user_session_and_provide_session_id` +
    `login_user_with_cookie_from_session` pair the other UI suites use
    so the Selenium session matches a logged-in browser exactly. The
    host portion of the URL is selected from the test config so the
    helper works both inside Docker (where Selenium reaches Flask via
    `http://web:<port>`) and on the host (`http://127.0.0.1:<port>`).
    """
    promote_user_to_admin(app=app, user_id=user_id)
    session_id = create_user_session_and_provide_session_id(app, user_id)
    login_user_with_cookie_from_session(browser, session_id)
    base_url = (
        UI_TEST_STRINGS.DOCKER_BASE_URL if config.DOCKER else UI_TEST_STRINGS.BASE_URL
    )
    browser.get(f"{base_url}{port}{ADMIN_METRICS_DASHBOARD_PATH}")
