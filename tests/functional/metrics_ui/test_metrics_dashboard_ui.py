from __future__ import annotations

import re

import pytest
from flask import Flask
from playwright.sync_api import Locator, Page, Route, expect

from backend.cli.mock_options import SEED_LATENCY_ENDPOINTS
from backend.config import ConfigTestUI
from backend.db import db
from backend.metrics.events import DeviceType
from backend.metrics.flow_limits import FLOW_LIMITS
from backend.metrics.gauges import GaugeName
from backend.models.anonymous_gauges import Anonymous_Gauges
from backend.models.anonymous_latency_samples import Anonymous_Latency_Samples
from backend.models.anonymous_metrics import Anonymous_Metrics
from backend.models.metric_flows import Metric_Flows
from backend.utils.strings.admin_metrics_strs import ADMIN_METRICS_STRINGS
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS
from tests.functional.locators import MetricsDashboardLocators as MDL
from tests.functional.metrics_ui.playwright_utils import (
    SeedCustomFlows,
    login_admin_and_open_metrics_dashboard,
    one_step_definition,
    removed_event_definition,
)
from tests.functional.playwright_utils import (
    wait_for_element_presence,
    wait_then_click_element,
    wait_then_get_at_least_n_elements,
    wait_then_get_element,
    wait_then_get_elements,
)

pytestmark = pytest.mark.metrics_ui

DEFAULT_ADMIN_USER_ID: int = 1
SEEDED_TABLE_ROW_SELECTOR: str = f"{MDL.TOP_TABLE_API} tbody tr.MetricsTopTableRow"
# The seeder writes the same two endpoints for every device type, so the
# per-endpoint percentile table groups down to exactly these two rows.
EXPECTED_LATENCY_ROW_COUNT: int = len(SEED_LATENCY_ENDPOINTS)
EXPECTED_FLOW_CARD_COUNT: int = 4
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
    page: Page,
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
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
    )

    title_locator = wait_then_get_element(page=page, css_selector=MDL.DASHBOARD_TITLE)
    expect(title_locator).to_have_text(UI_TEST_STRINGS.METRICS_DASHBOARD_TITLE)

    wait_for_element_presence(page=page, css_selector=SEEDED_TABLE_ROW_SELECTOR)


def test_window_switch_to_week_re_renders_chart(
    page: Page,
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
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
    )

    # Wait for the dashboard's initial render so the click below does
    # not race the initial fetch attaching its handlers.
    wait_for_element_presence(page=page, css_selector=SEEDED_TABLE_ROW_SELECTOR)

    wait_then_click_element(page=page, css_selector=MDL.WINDOW_WEEK_BUTTON)

    expect(page.locator(MDL.WINDOW_WEEK_BUTTON)).to_have_attribute(
        "aria-pressed", "true"
    )
    expect(page.locator(MDL.WINDOW_DAY_BUTTON)).to_have_attribute(
        "aria-pressed", "false"
    )

    # The SVG title node is appended by the admin-metrics chart-render
    # path on every refresh; presence proves a re-render against the
    # new window happened.
    chart_title_selector = f"{MDL.CHART_API} title"
    wait_for_element_presence(page=page, css_selector=chart_title_selector)


def test_substring_filter_narrows_top_table_to_no_matches(
    page: Page,
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
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
    )

    wait_for_element_presence(page=page, css_selector=SEEDED_TABLE_ROW_SELECTOR)

    # Gauges is the default tab, so the API panel (and its substring filter)
    # is hidden until the API tab is clicked.
    wait_then_click_element(page=page, css_selector=MDL.TAB_API_BUTTON)

    substring_input = wait_then_get_element(
        page=page, css_selector=MDL.TOP_SUBSTRING_FILTER_API
    )
    substring_input.fill("zzz-nonexistent-event")

    empty_row_selector = f"{MDL.TOP_TABLE_API} tr.MetricsTopTableEmptyRow"
    wait_for_element_presence(page=page, css_selector=empty_row_selector)
    assert page.locator(SEEDED_TABLE_ROW_SELECTOR).count() == 0


def test_device_filter_mobile_narrows_top_table_to_mobile_events(
    page: Page,
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
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
    )

    # Wait for the dashboard's initial render so subsequent interactions
    # do not race the initial fetch attaching its handlers.
    wait_for_element_presence(page=page, css_selector=SEEDED_TABLE_ROW_SELECTOR)

    # Switch to the UI tab; its panel is hidden until the tab is clicked.
    wait_then_click_element(page=page, css_selector=MDL.TAB_UI_BUTTON)

    ui_table_row_selector = f"{MDL.TOP_TABLE_UI} tbody tr.MetricsTopTableRow"
    wait_for_element_presence(page=page, css_selector=ui_table_row_selector)

    wait_then_get_element(page=page, css_selector=MDL.TOP_DEVICE_FILTER_UI)
    page.locator(MDL.TOP_DEVICE_FILTER_UI).select_option(str(int(DeviceType.MOBILE)))

    # The device filter is server-side (JSONB filter against
    # `dimensions.device_type`); when no mobile rows exist, the server
    # returns zero events and the renderer falls into the
    # `events.length === 0` branch using METRICS_EMPTY_STATE. The
    # METRICS_TOP_EMPTY_NO_MATCHES branch only fires for the client-side
    # substring filter (post-server-fetch). The empty row's presence
    # still proves the JSONB filter is wired end-to-end.
    empty_row_selector = f"{MDL.TOP_TABLE_UI} tr.MetricsTopTableEmptyRow"
    empty_row = wait_for_element_presence(page=page, css_selector=empty_row_selector)
    expect(empty_row).to_have_text(ADMIN_METRICS_STRINGS.METRICS_EMPTY_STATE)
    assert page.locator(ui_table_row_selector).count() == 0


