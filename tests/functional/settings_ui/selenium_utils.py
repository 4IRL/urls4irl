from __future__ import annotations

from flask import Flask
from selenium.webdriver.remote.webdriver import WebDriver

from backend.config import ConfigTestUI
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS
from tests.functional.login_utils import (
    create_user_session_and_provide_session_id,
    login_user_with_cookie_from_session,
)

SETTINGS_PATH: str = "/settings"
HOME_PATH: str = "/home"


def _base_url_for(*, config: ConfigTestUI) -> str:
    """Select the host portion of the URL from the test config so the
    helper works both inside Docker (where Selenium reaches Flask via
    `http://web:<port>`) and on the host (`http://127.0.0.1:<port>`).
    """
    return (
        UI_TEST_STRINGS.DOCKER_BASE_URL if config.DOCKER else UI_TEST_STRINGS.BASE_URL
    )


def login_user_and_open_settings(
    *,
    app: Flask,
    browser: WebDriver,
    port: int,
    user_id: int,
    config: ConfigTestUI,
) -> None:
    """Log `user_id` in via session cookie, then navigate the browser
    directly to the user settings page.

    Mirrors `metrics_ui.selenium_utils.login_admin_and_open_metrics_dashboard`
    minus the `promote_user_to_admin` step — every authenticated, email-
    validated user can reach `/settings`. `flask addmock users` seeds users
    with `email_validated=True`, so the page returns 200 without any post-
    seed patch.
    """
    session_id = create_user_session_and_provide_session_id(app, user_id)
    login_user_with_cookie_from_session(browser, session_id)
    base_url = _base_url_for(config=config)
    browser.get(f"{base_url}{port}{SETTINGS_PATH}")


def login_user_and_open_home(
    *,
    app: Flask,
    browser: WebDriver,
    port: int,
    user_id: int,
    config: ConfigTestUI,
) -> None:
    """Log `user_id` in via session cookie, then navigate the browser
    directly to the authenticated home page.

    Used by the cross-page nav-link test, which verifies the Settings
    nav link (added in Step 4) is reachable from the home page.
    """
    session_id = create_user_session_and_provide_session_id(app, user_id)
    login_user_with_cookie_from_session(browser, session_id)
    base_url = _base_url_for(config=config)
    browser.get(f"{base_url}{port}{HOME_PATH}")
