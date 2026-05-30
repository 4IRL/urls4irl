from __future__ import annotations

from typing import Any, Tuple

import pytest
from flask import Flask
from flask.testing import FlaskCliRunner
from redis import Redis
from selenium.webdriver.remote.webdriver import WebDriver

from backend.metrics.events import DeviceType, EventName
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.db_utils import add_mock_urls
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.login_utils import login_user_select_utub_by_name_and_url_by_title
from tests.functional.metrics_helpers.db_utils import wait_for_metrics_row
from tests.functional.selenium_utils import (
    get_selected_url,
    wait_then_click_element,
    wait_until_hidden,
)
from tests.functional.urls_ui.selenium_utils import update_url_title

pytestmark = pytest.mark.update_urls_ui

# Headless Chrome at 1920x1080 (see `tests/functional/conftest.py::build_driver`)
# resolves to DESKTOP via `frontend/lib/device-type.ts`'s media-query check.
_EXPECTED_DEVICE_TYPE: int = DeviceType.DESKTOP.value


def test_url_title_edit_form_submit_emits_to_anonymous_metrics(
    browser: WebDriver,
    create_test_utubs: Any,
    runner: Tuple[Flask, FlaskCliRunner],
    provide_app: Flask,
    metrics_redis_client: Redis,
    pg_conn_for_metrics: Any,
):
    """
    GIVEN a logged-in user with a UTub containing a selected URL and the
        metrics pipeline activated end-to-end
    WHEN the user opens the URL title edit form, types a new title, clicks
        the submit button, and the test then dispatches a `pagehide` event
        to fire the metrics-client's real flush path
    THEN the flush worker drains the counter into Postgres and exactly one
        `AnonymousMetrics` row exists for `ui_form_submit` with
        `dimensions = {"device_type": 2, "form": "url_title_edit",
        "trigger": "button_click"}` and count == 1.
    """
    _, cli_runner = runner
    add_mock_urls(cli_runner, list([UTS.TEST_URL_STRING_CREATE]))

    user_id_for_test = 1
    login_user_select_utub_by_name_and_url_by_title(
        provide_app,
        browser,
        user_id_for_test,
        UTS.TEST_UTUB_NAME_1,
        UTS.TEST_URL_TITLE_1,
    )

    url_row = get_selected_url(browser)
    update_url_title(browser, url_row, UTS.TEST_URL_TITLE_UPDATE)

    # Submitting the title edit form fires
    # `emitFormSubmit("url_title_edit", "button_click")` in
    # `frontend/home/urls/cards/url-title.ts`.
    submit_button_selector = (
        f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_TITLE_SUBMIT_UPDATE}"
    )
    wait_then_click_element(browser, submit_button_selector)

    # Confirm the title edit completed (submit button hidden) before
    # triggering the flush — otherwise the emit may not have been buffered
    # yet and the dispatch would flush an empty buffer.
    wait_until_hidden(browser, HPL.BUTTON_URL_TITLE_SUBMIT_UPDATE)

    expected_dimensions: dict[str, Any] = {
        "device_type": _EXPECTED_DEVICE_TYPE,
        "form": "url_title_edit",
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
