from __future__ import annotations

from typing import Any

import pytest
from flask import Flask
from playwright.sync_api import Page
from redis import Redis

from backend.metrics.events import DeviceType, EventName
from tests.functional.metrics_helpers.db_utils import (
    query_anonymous_metrics_rows,
    wait_for_metrics_row,
)
from tests.functional.playwright_utils import (
    click_on_navbar,
    close_navbar,
    login_user_to_home_page,
)

pytestmark = pytest.mark.mobile_ui

# Headless Chrome at 420x900 (see `tests/functional/conftest.py
# ::build_page_browser`) resolves to MOBILE via
# `frontend/lib/device-type.ts`'s media-query check.
_EXPECTED_DEVICE_TYPE: int = DeviceType.MOBILE.value


def test_mobile_menu_open_emits_to_anonymous_metrics(
    page_mobile_portrait: Page,
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
        `AnonymousMetrics` row exists for `ui_navbar_dropdown_open` with
        `dimensions = {"device_type": 1}` and count == 1.

    The mobile portrait viewport (420x900) triggers the matchMedia mobile
    breakpoint in `frontend/lib/device-type.ts`, so the backend resolves
    `device_type` to MOBILE (1). Tapping the toggler fires Bootstrap's
    `show.bs.collapse` event, which the navbar wiring in
    `frontend/home/navbar.ts::onMobileNavbarOpened` translates into
    `emit(UI_EVENTS.UI_NAVBAR_DROPDOWN_OPEN)`.
    """
    page = page_mobile_portrait
    user_id_for_test = 1
    login_user_to_home_page(app=provide_app, page=page, user_id=user_id_for_test)

    click_on_navbar(page=page)

    expected_dimensions: dict[str, Any] = {
        "device_type": _EXPECTED_DEVICE_TYPE,
    }
    matched_row = wait_for_metrics_row(
        browser=page,
        redis_client=metrics_redis_client,
        pg_conn=pg_conn_for_metrics_mobile,
        event_name=EventName.UI_NAVBAR_DROPDOWN_OPEN,
        expected_dimensions=expected_dimensions,
    )
    assert matched_row["count"] == 1
    assert matched_row["bucket_start"] is not None


def test_mobile_menu_close_emits_to_anonymous_metrics(
    page_mobile_portrait: Page,
    create_test_users: Any,
    provide_app: Flask,
    metrics_redis_client: Redis,
    pg_conn_for_metrics_mobile: Any,
):
    """
    GIVEN a logged-in user on the home page in a mobile-portrait viewport
        and the metrics pipeline activated end-to-end
    WHEN the user taps the hamburger toggler to open the navbar, then taps
        it again to collapse it, and the test dispatches a `pagehide` event
        to fire the metrics-client's real flush path
    THEN the flush worker drains the counter into Postgres and exactly one
        `AnonymousMetrics` row exists for `ui_navbar_dropdown_close` with
        `dimensions = {"device_type": 1}` and count == 1.

    The mobile portrait viewport (420x900) triggers the matchMedia mobile
    breakpoint in `frontend/lib/device-type.ts`, so the backend resolves
    `device_type` to MOBILE (1). Collapsing the navbar via the toggler fires
    Bootstrap's `hide.bs.collapse` event, which the navbar wiring in
    `frontend/home/navbar.ts::onMobileNavbarClosed` translates into
    `emit(UI_EVENTS.UI_NAVBAR_DROPDOWN_CLOSE)`.
    """
    page = page_mobile_portrait
    user_id_for_test = 1
    login_user_to_home_page(app=provide_app, page=page, user_id=user_id_for_test)

    rows_before = query_anonymous_metrics_rows(
        pg_conn_for_metrics_mobile,
        event_name=EventName.UI_NAVBAR_DROPDOWN_CLOSE.value,
    )
    assert rows_before == []

    click_on_navbar(page=page)
    close_navbar(page=page)

    expected_dimensions: dict[str, Any] = {
        "device_type": _EXPECTED_DEVICE_TYPE,
    }
    matched_row = wait_for_metrics_row(
        browser=page,
        redis_client=metrics_redis_client,
        pg_conn=pg_conn_for_metrics_mobile,
        event_name=EventName.UI_NAVBAR_DROPDOWN_CLOSE,
        expected_dimensions=expected_dimensions,
    )
    assert matched_row["count"] == 1
    assert matched_row["bucket_start"] is not None
