from __future__ import annotations

import pytest
from flask import Flask
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.ui import Select

from backend.config import ConfigTestUI
from backend.db import db
from backend.cli.mock_options import SEED_LATENCY_ENDPOINTS
from backend.metrics.events import DeviceType
from backend.metrics.gauges import GaugeName
from backend.models.anonymous_gauges import Anonymous_Gauges
from backend.models.anonymous_latency_samples import Anonymous_Latency_Samples
from backend.models.anonymous_metrics import Anonymous_Metrics
from backend.utils.strings.admin_metrics_strs import ADMIN_METRICS_STRINGS
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS
from tests.functional.locators import MetricsDashboardLocators as MDL
from tests.functional.metrics_ui.selenium_utils import (
    login_admin_and_open_metrics_dashboard,
)
from tests.functional.selenium_utils import (
    wait_for_element_presence,
    wait_then_click_element,
    wait_then_get_at_least_n_elements,
    wait_then_get_element,
    wait_then_get_elements,
)

pytestmark = pytest.mark.metrics_ui

DEFAULT_ADMIN_USER_ID: int = 1
SEEDED_TABLE_ROW_SELECTOR: str = f"{MDL.TOP_TABLE_API} tbody tr.MetricsTopTableRow"
WINDOW_BUTTON_TIMEOUT_SECONDS: int = 5
PIPELINE_HEALTH_RENDER_TIMEOUT: int = 15
FLOWS_RENDER_TIMEOUT: int = 15
EXPECTED_FLOW_CARD_COUNT: int = 4
GAUGES_RENDER_TIMEOUT: int = 15
LATENCY_RENDER_TIMEOUT: int = 15
# The seeder writes the same two endpoints for every device type, so the
# per-endpoint percentile table groups down to exactly these two rows.
EXPECTED_LATENCY_ROW_COUNT: int = len(SEED_LATENCY_ENDPOINTS)
ALL_PIPELINE_HEALTH_BAR_SELECTORS: tuple[str, ...] = (
    MDL.PIPELINE_HEALTH_BAR_FETCH_DESKTOP,
    MDL.PIPELINE_HEALTH_BAR_FETCH_MOBILE,
    MDL.PIPELINE_HEALTH_BAR_BEACON_DESKTOP,
    MDL.PIPELINE_HEALTH_BAR_BEACON_MOBILE,
)
ALL_PIPELINE_HEALTH_LEGEND_SELECTORS: tuple[str, ...] = (
    MDL.PIPELINE_HEALTH_LEGEND_SWATCH_FETCH_DESKTOP,
    MDL.PIPELINE_HEALTH_LEGEND_SWATCH_FETCH_MOBILE,
    MDL.PIPELINE_HEALTH_LEGEND_SWATCH_BEACON_DESKTOP,
    MDL.PIPELINE_HEALTH_LEGEND_SWATCH_BEACON_MOBILE,
)


