from __future__ import annotations

from typing import Any

import pytest
from flask import Flask
from playwright.sync_api import Page
from redis import Redis

from backend.metrics.events import DeviceType, EventName
from tests.functional.locators import SplashPageLocators as SPL
from tests.functional.metrics_helpers.db_utils import wait_for_metrics_row
from tests.functional.playwright_assert_utils import assert_login
from tests.functional.playwright_utils import (
    login_user_ui,
    wait_then_click_element,
)

pytestmark = pytest.mark.splash_ui

# Headless Chrome at 1920x1080 (see `tests/functional/conftest.py::page_without_cookie_banner_cookie`)
# resolves to DESKTOP via `frontend/lib/device-type.ts`'s media-query check.
_EXPECTED_DEVICE_TYPE: int = DeviceType.DESKTOP.value


def test_login_submit_emits_to_anonymous_metrics(
    page: Page,
    create_test_users: Any,
    provide_app: Flask,
    metrics_redis_client: Redis,
    pg_conn_for_metrics_playwright: Any,
):
    """
    GIVEN the splash page is loaded with a registered, validated user and
        the metrics pipeline activated end-to-end (Redis writer +
        EventRegistry synced)
    WHEN the user opens the login modal, fills in valid credentials, clicks
        the submit button, and the test then dispatches a `pagehide` event
        to fire the real `flushBeacon` -> `sendBeacon` path the production
        metrics-client uses
    THEN the flush worker drains the counter into Postgres and exactly one
        `AnonymousMetrics` row exists for `ui_login_submit` with
        `dimensions = {"device_type": 2}` and count == 1.
    """
    # `login_user_ui` opens the login modal and fills in the default test
    # username + password. Submitting the form fires the metrics-client
    # `emit(UI_EVENTS.UI_LOGIN_SUBMIT)` call in
    # `frontend/splash/login-form.ts::handleLogin`.
    login_user_ui(page=page)
    wait_then_click_element(page=page, css_selector=SPL.LOGIN_BUTTON_SUBMIT)

    # Confirm the login flow completed (home page rendered) before
    # triggering the flush — otherwise the emit may not have been buffered
    # yet and the dispatch would flush an empty buffer.
    assert_login(page=page)

    expected_dimensions: dict[str, Any] = {
        "device_type": _EXPECTED_DEVICE_TYPE,
    }
    matched_row = wait_for_metrics_row(
        browser=page,
        redis_client=metrics_redis_client,
        pg_conn=pg_conn_for_metrics_playwright,
        event_name=EventName.UI_LOGIN_SUBMIT,
        expected_dimensions=expected_dimensions,
    )
    assert matched_row["count"] == 1
    assert matched_row["bucket_start"] is not None
