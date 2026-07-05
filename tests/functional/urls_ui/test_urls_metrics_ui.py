from __future__ import annotations

import random
from typing import Any

import pytest
from flask import Flask
from playwright.sync_api import Page
from redis import Redis

from backend.cli.mock_constants import MOCK_TEST_URL_STRINGS
from backend.metrics.events import DeviceType, EventName
from tests.functional.db_utils import (
    get_utub_this_user_created,
    get_utub_url_id_by_url_string,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.metrics_helpers.db_utils import wait_for_metrics_row
from tests.functional.playwright_login_utils import (
    login_user_select_utub_by_id_and_url_by_id,
)
from tests.functional.playwright_utils import get_selected_url

pytestmark = pytest.mark.urls_ui

# Headless Chromium at the desktop viewport (see
# `tests/functional/conftest.py::page_without_cookie_banner_cookie`) resolves
# to DESKTOP via `frontend/lib/device-type.ts`'s media-query check.
_EXPECTED_DEVICE_TYPE: int = DeviceType.DESKTOP.value

# Mock URLs used by `create_test_access_urls` do not carry tag rows, so every
# URL row in the seeded UTub has zero active tag filters applied.
_NO_ACTIVE_TAGS: int = 0


def test_url_access_emits_to_anonymous_metrics(
    page: Page,
    create_test_access_urls: Any,
    provide_app: Flask,
    metrics_redis_client: Redis,
    pg_conn_for_metrics: Any,
):
    """
    GIVEN a logged-in user with a selected UTub containing accessible URLs and
        the metrics pipeline activated
    WHEN the user clicks the URL anchor text on a selected URL row (the
        `url_text` trigger path in `frontend/home/urls/cards/url-string.ts`)
        and the test then dispatches a `pagehide` event to fire the
        metrics-client's real flush path
    THEN the flush worker drains the counter into Postgres and exactly one
        matching `AnonymousMetrics` row exists with
        `dimensions = {"device_type": 2, "trigger": "url_text",
        "search_active": "false", "active_tag_count": 0}` and count == 1.
    """
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(provide_app, user_id_for_test)
    url_to_access = random.sample(MOCK_TEST_URL_STRINGS, 1)[0]
    utub_url_id = get_utub_url_id_by_url_string(
        provide_app, utub_user_created.id, url_to_access
    )

    login_user_select_utub_by_id_and_url_by_id(
        app=provide_app,
        page=page,
        user_id=user_id_for_test,
        utub_id=utub_user_created.id,
        utub_url_id=utub_url_id,
    )

    selected_url_row = get_selected_url(page=page)
    url_anchor = selected_url_row.locator(HPL.URL_STRING_READ)

    # `window.open(..., "_blank")` from `accessLink(...)` spawns a background
    # tab. Absorb the popup event; the original `page` object keeps pointing
    # at the tab that owns the metrics-client buffer, so the dispatched
    # `pagehide` inside `wait_for_metrics_row` fires on the right page (no
    # Selenium-style window-handle pivot needed).
    with page.context.expect_page():
        url_anchor.click()

    expected_dimensions: dict[str, Any] = {
        "device_type": _EXPECTED_DEVICE_TYPE,
        "trigger": "url_text",
        "search_active": "false",
        "active_tag_count": _NO_ACTIVE_TAGS,
    }
    matched_row = wait_for_metrics_row(
        browser=page,
        redis_client=metrics_redis_client,
        pg_conn=pg_conn_for_metrics,
        event_name=EventName.UI_URL_ACCESS,
        expected_dimensions=expected_dimensions,
    )
    assert matched_row["count"] == 1
    assert matched_row["bucket_start"] is not None
