from __future__ import annotations

from typing import Tuple

import pytest
from flask import Flask
from flask.testing import FlaskCliRunner
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

from backend.config import ConfigTestUI
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS
from tests.functional.locators import MetricsDashboardLocators as MDL
from tests.functional.metrics_ui.selenium_utils import (
    login_admin_and_open_metrics_dashboard,
)
from tests.functional.selenium_utils import (
    wait_for_element_presence,
    wait_then_click_element,
    wait_then_get_element,
)

pytestmark = pytest.mark.metrics_ui

DEFAULT_ADMIN_USER_ID: int = 1
SEEDED_TABLE_ROW_SELECTOR: str = f"{MDL.TOP_TABLE_API} tbody tr.MetricsTopTableRow"
WINDOW_BUTTON_TIMEOUT_SECONDS: int = 5


def _seed_metrics_via_cli(runner: Tuple[Flask, FlaskCliRunner]) -> None:
    """Invoke `flask metrics seed-uniform-test-data` through the test
    runner so the seeded rows live inside the test worker's DB.

    Using `subprocess.run(['flask', ...])` would escape the worker DB
    isolation, and `app.test_cli_runner().invoke(...)` would build a
    runner outside the fixture transaction scope. The `runner` fixture
    already wires both.
    """
    _, cli_runner = runner
    result = cli_runner.invoke(args=["metrics", "seed-uniform-test-data"])
    assert (
        result.exit_code == 0
    ), f"Metrics seed CLI failed: exit={result.exit_code} output={result.output}"


def test_admin_dashboard_renders_with_seeded_metrics(
    browser: WebDriver,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
    runner: Tuple[Flask, FlaskCliRunner],
):
    """
    GIVEN a logged-in admin user and seeded AnonymousMetrics rows across
        all three event categories (API, UI, DOMAIN)
    WHEN the admin opens `/admin/metrics`
    THEN the dashboard title renders with the localized string and the
        API top-events table has at least one populated row.
    """
    _seed_metrics_via_cli(runner)

    login_admin_and_open_metrics_dashboard(
        app=provide_app,
        browser=browser,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
    )

    title_element = wait_then_get_element(browser, MDL.DASHBOARD_TITLE, time=5)
    assert title_element is not None
    assert title_element.is_displayed()
    assert title_element.text == UI_TEST_STRINGS.METRICS_DASHBOARD_TITLE

    first_table_row = wait_for_element_presence(
        browser, SEEDED_TABLE_ROW_SELECTOR, timeout=10
    )
    assert first_table_row is not None


def test_window_switch_to_week_re_renders_chart(
    browser: WebDriver,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
    runner: Tuple[Flask, FlaskCliRunner],
):
    """
    GIVEN a logged-in admin user on the metrics dashboard with seeded
        data, with the default "Day" window button pressed
    WHEN the admin clicks the "Week" window button
    THEN `aria-pressed="true"` flips onto `#MetricsWindowWeek`,
        `aria-pressed="false"` flips back onto `#MetricsWindowDay`, and
        the API chart container re-renders (its inner title node is
        present in the DOM after the re-fetch).
    """
    _seed_metrics_via_cli(runner)

    login_admin_and_open_metrics_dashboard(
        app=provide_app,
        browser=browser,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
    )

    # Wait for the dashboard's initial render so the click below does
    # not race the initial fetch attaching its handlers.
    wait_for_element_presence(browser, SEEDED_TABLE_ROW_SELECTOR, timeout=10)

    wait_then_click_element(
        browser, MDL.WINDOW_WEEK_BUTTON, time=WINDOW_BUTTON_TIMEOUT_SECONDS
    )

    week_button = wait_then_get_element(browser, MDL.WINDOW_WEEK_BUTTON, time=5)
    day_button = wait_then_get_element(browser, MDL.WINDOW_DAY_BUTTON, time=5)
    assert week_button is not None
    assert day_button is not None
    assert week_button.get_attribute("aria-pressed") == "true"
    assert day_button.get_attribute("aria-pressed") == "false"

    # The SVG title node is appended by the admin-metrics chart-render
    # path on every refresh; presence proves a re-render against the
    # new window happened.
    chart_title_selector = f"{MDL.CHART_API} title"
    chart_title = wait_for_element_presence(browser, chart_title_selector, timeout=10)
    assert chart_title is not None


def test_substring_filter_narrows_top_table_to_no_matches(
    browser: WebDriver,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
    runner: Tuple[Flask, FlaskCliRunner],
):
    """
    GIVEN a logged-in admin user on the metrics dashboard with seeded
        API metrics rendered in the top-events table
    WHEN the admin types a substring into `#MetricsTopSubstringFilter-api`
        that does not match any rendered row
    THEN every `tr.MetricsTopTableRow` is removed and a single
        `tr.MetricsTopTableEmptyRow` is rendered in the API table,
        confirming the per-tab substring filter narrows the rendered set
        without a server round trip.
    """
    _seed_metrics_via_cli(runner)

    login_admin_and_open_metrics_dashboard(
        app=provide_app,
        browser=browser,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
    )

    wait_for_element_presence(browser, SEEDED_TABLE_ROW_SELECTOR, timeout=10)

    substring_input = wait_then_get_element(
        browser, MDL.TOP_SUBSTRING_FILTER_API, time=5
    )
    assert substring_input is not None
    substring_input.send_keys("zzz-nonexistent-event")

    empty_row_selector = f"{MDL.TOP_TABLE_API} tr.MetricsTopTableEmptyRow"
    empty_row = wait_for_element_presence(browser, empty_row_selector, timeout=5)
    assert empty_row is not None
    assert len(browser.find_elements(By.CSS_SELECTOR, SEEDED_TABLE_ROW_SELECTOR)) == 0
