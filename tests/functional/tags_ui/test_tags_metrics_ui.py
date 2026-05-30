from __future__ import annotations

from typing import Any

import pytest
from flask import Flask
from redis import Redis
from selenium.webdriver.remote.webdriver import WebDriver

from backend.metrics.events import DeviceType, EventName
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.db_utils import (
    get_url_in_utub,
    get_utub_this_user_created,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.login_utils import login_user_select_utub_by_id_and_url_by_id
from tests.functional.metrics_helpers.db_utils import wait_for_metrics_row
from tests.functional.selenium_utils import (
    wait_then_click_element,
    wait_until_hidden,
)
from tests.functional.tags_ui.selenium_utils import add_tag_to_url

pytestmark = pytest.mark.tags_ui

# Headless Chrome at 1920x1080 (see `tests/functional/conftest.py::build_driver`)
# resolves to DESKTOP via `frontend/lib/device-type.ts`'s media-query check.
_EXPECTED_DEVICE_TYPE: int = DeviceType.DESKTOP.value


def test_tag_apply_emits_to_anonymous_metrics(
    browser: WebDriver,
    create_test_urls: Any,
    provide_app: Flask,
    metrics_redis_client: Redis,
    pg_conn_for_metrics: Any,
):
    """
    GIVEN a logged-in user with a UTub containing a selected URL and the
        metrics pipeline activated end-to-end
    WHEN the user opens the URL tag create input, types a fresh tag value,
        clicks the submit button to apply the tag, and the test then
        dispatches a `pagehide` event to fire the metrics-client's real
        flush path
    THEN the flush worker drains the counter into Postgres and exactly one
        `AnonymousMetrics` row exists for `ui_tag_apply` with
        `dimensions = {"device_type": 2}` and count == 1.

    `UI_TAG_APPLY` fires in the success handler of `createURLTag`
    (frontend/home/urls/tags/create.ts) — the same code path runs whether
    the tag string is new to the UTub or an existing tag being re-applied,
    so creating a fresh tag (no setup overhead) is the cleanest gesture.
    """
    tag_text = UTS.TEST_TAG_NAME_1
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(provide_app, user_id_for_test)
    url_in_utub = get_url_in_utub(provide_app, utub_user_created.id)

    login_user_select_utub_by_id_and_url_by_id(
        provide_app,
        browser,
        user_id_for_test,
        utub_user_created.id,
        url_in_utub.id,
    )

    add_tag_to_url(browser, url_in_utub.id, tag_text)

    # Submit the tag create form — emits `UI_TAG_APPLY` in the success
    # handler after the POST completes.
    submit_button_selector = f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_TAG_SUBMIT_CREATE}"
    wait_then_click_element(browser, submit_button_selector, time=3)

    # Confirm the apply completed (submit button hidden) before triggering
    # the flush — otherwise the emit may not have been buffered yet and
    # the dispatch would flush an empty buffer.
    wait_until_hidden(browser, submit_button_selector, timeout=3)

    expected_dimensions: dict[str, Any] = {
        "device_type": _EXPECTED_DEVICE_TYPE,
    }
    matched_row = wait_for_metrics_row(
        browser=browser,
        redis_client=metrics_redis_client,
        pg_conn=pg_conn_for_metrics,
        event_name=EventName.UI_TAG_APPLY,
        expected_dimensions=expected_dimensions,
    )
    assert matched_row["count"] == 1
    assert matched_row["bucket_start"] is not None
