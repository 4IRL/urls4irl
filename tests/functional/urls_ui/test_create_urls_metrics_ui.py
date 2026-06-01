from __future__ import annotations

from typing import Any

import pytest
from flask import Flask
from redis import Redis
from selenium.webdriver.remote.webdriver import WebDriver

from backend.metrics.events import DeviceType, EventName
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.login_utils import login_user_and_select_utub_by_name
from tests.functional.metrics_helpers.db_utils import wait_for_metrics_row
from tests.functional.selenium_utils import wait_then_get_element
from tests.functional.urls_ui.selenium_utils import create_url

pytestmark = pytest.mark.create_urls_ui

# Headless Chrome at 1920x1080 (see `tests/functional/conftest.py::build_driver`)
# resolves to DESKTOP via `frontend/lib/device-type.ts`'s media-query check.
_EXPECTED_DEVICE_TYPE: int = DeviceType.DESKTOP.value

# A novel URL the user adds in `test_url_create_form_submit_*`. Distinct from
# `UTS.TEST_URL_STRING_CREATE` (the first mock URL) so the create flow does
# not collide with seeded data.
_NEW_URL_STRING: str = "https://metrics-ui-suite.example.com"
_NEW_URL_TITLE: str = "Metrics UI suite — create-URL fixture"


def test_url_create_form_submit_emits_to_anonymous_metrics(
    browser: WebDriver,
    create_test_utubs: Any,
    provide_app: Flask,
    metrics_redis_client: Redis,
    pg_conn_for_metrics: Any,
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
        provide_app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1
    )

    create_url(browser, _NEW_URL_TITLE, _NEW_URL_STRING)

    # Confirm the URL row landed in the deck before triggering the flush —
    # otherwise the form-submit emit may not have been buffered yet and
    # the dispatch would flush an empty buffer.
    new_url_row = wait_then_get_element(browser, HPL.ROWS_URLS, time=10)
    assert new_url_row is not None

    expected_dimensions: dict[str, Any] = {
        "device_type": _EXPECTED_DEVICE_TYPE,
        "form": "url_create",
        "trigger": "button_click",
    }
    matched_row = wait_for_metrics_row(
        browser=browser,
        redis_client=metrics_redis_client,
        pg_conn=pg_conn_for_metrics,
        event_name=EventName.UI_FORM_SUBMIT,
        expected_dimensions=expected_dimensions,
    )
    assert matched_row["count"] == 1
    assert matched_row["bucket_start"] is not None