def test_pipeline_health_card_renders_with_seeded_data(
    page: Page,
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
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
    )

    # Pipeline Health is the 4th tab and starts hidden. Click it so the user
    # journey of "open dashboard, click Pipeline Health, see chart" is what
    # gets validated, not just DOM presence under a hidden panel.
    wait_then_click_element(page=page, css_selector=MDL.TAB_PIPELINE_HEALTH_BUTTON)

    # The card is server-pre-rendered (the partial ships in the HTML), so
    # its container always exists; the rects only appear after fetchAll()
    # completes the grouped-timeseries XHR and the renderer mutates the SVG.
    wait_for_element_presence(page=page, css_selector=MDL.PIPELINE_HEALTH_CARD)

    for bar_selector in ALL_PIPELINE_HEALTH_BAR_SELECTORS:
        wait_for_element_presence(page=page, css_selector=bar_selector)

    for legend_selector in ALL_PIPELINE_HEALTH_LEGEND_SELECTORS:
        assert page.locator(legend_selector).count() == 1, (
            f"Expected exactly one legend swatch matching {legend_selector}, "
            f"got {page.locator(legend_selector).count()}."
        )


def test_pipeline_health_card_renders_empty_state_with_no_data(
    page: Page,
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
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
    )

    wait_then_click_element(page=page, css_selector=MDL.TAB_PIPELINE_HEALTH_BUTTON)

    empty_state_element = wait_for_element_presence(
        page=page, css_selector=MDL.PIPELINE_HEALTH_EMPTY_STATE
    )
    expect(empty_state_element).to_have_text(
        ADMIN_METRICS_STRINGS.METRICS_PIPELINE_HEALTH_EMPTY_STATE
    )

    for bar_selector in ALL_PIPELINE_HEALTH_BAR_SELECTORS:
        assert page.locator(bar_selector).count() == 0, (
            f"Expected no rects for {bar_selector} in the empty-state, "
            f"got {page.locator(bar_selector).count()}."
        )


def test_flows_tab_renders_funnel_cards_with_seeded_data(
    page: Page,
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
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
    )

    wait_then_click_element(page=page, css_selector=MDL.TAB_FLOWS_BUTTON)

    flow_cards = wait_then_get_at_least_n_elements(
        page=page,
        css_selector=MDL.FLOWS_CARD,
        minimum_count=EXPECTED_FLOW_CARD_COUNT,
    )
    assert len(flow_cards) >= EXPECTED_FLOW_CARD_COUNT, (
        f"Expected at least {EXPECTED_FLOW_CARD_COUNT} flow cards, "
        f"got {len(flow_cards)}."
    )
    # No custom flows are seeded here, so the grid holds exactly the built-ins.
    expect(page.locator(MDL.FLOWS_CARD)).to_have_count(EXPECTED_FLOW_CARD_COUNT)

    funnel_steps = wait_then_get_elements(page=page, css_selector=MDL.FLOWS_FUNNEL_STEP)
    assert len(funnel_steps) >= 1, "Expected at least one funnel step row to render."


def test_flows_tab_renders_empty_state_with_no_data(
    page: Page,
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
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
    )

    wait_then_click_element(page=page, css_selector=MDL.TAB_FLOWS_BUTTON)

    empty_state_element = wait_for_element_presence(
        page=page, css_selector=MDL.FLOWS_CARD_EMPTY
    )
    expect(empty_state_element).to_have_text(ADMIN_METRICS_STRINGS.METRICS_FLOW_EMPTY)


def test_gauges_tab_is_default_and_renders_chart_on_row_click(
    page: Page,
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
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
    )

    # Gauges is the default landing tab — it loads without any tab click.
    expect(page.locator(MDL.TAB_GAUGES_BUTTON)).to_have_attribute(
        "aria-selected", "true"
    )

    gauge_rows = wait_then_get_at_least_n_elements(
        page=page,
        css_selector=MDL.GAUGES_ROW,
        minimum_count=len(GaugeName),
    )
    assert len(gauge_rows) >= len(GaugeName), (
        f"Expected at least {len(GaugeName)} gauge rows, got {len(gauge_rows)}."
    )

    # The global event-totals summary is hidden on the Gauges tab.
    expect(page.locator(MDL.SUMMARY_SECTION)).to_be_hidden()

    # No chart until a row is clicked — only the prompt is shown.
    prompt = wait_for_element_presence(page=page, css_selector=MDL.GAUGES_DETAIL_PROMPT)
    expect(prompt).to_have_text(ADMIN_METRICS_STRINGS.METRICS_GAUGE_SELECT_PROMPT)
    assert page.locator(MDL.GAUGES_DETAIL_CHART).count() == 0, (
        "No gauge chart should render before a row is clicked."
    )

    # Click a known volume gauge (total_users) that has multiple seeded
    # timestamps, so its chart must contain a plotted line.
    wait_then_click_element(
        page=page, css_selector=f'{MDL.GAUGES_ROW}[data-gauge-name="total_users"]'
    )
    wait_for_element_presence(
        page=page, css_selector="#gauge-chart-total_users polyline"
    )
    assert page.locator(MDL.GAUGES_DETAIL_CHART).count() == 1, (
        "Only the selected gauge's chart should render."
    )
    assert page.locator(MDL.GAUGES_DETAIL_PROMPT).count() == 0, (
        "The prompt must be replaced by the chart once a row is selected."
    )


