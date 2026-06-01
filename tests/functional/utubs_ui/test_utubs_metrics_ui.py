from __future__ import annotations

from typing import Any

import pytest
from flask import Flask
from redis import Redis
from selenium.webdriver.remote.webdriver import WebDriver

from backend.metrics.events import DeviceType, EventName
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.db_utils import get_utub_this_user_created
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.login_utils import login_user_to_home_page
from tests.functional.metrics_helpers.db_utils import wait_for_metrics_row
from tests.functional.selenium_utils import (
    wait_then_click_element,
    wait_then_get_element,
)
from tests.functional.utubs_ui.selenium_utils import create_utub

pytestmark = pytest.mark.utubs_ui

# UI_TEST_STRINGS does not ship a dedicated UTub description constant; the
# create-UTub test only needs a non-empty placeholder for the description
# input. Keeping it local rather than mock_constants because no other test
# in this module references it.
_TEST_UTUB_DESCRIPTION: str = "UTub created from the metrics-ui suite"

# Headless Chrome at 1920x1080 (see `tests/functional/conftest.py::build_driver`)
# resolves to DESKTOP via `frontend/lib/device-type.ts`'s media-query check.
_EXPECTED_DEVICE_TYPE: int = DeviceType.DESKTOP.value


def test_utub_select_emits_to_anonymous_metrics(
    browser: WebDriver,
    create_test_utubs: Any,
    provide_app: Flask,
    metrics_redis_client: Redis,
    pg_conn_for_metrics: Any,
):
    """
    GIVEN a logged-in user with at least one UTub and the metrics pipeline
        activated end-to-end (Redis writer + EventRegistry synced)
    WHEN the user clicks a UTub selector tile in the sidebar, then the
        test dispatches a `pagehide` event to fire the real
        `flushBeacon` -> `sendBeacon` path the production metrics-client
        uses
    THEN the flush worker drains the counter from Redis into Postgres and
        exactly one `AnonymousMetrics` row exists with
        `dimensions = {"device_type": 2, "search_active": "false"}` and
        count == 1.
    """
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(provide_app, user_id_for_test)

    login_user_to_home_page(provide_app, browser, user_id_for_test)
    utub_selector_css = f"{HPL.SELECTORS_UTUB}[utubid='{utub_user_created.id}']"
    wait_then_click_element(browser, utub_selector_css, time=10)

    # The click handler invokes `selectUTub`, which calls `recordUIEvent`
    # to buffer the `ui_utub_select` event in the metrics-client. The
    # `wait_for_metrics_row` helper triggers the real flush path via a
    # synthesized `pagehide` event and asserts the row materialized.
    expected_dimensions: dict[str, Any] = {
        "device_type": _EXPECTED_DEVICE_TYPE,
        "search_active": "false",
    }
    matched_row = wait_for_metrics_row(
        browser=browser,
        redis_client=metrics_redis_client,
        pg_conn=pg_conn_for_metrics,
        event_name=EventName.UI_UTUB_SELECT,
        expected_dimensions=expected_dimensions,
    )
    assert matched_row["count"] == 1
    assert matched_row["bucket_start"] is not None


def test_utub_create_form_submit_emits_to_anonymous_metrics(
    browser: WebDriver,
    create_test_users: Any,
    provide_app: Flask,
    metrics_redis_client: Redis,
    pg_conn_for_metrics: Any,
):
    """
    GIVEN a logged-in user with no UTubs and the metrics pipeline activated
    WHEN the user opens the create-UTub form, fills in a name + description,
        clicks the submit button, and the test then dispatches a
        `pagehide` event to fire the metrics-client's real flush path
    THEN the flush drains the counter into Postgres and exactly one
        matching `AnonymousMetrics` row exists with
        `dimensions = {"device_type": 2, "form": "utub_create",
        "trigger": "button_click"}` and count == 1.
    """
    user_id_for_test = 1
    login_user_to_home_page(provide_app, browser, user_id_for_test)

    create_utub(browser, UTS.TEST_UTUB_NAME_1, _TEST_UTUB_DESCRIPTION)
    wait_then_click_element(browser, HPL.BUTTON_UTUB_SUBMIT_CREATE)

    # Confirm the UTub creation completed (sidebar tile rendered) before
    # triggering the flush — otherwise the form-submit emit may not have
    # been buffered yet and the dispatch would flush an empty buffer.
    created_utub_tile = wait_then_get_element(
        browser,
        f"{HPL.SELECTORS_UTUB} {HPL.SELECTORS_UTUB_NAME}",
        time=10,
    )
    assert created_utub_tile is not None

    expected_dimensions: dict[str, Any] = {
        "device_type": _EXPECTED_DEVICE_TYPE,
        "form": "utub_create",
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