def test_admin_dashboard_renders_with_seeded_metrics(
    browser: WebDriver,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN a logged-in admin user and seeded AnonymousMetrics rows across
        all three event categories (API, UI, DOMAIN)
    WHEN the admin opens `/admin/metrics`
    THEN the dashboard title renders with the localized string and the
        API top-events table has at least one populated row.
    """
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
    login_admin_and_open_metrics_dashboard(
        app=provide_app,
        browser=browser,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
    )

    wait_for_element_presence(browser, SEEDED_TABLE_ROW_SELECTOR, timeout=10)

    # Gauges is the default tab, so the API panel (and its substring filter)
    # is hidden until the API tab is clicked.
    wait_then_click_element(
        browser, MDL.TAB_API_BUTTON, time=WINDOW_BUTTON_TIMEOUT_SECONDS
    )

    substring_input = wait_then_get_element(
        browser, MDL.TOP_SUBSTRING_FILTER_API, time=5
    )
    assert substring_input is not None
    substring_input.send_keys("zzz-nonexistent-event")

    empty_row_selector = f"{MDL.TOP_TABLE_API} tr.MetricsTopTableEmptyRow"
    empty_row = wait_for_element_presence(browser, empty_row_selector, timeout=5)
    assert empty_row is not None
    assert len(browser.find_elements(By.CSS_SELECTOR, SEEDED_TABLE_ROW_SELECTOR)) == 0


def test_device_filter_mobile_narrows_top_table_to_mobile_events(
    browser: WebDriver,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN a logged-in admin user on the metrics dashboard with seeded
        AnonymousMetrics rows that all carry `device_type=DESKTOP`
        (the default for the seeded UI event `ui_login_submit`)
    WHEN the admin switches to the UI tab and selects "Mobile" in
        `#MetricsTopDeviceFilter-ui`
    THEN the JSONB device-type filter narrows the UI top-events table
        to zero matching rows and the empty-state row is rendered,
        proving the UA classifier -> middleware -> JSONB filter ->
        frontend chain is wired end-to-end.
    """
    login_admin_and_open_metrics_dashboard(
        app=provide_app,
        browser=browser,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
    )

    # Wait for the dashboard's initial render so subsequent interactions
    # do not race the initial fetch attaching its handlers.
    wait_for_element_presence(browser, SEEDED_TABLE_ROW_SELECTOR, timeout=10)

    # Switch to the UI tab; its panel is hidden until the tab is clicked.
    wait_then_click_element(
        browser, MDL.TAB_UI_BUTTON, time=WINDOW_BUTTON_TIMEOUT_SECONDS
    )

    ui_table_row_selector = f"{MDL.TOP_TABLE_UI} tbody tr.MetricsTopTableRow"
    wait_for_element_presence(browser, ui_table_row_selector, timeout=10)

    device_filter = wait_then_get_element(browser, MDL.TOP_DEVICE_FILTER_UI, time=5)
    assert device_filter is not None
    Select(device_filter).select_by_value(str(int(DeviceType.MOBILE)))

    # The device filter is server-side (JSONB filter against
    # `dimensions.device_type`); when no mobile rows exist, the server
    # returns zero events and the renderer falls into the
    # `events.length === 0` branch using METRICS_EMPTY_STATE. The
    # METRICS_TOP_EMPTY_NO_MATCHES branch only fires for the client-side
    # substring filter (post-server-fetch). The empty row's presence
    # still proves the JSONB filter is wired end-to-end.
    empty_row_selector = f"{MDL.TOP_TABLE_UI} tr.MetricsTopTableEmptyRow"
    empty_row = wait_for_element_presence(browser, empty_row_selector, timeout=10)
    assert empty_row is not None
    assert empty_row.text == ADMIN_METRICS_STRINGS.METRICS_EMPTY_STATE
    assert len(browser.find_elements(By.CSS_SELECTOR, ui_table_row_selector)) == 0


def test_pipeline_health_card_renders_with_seeded_data(
    browser: WebDriver,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN seed-uniform-test-data has inserted one AnonymousMetrics row per
        `(transport × device_type)` for `API_METRICS_INGEST_BATCH` at
        batch_size_bucket="2-5"
    WHEN an admin opens `/admin/metrics`
    THEN the Pipeline Health card renders with one `<rect>` per swatch
        class (four rects total) and all four legend swatches are
        present in the DOM.
    """
    login_admin_and_open_metrics_dashboard(
        app=provide_app,
        browser=browser,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
    )

    # Pipeline Health is the 4th tab and starts hidden. Click it so the user
    # journey of "open dashboard, click Pipeline Health, see chart" is what
    # gets validated, not just DOM presence under a hidden panel.
    wait_then_click_element(browser, MDL.TAB_PIPELINE_HEALTH_BUTTON)

    # The card is server-pre-rendered (the partial ships in the HTML), so
    # its container always exists; the rects only appear after fetchAll()
    # completes the grouped-timeseries XHR and the renderer mutates the SVG.
    wait_for_element_presence(
        browser, MDL.PIPELINE_HEALTH_CARD, timeout=PIPELINE_HEALTH_RENDER_TIMEOUT
    )

    for bar_selector in ALL_PIPELINE_HEALTH_BAR_SELECTORS:
        bar_element = wait_for_element_presence(
            browser, bar_selector, timeout=PIPELINE_HEALTH_RENDER_TIMEOUT
        )
        assert (
            bar_element is not None
        ), f"Expected one rect for {bar_selector} but none rendered."

    for legend_selector in ALL_PIPELINE_HEALTH_LEGEND_SELECTORS:
        legend_swatch = browser.find_elements(By.CSS_SELECTOR, legend_selector)
        assert len(legend_swatch) == 1, (
            f"Expected exactly one legend swatch matching {legend_selector}, "
            f"got {len(legend_swatch)}."
        )


def test_pipeline_health_card_renders_empty_state_with_no_data(
    browser: WebDriver,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN the AnonymousMetrics table has been emptied AFTER the autouse
        seed fixture (so no API_METRICS_INGEST_BATCH rows exist)
    WHEN an admin opens `/admin/metrics`
    THEN the Pipeline Health card renders the empty-state text and zero
        stacked-bar rects.
    """
    with provide_app.app_context():
        Anonymous_Metrics.query.delete()
        db.session.commit()

    login_admin_and_open_metrics_dashboard(
        app=provide_app,
        browser=browser,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
    )

    wait_then_click_element(browser, MDL.TAB_PIPELINE_HEALTH_BUTTON)

    empty_state_element = wait_for_element_presence(
        browser,
        MDL.PIPELINE_HEALTH_EMPTY_STATE,
        timeout=PIPELINE_HEALTH_RENDER_TIMEOUT,
    )
    assert empty_state_element is not None
    assert (
        empty_state_element.text
        == ADMIN_METRICS_STRINGS.METRICS_PIPELINE_HEALTH_EMPTY_STATE
    )

    for bar_selector in ALL_PIPELINE_HEALTH_BAR_SELECTORS:
        rendered_bars = browser.find_elements(By.CSS_SELECTOR, bar_selector)
        assert len(rendered_bars) == 0, (
            f"Expected no rects for {bar_selector} in the empty-state, "
            f"got {len(rendered_bars)}."
        )


def test_flows_tab_renders_funnel_cards_with_seeded_data(
    browser: WebDriver,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN seed-uniform-test-data has inserted AnonymousMetrics rows spanning
        the UI / API / domain streams the funnels join
    WHEN an admin opens `/admin/metrics` and clicks the Flows tab
    THEN one funnel card renders per defined flow (four) and at least one
        funnel step row is present in the grid.
    """
    login_admin_and_open_metrics_dashboard(
        app=provide_app,
        browser=browser,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
    )

    wait_then_click_element(browser, MDL.TAB_FLOWS_BUTTON)

    flow_cards = wait_then_get_at_least_n_elements(
        browser,
        MDL.FLOWS_CARD,
        minimum_count=EXPECTED_FLOW_CARD_COUNT,
        time=FLOWS_RENDER_TIMEOUT,
    )
    assert len(flow_cards) >= EXPECTED_FLOW_CARD_COUNT, (
        f"Expected at least {EXPECTED_FLOW_CARD_COUNT} flow cards, "
        f"got {len(flow_cards)}."
    )

    funnel_steps = wait_then_get_elements(
        browser, MDL.FLOWS_FUNNEL_STEP, time=FLOWS_RENDER_TIMEOUT
    )
    assert len(funnel_steps) >= 1, "Expected at least one funnel step row to render."


def test_flows_tab_renders_empty_state_with_no_data(
    browser: WebDriver,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN the AnonymousMetrics table has been emptied AFTER the autouse seed
        fixture (so no flow events exist)
    WHEN an admin opens `/admin/metrics` and clicks the Flows tab
    THEN every funnel card renders the empty-state text instead of a funnel.
    """
    with provide_app.app_context():
        Anonymous_Metrics.query.delete()
        db.session.commit()

    login_admin_and_open_metrics_dashboard(
        app=provide_app,
        browser=browser,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
    )

    wait_then_click_element(browser, MDL.TAB_FLOWS_BUTTON)

    empty_state_element = wait_for_element_presence(
        browser, MDL.FLOWS_CARD_EMPTY, timeout=FLOWS_RENDER_TIMEOUT
    )
    assert empty_state_element is not None
    assert empty_state_element.text == ADMIN_METRICS_STRINGS.METRICS_FLOW_EMPTY


def test_gauges_tab_is_default_and_renders_chart_on_row_click(
    browser: WebDriver,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN the autouse `seeded_metrics` fixture has seeded AnonymousGauges rows
        (each gauge gets multiple sample timestamps via `_seed_uniform_gauges`)
    WHEN an admin opens `/admin/metrics`
    THEN the Gauges tab is selected by default (no click needed): a 2-column
        table renders one row per shipped gauge, the global summary is hidden,
        and no chart is shown (only the select-a-gauge prompt); clicking the
        total_users row renders exactly that gauge's inline `svg.gauge-chart`
        with a plotted line.
    """
    login_admin_and_open_metrics_dashboard(
        app=provide_app,
        browser=browser,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
    )

    # Gauges is the default landing tab — it loads without any tab click.
    gauges_tab = wait_then_get_element(browser, MDL.TAB_GAUGES_BUTTON, time=5)
    assert gauges_tab is not None
    assert gauges_tab.get_attribute("aria-selected") == "true"

    gauge_rows = wait_then_get_at_least_n_elements(
        browser,
        MDL.GAUGES_ROW,
        minimum_count=len(GaugeName),
        time=GAUGES_RENDER_TIMEOUT,
    )
    assert len(gauge_rows) >= len(GaugeName), (
        f"Expected at least {len(GaugeName)} gauge rows, " f"got {len(gauge_rows)}."
    )

    # The global event-totals summary is hidden on the Gauges tab.
    summary = browser.find_element(By.CSS_SELECTOR, MDL.SUMMARY_SECTION)
    assert not summary.is_displayed(), "Summary must be hidden on the Gauges tab."

    # No chart until a row is clicked — only the prompt is shown.
    prompt = wait_for_element_presence(
        browser, MDL.GAUGES_DETAIL_PROMPT, timeout=GAUGES_RENDER_TIMEOUT
    )
    assert prompt is not None
    assert prompt.text == ADMIN_METRICS_STRINGS.METRICS_GAUGE_SELECT_PROMPT
    assert (
        len(browser.find_elements(By.CSS_SELECTOR, MDL.GAUGES_DETAIL_CHART)) == 0
    ), "No gauge chart should render before a row is clicked."

    # Click a known volume gauge (total_users) that has multiple seeded
    # timestamps, so its chart must contain a plotted line.
    wait_then_click_element(browser, f'{MDL.GAUGES_ROW}[data-gauge-name="total_users"]')
    total_users_polyline = wait_for_element_presence(
        browser,
        "#gauge-chart-total_users polyline",
        timeout=GAUGES_RENDER_TIMEOUT,
    )
    assert total_users_polyline is not None
    detail_charts = browser.find_elements(By.CSS_SELECTOR, MDL.GAUGES_DETAIL_CHART)
    assert len(detail_charts) == 1, "Only the selected gauge's chart should render."
    assert (
        len(browser.find_elements(By.CSS_SELECTOR, MDL.GAUGES_DETAIL_PROMPT)) == 0
    ), "The prompt must be replaced by the chart once a row is selected."


def test_gauges_tab_renders_empty_state_with_no_data(
    browser: WebDriver,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN the AnonymousGauges table has been emptied AFTER the autouse seed
        fixture (so the batched response carries an empty gauges[])
    WHEN an admin opens `/admin/metrics` (Gauges is the default tab)
    THEN the panel-level empty state renders (a single MetricsEmptyState element
        appended to the grid) and no gauge rows are present.
    """
    with provide_app.app_context():
        Anonymous_Gauges.query.delete()
        db.session.commit()

    login_admin_and_open_metrics_dashboard(
        app=provide_app,
        browser=browser,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
    )

    # Gauges is the default tab, so the empty state renders without a tab click.
    empty_state_element = wait_for_element_presence(
        browser, MDL.GAUGES_PANEL_EMPTY_STATE, timeout=GAUGES_RENDER_TIMEOUT
    )
    assert empty_state_element is not None
    assert empty_state_element.text == ADMIN_METRICS_STRINGS.METRICS_GAUGES_EMPTY
    assert (
        len(browser.find_elements(By.CSS_SELECTOR, MDL.GAUGES_ROW)) == 0
    ), "No gauge rows should render when the batched response is empty."


def test_latency_tab_renders_percentile_table_and_chart_on_row_click(
    browser: WebDriver,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN the autouse `seeded_metrics` fixture has seeded
        AnonymousLatencySamples rows (a fixed durationMs distribution per
        seeded endpoint × device type via `_seed_uniform_latency`)
    WHEN an admin opens `/admin/metrics` and activates the Backend
        Performance (Latency) tab
    THEN the per-endpoint percentile table renders one row per seeded
        endpoint with non-empty p50/p95/p99 values, the global summary is
        hidden, only the select-an-endpoint prompt is shown (no chart), and
        clicking a row replaces the prompt with that endpoint's
        latency-over-time chart containing a plotted polyline.
    """
    login_admin_and_open_metrics_dashboard(
        app=provide_app,
        browser=browser,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
    )

    # Latency is not the default tab — activate it explicitly so the
    # "open dashboard, click Backend Performance, see table + chart" user
    # journey is what gets validated.
    latency_tab = wait_then_click_element(
        browser, MDL.TAB_LATENCY_BUTTON, time=WINDOW_BUTTON_TIMEOUT_SECONDS
    )
    assert latency_tab is not None
    assert latency_tab.get_attribute("aria-selected") == "true"

    latency_rows = wait_then_get_at_least_n_elements(
        browser,
        MDL.LATENCY_ROW,
        minimum_count=EXPECTED_LATENCY_ROW_COUNT,
        time=LATENCY_RENDER_TIMEOUT,
    )
    assert len(latency_rows) == EXPECTED_LATENCY_ROW_COUNT, (
        f"Expected exactly {EXPECTED_LATENCY_ROW_COUNT} per-endpoint latency "
        f"rows, got {len(latency_rows)}."
    )

    # Every seeded endpoint string is present as a row, and each row's
    # percentile cells carry a real value (not the en-dash null placeholder).
    rendered_endpoints = {row.get_attribute("data-endpoint") for row in latency_rows}
    seeded_endpoints = {endpoint for endpoint, _method in SEED_LATENCY_ENDPOINTS}
    assert seeded_endpoints.issubset(rendered_endpoints), (
        f"Seeded endpoints {seeded_endpoints} not all rendered; "
        f"table shows {rendered_endpoints}."
    )
    for row in latency_rows:
        metric_cells = row.find_elements(By.CSS_SELECTOR, "td.metric")
        assert len(metric_cells) == 3, "Each row must have p50/p95/p99 cells."
        for metric_cell in metric_cells:
            assert metric_cell.text.strip(), "Percentile cell must not be empty."

    # The global event-totals summary is hidden on the Latency tab.
    summary = browser.find_element(By.CSS_SELECTOR, MDL.SUMMARY_SECTION)
    assert not summary.is_displayed(), "Summary must be hidden on the Latency tab."

    # No chart until a row is clicked — only the prompt is shown.
    prompt = wait_for_element_presence(
        browser, MDL.LATENCY_DETAIL_PROMPT, timeout=LATENCY_RENDER_TIMEOUT
    )
    assert prompt is not None
    assert prompt.text == ADMIN_METRICS_STRINGS.METRICS_LATENCY_SELECT_PROMPT
    assert (
        len(browser.find_elements(By.CSS_SELECTOR, MDL.LATENCY_DETAIL_CHART)) == 0
    ), "No latency chart should render before a row is clicked."

    # Click the first seeded endpoint row; its timeseries chart must render
    # with at least one plotted polyline segment.
    first_endpoint = SEED_LATENCY_ENDPOINTS[0][0]
    wait_then_click_element(
        browser,
        f'{MDL.LATENCY_ROW}[data-endpoint="{first_endpoint}"]',
        time=LATENCY_RENDER_TIMEOUT,
    )
    chart_polyline = wait_for_element_presence(
        browser, MDL.LATENCY_DETAIL_CHART_LINE, timeout=LATENCY_RENDER_TIMEOUT
    )
    assert chart_polyline is not None
    detail_charts = browser.find_elements(By.CSS_SELECTOR, MDL.LATENCY_DETAIL_CHART)
    assert len(detail_charts) == 1, "Only the selected endpoint's chart should render."
    assert (
        len(browser.find_elements(By.CSS_SELECTOR, MDL.LATENCY_DETAIL_PROMPT)) == 0
    ), "The prompt must be replaced by the chart once a row is selected."


def test_latency_tab_renders_as_cards_without_truncation_at_all_widths(
    browser: WebDriver,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN the autouse `seeded_metrics` fixture has seeded AnonymousLatencySamples
        rows
    WHEN an admin opens `/admin/metrics`, activates the Backend Performance
        (Latency) tab, and views it at BOTH a wide desktop and a phone width
    THEN at every width the percentile table renders as cards (no column table):
        the header row is hidden, value cells lay out as flex "label value"
        rows carrying the `ms` unit via `data-label`, and each endpoint name
        renders in full with no horizontal overflow / ellipsis.
    """
    # Wide desktop first — the originally-reported truncation happened here, not
    # only on phones — then a phone width. Cards must hold at both.
    desktop_width = (1280, 900)
    phone_width = (390, 844)
    browser.set_window_size(*desktop_width)

    login_admin_and_open_metrics_dashboard(
        app=provide_app,
        browser=browser,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
    )

    wait_then_click_element(
        browser, MDL.TAB_LATENCY_BUTTON, time=WINDOW_BUTTON_TIMEOUT_SECONDS
    )

    wait_then_get_at_least_n_elements(
        browser,
        MDL.LATENCY_ROW,
        minimum_count=EXPECTED_LATENCY_ROW_COUNT,
        time=LATENCY_RENDER_TIMEOUT,
    )

    for width, height in (desktop_width, phone_width):
        browser.set_window_size(width, height)
        latency_rows = browser.find_elements(By.CSS_SELECTOR, MDL.LATENCY_ROW)
        assert len(latency_rows) == EXPECTED_LATENCY_ROW_COUNT

        # Card mode is active: value cells lay out as flex rows (label + value)
        # rather than table cells. (The header row is visually hidden via clip
        # for screen readers, so geometry — not is_displayed — is the signal.)
        sample_metric_cell = latency_rows[0].find_element(By.CSS_SELECTOR, "td.metric")
        metric_display = browser.execute_script(
            "return window.getComputedStyle(arguments[0]).display;",
            sample_metric_cell,
        )
        assert metric_display == "flex", (
            f"At {width}px metric cells must render as flex card rows; "
            f"got '{metric_display}'."
        )

        for row in latency_rows:
            endpoint_cell = row.find_element(By.CSS_SELECTOR, "td.endpoint")
            # The full endpoint label is present (method + path), not an ellipsis.
            expected_endpoint = row.get_attribute("data-endpoint")
            assert expected_endpoint in endpoint_cell.text, (
                f"Endpoint cell '{endpoint_cell.text}' must contain the full "
                f"endpoint '{expected_endpoint}' at {width}px."
            )
            assert (
                "…" not in endpoint_cell.text and "..." not in endpoint_cell.text
            ), f"Endpoint name must not be truncated at {width}px."
            # The wrapping cell must not overflow its box (truncation produces
            # scrollWidth > clientWidth; a wrapping cell stays within its box).
            overflowed = browser.execute_script(
                "return arguments[0].scrollWidth > arguments[0].clientWidth + 1;",
                endpoint_cell,
            )
            assert not overflowed, f"Endpoint cell overflows (truncated) at {width}px."

            # Each percentile value surfaces its column label + unit via ::before.
            p50_cell = row.find_elements(By.CSS_SELECTOR, "td.metric")[0]
            before_content = browser.execute_script(
                "return window.getComputedStyle(arguments[0], '::before').content;",
                p50_cell,
            )
            assert "ms" in before_content, (
                f"Metric label must include the 'ms' unit at {width}px; "
                f"got {before_content}."
            )


def test_latency_tab_renders_empty_state_with_no_samples(
    browser: WebDriver,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN the AnonymousLatencySamples table has been emptied AFTER the autouse
        seed fixture (so the query window contains no samples)
    WHEN an admin opens `/admin/metrics` and activates the Backend
        Performance (Latency) tab
    THEN the percentile table renders its empty-state row with the bridged
        no-samples message and no per-endpoint rows are present.
    """
    with provide_app.app_context():
        Anonymous_Latency_Samples.query.delete()
        db.session.commit()

    login_admin_and_open_metrics_dashboard(
        app=provide_app,
        browser=browser,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
    )

    wait_then_click_element(
        browser, MDL.TAB_LATENCY_BUTTON, time=WINDOW_BUTTON_TIMEOUT_SECONDS
    )

    empty_row = wait_for_element_presence(
        browser, MDL.LATENCY_EMPTY_ROW, timeout=LATENCY_RENDER_TIMEOUT
    )
    assert empty_row is not None
    assert empty_row.text.strip() == ADMIN_METRICS_STRINGS.METRICS_LATENCY_EMPTY
    assert (
        len(browser.find_elements(By.CSS_SELECTOR, MDL.LATENCY_ROW)) == 0
    ), "No per-endpoint latency rows should render when no samples exist."