def test_gauges_row_tap_scrolls_chart_into_view_on_mobile(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN a phone-width viewport (390x844) and the full seeded gauge table
    WHEN the admin taps the median_urls_per_utub row
    THEN the gauge chart, initially below the fold, scrolls into the viewport.
    """
    page.set_viewport_size({"width": 390, "height": 844})
    login_admin_and_open_metrics_dashboard(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
    )

    wait_then_get_at_least_n_elements(
        page=page,
        css_selector=MDL.GAUGES_ROW,
        minimum_count=len(GaugeName),
    )

    # Precondition: the detail area starts below the fold of the tall table.
    expect(page.locator(MDL.GAUGES_DETAIL)).not_to_be_in_viewport()

    wait_then_click_element(
        page=page,
        css_selector=f'{MDL.GAUGES_ROW}[data-gauge-name="median_urls_per_utub"]',
    )
    expect(page.locator("#gauge-chart-median_urls_per_utub")).to_be_in_viewport()


def test_gauges_tab_renders_empty_state_with_no_data(
    page: Page,
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
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
    )

    # Gauges is the default tab, so the empty state renders without a tab click.
    empty_state_element = wait_for_element_presence(
        page=page, css_selector=MDL.GAUGES_PANEL_EMPTY_STATE
    )
    expect(empty_state_element).to_have_text(ADMIN_METRICS_STRINGS.METRICS_GAUGES_EMPTY)
    assert page.locator(MDL.GAUGES_ROW).count() == 0, (
        "No gauge rows should render when the batched response is empty."
    )


def test_latency_tab_renders_percentile_table_and_chart_on_row_click(
    page: Page,
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
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
    )

    # Latency is not the default tab — activate it explicitly so the
    # "open dashboard, click Backend Performance, see table + chart" user
    # journey is what gets validated.
    wait_then_click_element(page=page, css_selector=MDL.TAB_LATENCY_BUTTON)
    expect(page.locator(MDL.TAB_LATENCY_BUTTON)).to_have_attribute(
        "aria-selected", "true"
    )

    latency_rows = wait_then_get_at_least_n_elements(
        page=page,
        css_selector=MDL.LATENCY_ROW,
        minimum_count=EXPECTED_LATENCY_ROW_COUNT,
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
        metric_cells = row.locator("td.metric").all()
        assert len(metric_cells) == 3, "Each row must have p50/p95/p99 cells."
        for metric_cell in metric_cells:
            assert metric_cell.inner_text().strip(), (
                "Percentile cell must not be empty."
            )

    # The global event-totals summary is hidden on the Latency tab.
    expect(page.locator(MDL.SUMMARY_SECTION)).to_be_hidden()

    # No chart until a row is clicked — only the prompt is shown.
    prompt = wait_for_element_presence(
        page=page, css_selector=MDL.LATENCY_DETAIL_PROMPT
    )
    expect(prompt).to_have_text(ADMIN_METRICS_STRINGS.METRICS_LATENCY_SELECT_PROMPT)
    assert page.locator(MDL.LATENCY_DETAIL_CHART).count() == 0, (
        "No latency chart should render before a row is clicked."
    )

    # Click the first seeded endpoint row; its timeseries chart must render
    # with at least one plotted polyline segment.
    first_endpoint = SEED_LATENCY_ENDPOINTS[0][0]
    wait_then_click_element(
        page=page,
        css_selector=f'{MDL.LATENCY_ROW}[data-endpoint="{first_endpoint}"]',
    )
    wait_for_element_presence(page=page, css_selector=MDL.LATENCY_DETAIL_CHART_LINE)
    assert page.locator(MDL.LATENCY_DETAIL_CHART).count() == 1, (
        "Only the selected endpoint's chart should render."
    )
    assert page.locator(MDL.LATENCY_DETAIL_PROMPT).count() == 0, (
        "The prompt must be replaced by the chart once a row is selected."
    )


def test_latency_tab_renders_as_cards_without_truncation_at_all_widths(
    page: Page,
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
    page.set_viewport_size({"width": desktop_width[0], "height": desktop_width[1]})

    login_admin_and_open_metrics_dashboard(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
    )

    wait_then_click_element(page=page, css_selector=MDL.TAB_LATENCY_BUTTON)

    wait_then_get_at_least_n_elements(
        page=page,
        css_selector=MDL.LATENCY_ROW,
        minimum_count=EXPECTED_LATENCY_ROW_COUNT,
    )

    for width, height in (desktop_width, phone_width):
        page.set_viewport_size({"width": width, "height": height})
        latency_rows = page.locator(MDL.LATENCY_ROW).all()
        assert len(latency_rows) == EXPECTED_LATENCY_ROW_COUNT

        # Card mode is active: value cells lay out as flex rows (label + value)
        # rather than table cells. (The header row is visually hidden via clip
        # for screen readers, so geometry — not is_displayed — is the signal.)
        sample_metric_cell = latency_rows[0].locator("td.metric").first
        metric_display = sample_metric_cell.evaluate(
            "element => window.getComputedStyle(element).display"
        )
        assert metric_display == "flex", (
            f"At {width}px metric cells must render as flex card rows; "
            f"got '{metric_display}'."
        )

        for row in latency_rows:
            endpoint_cell = row.locator("td.endpoint").first
            # The full endpoint label is present (method + path), not an ellipsis.
            expected_endpoint = row.get_attribute("data-endpoint")
            endpoint_text = endpoint_cell.inner_text()
            assert expected_endpoint in endpoint_text, (
                f"Endpoint cell '{endpoint_text}' must contain the full "
                f"endpoint '{expected_endpoint}' at {width}px."
            )
            assert "…" not in endpoint_text and "..." not in endpoint_text, (
                f"Endpoint name must not be truncated at {width}px."
            )
            # The wrapping cell must not overflow its box (truncation produces
            # scrollWidth > clientWidth; a wrapping cell stays within its box).
            overflowed = endpoint_cell.evaluate(
                "element => element.scrollWidth > element.clientWidth + 1"
            )
            assert not overflowed, f"Endpoint cell overflows (truncated) at {width}px."

            # Each percentile value surfaces its column label + unit via ::before.
            p50_cell = row.locator("td.metric").first
            before_content = p50_cell.evaluate(
                "element => window.getComputedStyle(element, '::before').content"
            )
            assert "ms" in before_content, (
                f"Metric label must include the 'ms' unit at {width}px; "
                f"got {before_content}."
            )


def test_latency_cards_have_consistent_dividers_and_selected_ring(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN the autouse `seeded_metrics` fixture has seeded AnonymousLatencySamples
        rows rendered as latency cards
    WHEN an admin opens the Backend Performance (Latency) tab
    THEN every card shares one identical surface colour (the inherited
        `.top-table` zebra striping is neutralised — no "darker" alternating
        cards), each metric row carries a visible ruled divider with none after
        the final row, and selecting a card changes only its border (a green
        ring), not its background.
    """
    login_admin_and_open_metrics_dashboard(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
    )

    wait_then_click_element(page=page, css_selector=MDL.TAB_LATENCY_BUTTON)

    latency_rows = wait_then_get_at_least_n_elements(
        page=page,
        css_selector=MDL.LATENCY_ROW,
        minimum_count=EXPECTED_LATENCY_ROW_COUNT,
    )

    # Read before any hover/selection (mouse rests on the tab button, not a card)
    # so the only background variation that could exist is the zebra striping.
    card_backgrounds = {
        row.evaluate("element => window.getComputedStyle(element).backgroundColor")
        for row in latency_rows
    }
    assert len(card_backgrounds) == 1, (
        f"All latency cards must share one surface colour (no zebra striping); "
        f"got {card_backgrounds}."
    )

    # Ruled rows: each metric line has a visible bottom divider; the last line
    # (Samples) has none, so the divider never collides with the card border.
    first_row = latency_rows[0]
    metric_cell = first_row.locator("td.metric").first
    samples_cell = first_row.locator("td.samples").first
    metric_border = metric_cell.evaluate(
        "element => window.getComputedStyle(element).borderBottomWidth"
    )
    samples_border = samples_cell.evaluate(
        "element => window.getComputedStyle(element).borderBottomWidth"
    )
    assert metric_border != "0px", "Metric rows must show a ruled divider."
    assert samples_border == "0px", "The last (Samples) row must have no divider."

    # Selecting a card changes only its border (green ring) — not its surface.
    unselected_border = latency_rows[1].evaluate(
        "element => window.getComputedStyle(element).borderTopColor"
    )
    wait_then_click_element(
        page=page,
        css_selector=f'{MDL.LATENCY_ROW}[data-endpoint="{SEED_LATENCY_ENDPOINTS[0][0]}"]',
    )
    selected_row = wait_for_element_presence(
        page=page, css_selector=MDL.LATENCY_ROW_SELECTED
    )
    selected_border = selected_row.evaluate(
        "element => window.getComputedStyle(element).borderTopColor"
    )
    assert selected_border != unselected_border, (
        "The selected card must show a distinct (green) border ring; "
        f"selected={selected_border}, unselected={unselected_border}."
    )


def test_latency_tab_renders_empty_state_with_no_samples(
    page: Page,
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
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
    )

    wait_then_click_element(page=page, css_selector=MDL.TAB_LATENCY_BUTTON)

    empty_row = wait_for_element_presence(page=page, css_selector=MDL.LATENCY_EMPTY_ROW)
    expect(empty_row).to_have_text(ADMIN_METRICS_STRINGS.METRICS_LATENCY_EMPTY)
    assert page.locator(MDL.LATENCY_ROW).count() == 0, (
        "No per-endpoint latency rows should render when no samples exist."
    )


def test_latency_tab_shows_approximate_note_for_long_window(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN the autouse `seeded_metrics` fixture has seeded both raw
        AnonymousLatencySamples and AnonymousLatencyDailyRollups rows
    WHEN an admin opens the Backend Performance (Latency) tab on the
        default "Day" window, then switches to the "Year" window, then to
        the "Month" window
    THEN with raw retention at 35 days the "Day" and "Month" windows stay
        on the exact raw path (no approximate note), while only "Year"
        crosses into the daily rollup tier — surfacing the
        approximate-summary note on the table render and the
        daily-resolution note once an endpoint's daily-grain trend chart
        is rendered, while per-endpoint rows still render from the seeded
        rollup data.

    The approximate-summary note is injected by the percentile-table
    render, so it appears as soon as the Year window's table lands. The
    daily-resolution note is injected by the detail-chart renderer
    (`renderLatencyDetailChart`), which only runs once an endpoint row is
    selected and its timeseries fetch resolves — so the test clicks a row
    on the Year window before asserting that note.
    """
    login_admin_and_open_metrics_dashboard(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
    )

    # Activate the Latency tab and wait for its initial (Day-window) render
    # so the window-switch clicks below do not race the initial fetch.
    wait_then_click_element(page=page, css_selector=MDL.TAB_LATENCY_BUTTON)
    wait_then_get_at_least_n_elements(
        page=page,
        css_selector=MDL.LATENCY_ROW,
        minimum_count=EXPECTED_LATENCY_ROW_COUNT,
    )

    # Day is inside the 35-day raw retention -> exact path, no notes.
    assert page.locator(MDL.LATENCY_APPROXIMATE_NOTE).count() == 0, (
        "The approximate note must be absent on the exact (Day) raw window."
    )
    assert page.locator(MDL.LATENCY_DAILY_RESOLUTION_NOTE).count() == 0, (
        "The daily-resolution note must be absent on the exact (Day) raw window."
    )

    # Year crosses the 35-day boundary -> rollup tier: approximate summary
    # note + daily-resolution note appear, and per-endpoint rows still
    # render from the seeded rollup data.
    wait_then_click_element(page=page, css_selector=MDL.WINDOW_YEAR_BUTTON)

    approximate_note = wait_for_element_presence(
        page=page, css_selector=MDL.LATENCY_APPROXIMATE_NOTE
    )
    expect(approximate_note).to_have_text(
        ADMIN_METRICS_STRINGS.METRICS_LATENCY_APPROXIMATE_NOTE
    )

    # The rollup still serves per-endpoint rows for the long window.
    year_rows = wait_then_get_at_least_n_elements(
        page=page,
        css_selector=MDL.LATENCY_ROW,
        minimum_count=1,
    )
    assert len(year_rows) >= 1, (
        "Year window must still render per-endpoint rollup rows."
    )

    # The daily-resolution note lives in the detail-chart container, which
    # is only rendered once an endpoint row is selected. Click a seeded
    # endpoint so the daily-grain trend chart (and its note) render.
    first_endpoint = SEED_LATENCY_ENDPOINTS[0][0]
    wait_then_click_element(
        page=page,
        css_selector=f'{MDL.LATENCY_ROW}[data-endpoint="{first_endpoint}"]',
    )

    daily_note = wait_for_element_presence(
        page=page, css_selector=MDL.LATENCY_DAILY_RESOLUTION_NOTE
    )
    expect(daily_note).to_have_text(
        ADMIN_METRICS_STRINGS.METRICS_LATENCY_DAILY_RESOLUTION_NOTE
    )

    # Month (~28-31 days) is inside the 35-day raw retention -> exact path:
    # both notes disappear again.
    wait_then_click_element(page=page, css_selector=MDL.WINDOW_MONTH_BUTTON)

    # The Month re-render replaces the table rows; wait for the exact-path
    # render to land before asserting the notes were removed.
    wait_then_get_at_least_n_elements(
        page=page,
        css_selector=MDL.LATENCY_ROW,
        minimum_count=EXPECTED_LATENCY_ROW_COUNT,
    )

    expect(page.locator(MDL.LATENCY_APPROXIMATE_NOTE)).to_have_count(0)
    expect(page.locator(MDL.LATENCY_DAILY_RESOLUTION_NOTE)).to_have_count(0)


# ---------------------------------------------------------------------------
# Flows grid: custom flows, delete confirm, needs-attention, toolbar
# ---------------------------------------------------------------------------

DESKTOP_VIEWPORT: dict[str, int] = {"width": 1280, "height": 900}
MOBILE_VIEWPORT: dict[str, int] = {"width": 420, "height": 900}
VIEWPORTS = pytest.mark.parametrize(
    "viewport",
    [DESKTOP_VIEWPORT, MOBILE_VIEWPORT],
    ids=["1280", "420"],
)
FLOW_LIST_URL_RE: re.Pattern[str] = re.compile(r".*/admin/metrics/flows(\?.*)?$")
FLOW_DELETE_URL_RE: re.Pattern[str] = re.compile(r".*/admin/metrics/flows/[^/?]+$")
FLOW_QUERY_URL_RE: re.Pattern[str] = re.compile(r".*/api/metrics/query/flow(\?.*)?$")
MIN_TOUCH_TARGET_PX: int = 44
LONG_FLOW_NAME: str = "x" * FLOW_LIMITS.NAME_MAX_LENGTH


class HeldFlowQueries:
    """Holds every `/api/metrics/query/flow` request until `release()`;
    afterwards requests pass straight through."""

    def __init__(self) -> None:
        self._held: list[Route] = []
        self._released: bool = False

    def handle(self, route: Route) -> None:
        if self._released:
            route.continue_()
        else:
            self._held.append(route)

    def release(self) -> None:
        self._released = True
        for route in self._held:
            route.continue_()
        self._held.clear()


def _open_flows_tab(
    *,
    page: Page,
    app: Flask,
    port: int,
    config: ConfigTestUI,
    viewport: dict[str, int] | None = None,
    wait_for_settled: bool = True,
) -> None:
    """Log in, open the Flows tab and (by default) wait for every card to leave
    the loading state, since cards are rebuilt when their funnel settles.
    Tests that hold `/flow` responses pass ``wait_for_settled=False``."""
    if viewport is not None:
        page.set_viewport_size(viewport)
    login_admin_and_open_metrics_dashboard(
        app=app,
        context=page.context,
        page=page,
        port=port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=config,
    )
    wait_then_click_element(page=page, css_selector=MDL.TAB_FLOWS_BUTTON)
    if wait_for_settled:
        expect(page.locator(MDL.FLOWS_COUNT)).not_to_have_text(
            UI_TEST_STRINGS.METRICS_FLOWS_COUNT_LOADING
        )
        expect(page.locator(MDL.FLOWS_CARD_LOADING)).to_have_count(0)


def _custom_card(page: Page, flow_id: str) -> Locator:
    return page.locator(f'{MDL.FLOWS_CARD}[data-flow-id="{flow_id}"]')


def _count_text(*, custom: int) -> str:
    return UI_TEST_STRINGS.METRICS_FLOWS_COUNT.format(
        builtin=EXPECTED_FLOW_CARD_COUNT,
        custom=custom,
        max=FLOW_LIMITS.MAX_CUSTOM,
    )


def _delete_other_admin(*, app: Flask, flow_id: str) -> None:
    """Remove the row as if another admin had deleted it."""
    with app.app_context():
        Metric_Flows.query.filter_by(id=int(flow_id.removeprefix("custom_"))).delete()
        db.session.commit()


def test_flows_toolbar_shows_counts_and_custom_card_controls(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
    seed_custom_flows: SeedCustomFlows,
):
    """
    GIVEN two custom flows alongside the four built-ins
    WHEN an admin opens the Flows tab
    THEN the toolbar reads "4 built-in · 2 custom (of 20)" with no zero-custom
        hint, custom cards show the Custom badge and a labelled Delete button,
        and built-in cards show neither a custom badge nor Delete.
    """
    flow_ids = seed_custom_flows(display_names=["Alpha flow", "Beta flow"])
    _open_flows_tab(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
    )

    expect(page.locator(MDL.FLOWS_CARD)).to_have_count(EXPECTED_FLOW_CARD_COUNT + 2)
    expect(page.locator(MDL.FLOWS_HEADING)).to_have_text(
        UI_TEST_STRINGS.METRICS_FLOWS_HEADING
    )
    expect(page.locator(MDL.FLOWS_COUNT)).to_have_text(_count_text(custom=2))
    expect(page.locator(MDL.FLOWS_HINT)).to_be_hidden()

    for flow_id, name in zip(flow_ids, ["Alpha flow", "Beta flow"]):
        card = _custom_card(page, flow_id)
        expect(card.locator(".flow-badge.custom")).to_have_text(
            UI_TEST_STRINGS.METRICS_FLOW_BADGE_CUSTOM
        )
        delete_button = card.locator(".flow-delete-btn")
        expect(delete_button).to_have_count(1)
        expect(delete_button).to_have_attribute(
            "aria-label",
            UI_TEST_STRINGS.METRICS_FLOW_DELETE_LABEL.format(name=name),
        )

    built_in_cards = page.locator(f"{MDL.FLOWS_CARD}:not([data-flow-id^=custom_])")
    expect(built_in_cards).to_have_count(EXPECTED_FLOW_CARD_COUNT)
    expect(built_in_cards.locator(".flow-delete-btn")).to_have_count(0)
    expect(built_in_cards.locator(".flow-badge.custom")).to_have_count(0)


def test_flows_toolbar_shows_zero_custom_hint(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN no custom flows
    WHEN an admin opens the Flows tab
    THEN the toolbar reads "4 built-in · 0 custom (of 20)" and the zero-custom
        hint is visible.
    """
    _open_flows_tab(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
    )

    expect(page.locator(MDL.FLOWS_COUNT)).to_have_text(_count_text(custom=0))
    expect(page.locator(MDL.FLOWS_HINT)).to_have_text(
        UI_TEST_STRINGS.METRICS_FLOWS_ZERO_CUSTOM_HINT
    )


@VIEWPORTS
def test_flow_delete_escape_returns_focus_to_delete_button(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
    seed_custom_flows: SeedCustomFlows,
    viewport: dict[str, int],
):
    """
    GIVEN a custom flow card
    WHEN the admin opens the delete confirm and presses Escape
    THEN Cancel was focused while open and the Delete button is focused after.
    """
    [flow_id] = seed_custom_flows(display_names=["Escape flow"])
    _open_flows_tab(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
        viewport=viewport,
    )

    card = _custom_card(page, flow_id)
    card.locator(".flow-delete-btn").click()
    expect(card.locator(".flow-cancel-btn")).to_be_focused()
    expect(page.locator(MDL.FLOWS_CONFIRM_GROUP)).to_have_count(1)

    page.keyboard.press("Escape")
    expect(card.locator("[data-flow-confirm]")).to_have_count(0)
    expect(card.locator(".flow-delete-btn")).to_be_focused()


@VIEWPORTS
def test_flow_delete_cancel_click_returns_focus_to_delete_button(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
    seed_custom_flows: SeedCustomFlows,
    viewport: dict[str, int],
):
    """
    GIVEN an open delete confirm on a custom card
    WHEN the admin clicks Cancel
    THEN the confirm closes and the Delete button is focused.
    """
    [flow_id] = seed_custom_flows(display_names=["Cancel flow"])
    _open_flows_tab(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
        viewport=viewport,
    )

    card = _custom_card(page, flow_id)
    card.locator(".flow-delete-btn").click()
    card.locator(".flow-cancel-btn").click()

    expect(card.locator("[data-flow-confirm]")).to_have_count(0)
    expect(card.locator(".flow-delete-btn")).to_be_focused()


@VIEWPORTS
def test_flow_delete_confirm_removes_card_and_updates_toolbar(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
    seed_custom_flows: SeedCustomFlows,
    viewport: dict[str, int],
):
    """
    GIVEN one custom flow (five cards)
    WHEN the admin confirms the delete
    THEN four cards remain, the toolbar returns to the zero-custom text and
        hint, focus moves to the heading and the action announcement names the
        deleted flow.
    """
    [flow_id] = seed_custom_flows(display_names=["Doomed flow"])
    _open_flows_tab(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
        viewport=viewport,
    )
    expect(page.locator(MDL.FLOWS_CARD)).to_have_count(EXPECTED_FLOW_CARD_COUNT + 1)

    card = _custom_card(page, flow_id)
    card.locator(".flow-delete-btn").click()
    card.locator(".flow-confirm-btn").click()

    expect(page.locator(MDL.FLOWS_CARD)).to_have_count(EXPECTED_FLOW_CARD_COUNT)
    expect(page.locator(MDL.FLOWS_COUNT)).to_have_text(_count_text(custom=0))
    expect(page.locator(MDL.FLOWS_HINT)).to_have_text(
        UI_TEST_STRINGS.METRICS_FLOWS_ZERO_CUSTOM_HINT
    )
    expect(page.locator(MDL.FLOWS_HEADING)).to_be_focused()
    expect(page.locator(MDL.FLOWS_ACTION_ANNOUNCEMENT)).to_have_text(
        UI_TEST_STRINGS.METRICS_FLOW_DELETED.format(name="Doomed flow")
    )


def test_flow_needs_attention_card_names_the_failing_step(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
    seed_custom_flows: SeedCustomFlows,
):
    """
    GIVEN a custom flow whose second step names a removed event
    WHEN an admin opens the Flows tab
    THEN its card is a needs-attention card whose accessible name contains
        "Needs attention." and "Step 2:", the glyph and text are visible, and
        there is no Retry button.
    """
    [flow_id] = seed_custom_flows(
        display_names=["Broken flow"], definition=removed_event_definition()
    )
    _open_flows_tab(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
    )

    card = _custom_card(page, flow_id)
    expect(card).to_have_attribute("data-flow-state", "invalid")
    expect(card).to_have_attribute(
        "aria-label",
        re.compile(
            re.escape(UI_TEST_STRINGS.METRICS_FLOW_NEEDS_ATTENTION) + r".*Step 2:"
        ),
    )
    attention = card.locator(".flow-attention")
    expect(attention).to_be_visible()
    expect(attention).to_contain_text(UI_TEST_STRINGS.METRICS_FLOW_NEEDS_ATTENTION)
    expect(attention).to_contain_text("Step 2:")
    glyph_content = attention.evaluate(
        "element => getComputedStyle(element, '::before').content"
    )
    assert "⚠" in glyph_content
    expect(card.locator(".flow-retry-btn")).to_have_count(0)
    expect(page.locator(MDL.FLOWS_CARD)).to_have_count(EXPECTED_FLOW_CARD_COUNT + 1)


def test_flow_level_needs_attention_card_has_no_step_number(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
    seed_custom_flows: SeedCustomFlows,
):
    """
    GIVEN a custom flow with a single step (a flow-level problem)
    WHEN an admin opens the Flows tab
    THEN its needs-attention card shows the reason without a "Step N:" prefix.
    """
    [flow_id] = seed_custom_flows(
        display_names=["Short flow"], definition=one_step_definition()
    )
    _open_flows_tab(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
    )

    card = _custom_card(page, flow_id)
    expect(card).to_have_attribute("data-flow-state", "invalid")
    attention = card.locator(".flow-attention")
    expect(attention).to_contain_text(UI_TEST_STRINGS.METRICS_FLOW_NEEDS_ATTENTION)
    expect(attention).not_to_have_text(re.compile(r"Step \d+:"))
    expect(card).to_have_attribute(
        "aria-label",
        re.compile(re.escape(UI_TEST_STRINGS.METRICS_FLOW_NEEDS_ATTENTION)),
    )
    expect(card).not_to_have_attribute("aria-label", re.compile(r"Step \d+:"))


def test_flows_panel_is_busy_until_cards_load(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
    seed_custom_flows: SeedCustomFlows,
):
    """
    GIVEN `/flow` requests are held
    WHEN an admin opens the Flows tab
    THEN the panel is `aria-busy="true"` while cards load, and after release
        it is no longer busy and the "Flow funnels updated." announcement lands.
    """
    seed_custom_flows(display_names=["Busy flow"])
    held = HeldFlowQueries()
    page.route(FLOW_QUERY_URL_RE, held.handle)
    _open_flows_tab(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
        wait_for_settled=False,
    )

    panel = page.locator(MDL.FLOWS_PANEL)
    expect(panel).to_have_attribute("aria-busy", "true")

    held.release()

    expect(panel).not_to_have_attribute("aria-busy", "true")
    expect(page.locator(MDL.FLOWS_PANEL_ANNOUNCEMENT)).to_have_text(
        UI_TEST_STRINGS.METRICS_FLOWS_LOADED
    )


def test_flows_grid_shows_loading_skeletons_for_queued_cards(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
    seed_custom_flows: SeedCustomFlows,
):
    """
    GIVEN six custom flows (ten cards, more than the four-request cap) and held
        `/flow` responses
    WHEN an admin opens the Flows tab
    THEN every card renders as a loading skeleton (none dropped), and after
        release all ten settle with no skeleton left.
    """
    custom_count = 6
    seed_custom_flows(
        display_names=[f"Queued flow {index}" for index in range(custom_count)]
    )
    held = HeldFlowQueries()
    page.route(FLOW_QUERY_URL_RE, held.handle)
    _open_flows_tab(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
        wait_for_settled=False,
    )

    total = EXPECTED_FLOW_CARD_COUNT + custom_count
    expect(page.locator(MDL.FLOWS_CARD)).to_have_count(total)
    expect(page.locator(MDL.FLOWS_CARD_LOADING)).to_have_count(total)

    held.release()

    expect(page.locator(MDL.FLOWS_CARD_LOADING)).to_have_count(0)
    expect(page.locator(MDL.FLOWS_CARD)).to_have_count(total)


def test_flow_delete_confirm_survives_card_settles(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
    seed_custom_flows: SeedCustomFlows,
):
    """
    GIVEN six custom flows with held `/flow` responses and an open confirm on
        one custom card
    WHEN the held responses are released and the cards re-render
    THEN exactly one confirm is still open and Cancel keeps focus.
    """
    flow_ids = seed_custom_flows(
        display_names=[f"Settle flow {index}" for index in range(6)]
    )
    held = HeldFlowQueries()
    page.route(FLOW_QUERY_URL_RE, held.handle)
    _open_flows_tab(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
        wait_for_settled=False,
    )

    card = _custom_card(page, flow_ids[0])
    card.locator(".flow-delete-btn").click()
    expect(card.locator(".flow-cancel-btn")).to_be_focused()

    held.release()

    expect(page.locator(MDL.FLOWS_CARD_LOADING)).to_have_count(0)
    expect(page.locator(MDL.FLOWS_CONFIRM_GROUP)).to_have_count(1)
    expect(card.locator(".flow-cancel-btn")).to_be_focused()


def test_flow_delete_404_shows_already_deleted_notice(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
    seed_custom_flows: SeedCustomFlows,
):
    """
    GIVEN another admin has already deleted the flow (DELETE answers 404)
    WHEN the admin confirms the delete
    THEN the card disappears and the already-deleted notice is shown.
    """
    [flow_id] = seed_custom_flows(display_names=["Gone flow"])

    def _answer_404(route: Route) -> None:
        if route.request.method != "DELETE":
            route.fallback()
            return
        _delete_other_admin(app=provide_app, flow_id=flow_id)
        route.fulfill(
            status=404,
            content_type="application/json",
            body='{"status": "Failure", "message": "Not found"}',
        )

    page.route(FLOW_DELETE_URL_RE, _answer_404)
    _open_flows_tab(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
    )

    card = _custom_card(page, flow_id)
    card.locator(".flow-delete-btn").click()
    card.locator(".flow-confirm-btn").click()

    expect(page.locator(MDL.FLOWS_NOTICE)).to_have_text(
        UI_TEST_STRINGS.METRICS_FLOW_ALREADY_DELETED.format(name="Gone flow")
    )
    expect(page.locator(MDL.FLOWS_CARD)).to_have_count(EXPECTED_FLOW_CARD_COUNT)


def test_flows_list_429_falls_back_to_built_ins_with_list_error(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
    seed_custom_flows: SeedCustomFlows,
):
    """
    GIVEN the flow list endpoint answers 429 with a JSON body
    WHEN an admin opens the Flows tab
    THEN the four built-ins render, the error banner and the inline list error
        show, and the page is not replaced.
    """
    seed_custom_flows(display_names=["Hidden flow"])

    def _rate_limit_list(route: Route) -> None:
        if route.request.method != "GET":
            route.fallback()
            return
        route.fulfill(
            status=429,
            content_type="application/json",
            body='{"status": "Failure", "message": "Too many requests"}',
        )

    page.route(FLOW_LIST_URL_RE, _rate_limit_list)
    _open_flows_tab(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
    )

    expect(page.locator(MDL.FLOWS_CARD)).to_have_count(EXPECTED_FLOW_CARD_COUNT)
    expect(page.locator(MDL.FLOWS_LIST_ERROR)).to_contain_text(
        UI_TEST_STRINGS.METRICS_FLOWS_LIST_FAILED
    )
    expect(page.locator(MDL.ERROR_BANNER)).to_be_visible()
    expect(page.locator(MDL.DASHBOARD_ROOT)).to_be_visible()


def test_flow_delete_controls_meet_touch_target_and_fit_at_420px(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
    seed_custom_flows: SeedCustomFlows,
):
    """
    GIVEN a custom flow with a 64-character name at a 420px viewport
    WHEN the admin opens the delete confirm
    THEN Delete, Confirm and Cancel are each at least 44x44 and the card does
        not overflow horizontally.
    """
    [flow_id] = seed_custom_flows(display_names=[LONG_FLOW_NAME])
    _open_flows_tab(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
        viewport=MOBILE_VIEWPORT,
    )

    # Cards are rebuilt when their funnel settles; measure only after that.
    expect(page.locator(MDL.FLOWS_CARD_LOADING)).to_have_count(0)
    card = _custom_card(page, flow_id)
    delete_button = card.locator(".flow-delete-btn")
    expect(delete_button).to_be_visible()
    delete_box = delete_button.bounding_box()
    assert delete_box is not None
    assert delete_box["width"] >= MIN_TOUCH_TARGET_PX
    assert delete_box["height"] >= MIN_TOUCH_TARGET_PX

    delete_button.click()
    confirm_button = card.locator(".flow-confirm-btn")
    cancel_button = card.locator(".flow-cancel-btn")
    expect(confirm_button).to_be_visible()
    for button in (confirm_button, cancel_button):
        box = button.bounding_box()
        assert box is not None
        assert box["width"] >= MIN_TOUCH_TARGET_PX, box
        assert box["height"] >= MIN_TOUCH_TARGET_PX, box

    overflow = card.evaluate("el => el.scrollWidth - el.clientWidth")
    assert overflow <= 1, f"Card overflows horizontally by {overflow}px."


def test_already_deleted_notice_fits_viewport_at_420px(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
    seed_custom_flows: SeedCustomFlows,
):
    """
    GIVEN a 64-character flow name that another admin already deleted, at 420px
    WHEN the admin confirms the delete and the notice appears
    THEN the toolbar and notice stay within the viewport width.
    """
    [flow_id] = seed_custom_flows(display_names=[LONG_FLOW_NAME])

    def _answer_404(route: Route) -> None:
        if route.request.method != "DELETE":
            route.fallback()
            return
        _delete_other_admin(app=provide_app, flow_id=flow_id)
        route.fulfill(
            status=404,
            content_type="application/json",
            body='{"status": "Failure", "message": "Not found"}',
        )

    page.route(FLOW_DELETE_URL_RE, _answer_404)
    _open_flows_tab(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
        viewport=MOBILE_VIEWPORT,
    )

    card = _custom_card(page, flow_id)
    card.locator(".flow-delete-btn").click()
    card.locator(".flow-confirm-btn").click()

    notice = page.locator(MDL.FLOWS_NOTICE)
    expect(notice).to_be_visible()
    viewport_width = MOBILE_VIEWPORT["width"]
    expect(page.locator(MDL.FLOWS_CARD)).to_have_count(EXPECTED_FLOW_CARD_COUNT)
    for selector in (MDL.FLOWS_NOTICE, MDL.FLOWS_TOOLBAR):
        box = page.locator(selector).bounding_box()
        assert box is not None
        assert box["x"] + box["width"] <= viewport_width + 1, (selector, box)
    page_overflow = page.evaluate(
        "() => document.documentElement.scrollWidth - window.innerWidth"
    )
    assert page_overflow <= 1, f"Page overflows horizontally by {page_overflow}px."
