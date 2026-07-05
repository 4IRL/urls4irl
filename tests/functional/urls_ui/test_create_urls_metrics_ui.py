from __future__ import annotations

from typing import Any

import pytest
from flask import Flask
from playwright.sync_api import Page
from redis import Redis

from backend.metrics.events import DeviceType, EventName
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.metrics_helpers.db_utils import wait_for_metrics_row
from tests.functional.playwright_login_utils import login_user_and_select_utub_by_name
from tests.functional.playwright_utils import wait_then_get_element
from tests.functional.urls_ui.playwright_utils import create_url

pytestmark = pytest.mark.create_urls_ui

# Headless Chromium at the desktop viewport (see
# `tests/functional/conftest.py::page_without_cookie_banner_cookie`) resolves
# to DESKTOP via `frontend/lib/device-type.ts`'s media-query check.
_EXPECTED_DEVICE_TYPE: int = DeviceType.DESKTOP.value

# A novel URL the user adds in `test_url_create_form_submit_*`. Distinct from
# `UTS.TEST_URL_STRING_CREATE` (the first mock URL) so the create flow does
# not collide with seeded data.
_NEW_URL_STRING: str = "https://metrics-ui-suite.example.com"
_NEW_URL_TITLE: str = "Metrics UI suite — create-URL fixture"


def test_url_create_form_submit_emits_to_anonymous_metrics(
    page: Page,
    create_test_utubs: Any,
    provide_app: Flask,
    metrics_redis_client: Redis,
    pg_conn_for_metrics_playwright: Any,
):
    """
    GIVEN a logged-in user with an empty UTub selected and the metrics
        pipeline activated
    WHEN the user opens the add-URL form, fills in a URL and title, clicks
        the submit button, and the test then dispatches a `pagehide`
        event to fire the metrics-client's real flush path
    THEN the flush worker drains the counter into Postgres and exactly one
        matching `AnonymousMetrics` row exists with
        `dimensions = {"device_type": 2, "form": "url_create",
        "trigger": "button_click"}` and count == 1.
    """
    user_id_for_test = 1
    login_user_and_select_utub_by_name(
        app=provide_app,
        page=page,
        user_id=user_id_for_test,
        utub_name=UTS.TEST_UTUB_NAME_1,
    )

    create_url(page=page, url_title=_NEW_URL_TITLE, url_string=_NEW_URL_STRING)

    # Confirm the URL row landed in the deck before triggering the flush —
    # otherwise the form-submit emit may not have been buffered yet and
    # the dispatch would flush an empty buffer.
    wait_then_get_element(page=page, css_selector=HPL.ROWS_URLS)

    expected_dimensions: dict[str, Any] = {
        "device_type": _EXPECTED_DEVICE_TYPE,
        "form": "url_create",
        "trigger": "button_click",
    }
    matched_row = wait_for_metrics_row(
        browser=page,
        redis_client=metrics_redis_client,
        pg_conn=pg_conn_for_metrics_playwright,
        event_name=EventName.UI_FORM_SUBMIT,
        expected_dimensions=expected_dimensions,
    )
    assert matched_row["count"] == 1
    assert matched_row["bucket_start"] is not None


def test_url_create_with_tags_form_submit_emits_to_anonymous_metrics(
    page: Page,
    create_test_utubs: Any,
    provide_app: Flask,
    metrics_redis_client: Redis,
    pg_conn_for_metrics_playwright: Any,
):
    """
    GIVEN a logged-in user with an empty UTub selected and the metrics
        pipeline activated
    WHEN the user opens the add-URL form, fills in a URL and title, stages a
        tag chip in the inline create-form combobox, clicks the submit button,
        and the test then dispatches a `pagehide` event to fire the
        metrics-client's real flush path
    THEN the flush worker drains the counter into Postgres and exactly one
        matching `AnonymousMetrics` row exists for `UI_FORM_SUBMIT` with
        `dimensions = {"device_type": 2, "form": "url_create",
        "trigger": "button_click"}` and count == 1 — i.e. the create-with-tags
        flow still emits the same UI form-submit signal as the tagless flow.

    # The URL_ADDED_TO_UTUB{tag_count_bucket} dimension itself is verified by the
    # Step 4 integration tests (cases a and b in
    # tests/integration/utuburls/test_add_url_to_utub_route.py). That DOMAIN
    # event is recorded server-side via `record_event` (not the client metrics
    # bus), so it is asserted at the integration layer rather than re-checked
    # through the browser flush path here.
    """
    user_id_for_test = 1
    login_user_and_select_utub_by_name(
        app=provide_app,
        page=page,
        user_id=user_id_for_test,
        utub_name=UTS.TEST_UTUB_NAME_1,
    )

    create_url(
        page=page,
        url_title=_NEW_URL_TITLE,
        url_string=_NEW_URL_STRING,
        tag_strings=["metricstag"],
    )

    # Confirm the URL row landed in the deck before triggering the flush.
    wait_then_get_element(page=page, css_selector=HPL.ROWS_URLS)

    expected_dimensions: dict[str, Any] = {
        "device_type": _EXPECTED_DEVICE_TYPE,
        "form": "url_create",
        "trigger": "button_click",
    }
    matched_row = wait_for_metrics_row(
        browser=page,
        redis_client=metrics_redis_client,
        pg_conn=pg_conn_for_metrics_playwright,
        event_name=EventName.UI_FORM_SUBMIT,
        expected_dimensions=expected_dimensions,
    )
    assert matched_row["count"] == 1
    assert matched_row["bucket_start"] is not None
