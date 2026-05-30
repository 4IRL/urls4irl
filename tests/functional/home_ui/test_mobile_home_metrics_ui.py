from __future__ import annotations

from typing import Any

import pytest
from flask import Flask
from redis import Redis
from selenium.webdriver.remote.webdriver import WebDriver

from backend.metrics.events import DeviceType, EventName
from tests.functional.login_utils import login_user_to_home_page
from tests.functional.metrics_helpers.db_utils import wait_for_metrics_row
from tests.functional.selenium_utils import click_on_navbar

pytestmark = pytest.mark.mobile_ui

# Headless Chrome at 420x900 (see `tests/functional/conftest.py
# ::build_driver_mobile_portrait`) resolves to MOBILE via
# `frontend/lib/device-type.ts`'s media-query check.
_EXPECTED_DEVICE_TYPE: int = DeviceType.MOBILE.value


def test_mobile_menu_open_emits_to_anonymous_metrics(
    browser_mobile_portrait: WebDriver,
    create_test_users: Any,
    provide_app: Flask,
    metrics_redis_client: Redis,
    pg_conn_for_metrics_mobile: Any,
):
    """
    GIVEN a logged-in user on the home page in a mobile-portrait viewport
        and the metrics pipeline activated end-to-end
    WHEN the user taps the hamburger toggler to open the navbar, and the
        test then dispatches a `pagehide` event to fire the metrics-client's
        real flush path
    THEN the flush worker drains the counter into Postgres and exactly one
        `AnonymousMetrics` row exists for `ui_navbar_mobile_menu_open` with
        `dimensions = {"device_type": 1}` and count == 1.

    The mobile portrait viewport (420x900) triggers the matchMedia mobile
    breakpoint in `frontend/lib/device-type.ts`, so the backend resolves
    `device_type` to MOBILE (1). Tapping the toggler fires Bootstrap's
    `show.bs.collapse` event, which the navbar wiring in
    `frontend/home/navbar.ts::onMobileNavbarOpened` translates into
    `emit(UI_EVENTS.UI_NAVBAR_MOBILE_MENU_OPEN)`.
    """
    browser = browser_mobile_portrait
    user_id_for_test = 1
    login_user_to_home_page(provide_app, browser, user_id_for_test)

    click_on_navbar(browser)

    expected_dimensions: dict[str, Any] = {
        "device_type": _EXPECTED_DEVICE_TYPE,
    }
    matched_row = wait_for_metrics_row(
        browser=browser,
        redis_client=metrics_redis_client,
        pg_conn=pg_conn_for_metrics_mobile,
        event_name=EventName.UI_NAVBAR_MOBILE_MENU_OPEN,
        expected_dimensions=expected_dimensions,
    )
    assert matched_row["count"] == 1
    assert matched_row["bucket_start"] is not None
