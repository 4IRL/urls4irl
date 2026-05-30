from __future__ import annotations

from typing import Any

import pytest
from flask import Flask
from redis import Redis
from selenium.webdriver.remote.webdriver import WebDriver

from backend.metrics.events import DeviceType, EventName
from tests.functional.login_utils import login_user_to_home_page
from tests.functional.metrics_helpers.db_utils import wait_for_metrics_row
from tests.functional.selenium_utils import wait_then_click_element

pytestmark = pytest.mark.home_ui

# Headless Chrome at 1920x1080 (see `tests/functional/conftest.py::build_driver`)
# resolves to DESKTOP via `frontend/lib/device-type.ts`'s media-query check.
_EXPECTED_DEVICE_TYPE: int = DeviceType.DESKTOP.value

# The collapsible-deck click handler in `frontend/home/collapsible-decks.ts`
# attaches to `#MemberDeckHeaderAndCaret` (not `#MemberDeckHeader`). Targeting
# the same selector the production click handler is bound to keeps the test
# resilient to selector renames in the locator module.
_MEMBER_DECK_HEADER_AND_CARET: str = "#MemberDeckHeaderAndCaret"


def test_deck_collapse_emits_to_anonymous_metrics(
    browser: WebDriver,
    create_test_users: Any,
    provide_app: Flask,
    metrics_redis_client: Redis,
    pg_conn_for_metrics: Any,
):
    """
    GIVEN a logged-in user on the home page (no UTub selected) and the
        metrics pipeline activated end-to-end
    WHEN the user clicks the Member deck header (the desktop deck-collapse
        gesture), then the test dispatches a `pagehide` event to fire the
        metrics-client's real flush path
    THEN the flush worker drains the counter into Postgres and exactly one
        `AnonymousMetrics` row exists for `ui_deck_collapse` with
        `dimensions = {"device_type": 2, "deck": "members"}` and count == 1.

    The Member deck is chosen over UTubs/Tags because it has no selection-
    state preconditions — the click handler in
    `frontend/home/collapsible-decks.ts::setupMemberHeaderForMaximizeMinimize`
    fires the emit on any header click while the Member deck is expanded
    (the default state on home page load).
    """
    user_id_for_test = 1
    login_user_to_home_page(provide_app, browser, user_id_for_test)

    # First click collapses the Member deck (default state is expanded), so
    # the emit fires UI_DECK_COLLAPSE.
    wait_then_click_element(browser, _MEMBER_DECK_HEADER_AND_CARET, time=10)

    expected_dimensions: dict[str, Any] = {
        "device_type": _EXPECTED_DEVICE_TYPE,
        "deck": "members",
    }
    matched_row = wait_for_metrics_row(
        browser=browser,
        redis_client=metrics_redis_client,
        pg_conn=pg_conn_for_metrics,
        event_name=EventName.UI_DECK_COLLAPSE,
        expected_dimensions=expected_dimensions,
    )
    assert matched_row["count"] == 1
    assert matched_row["bucket_start"] is not None
