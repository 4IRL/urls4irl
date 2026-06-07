/**
 * Section-tabs ARIA behavior for the admin metrics dashboard controller.
 *
 * Covers the ARIA Authoring Practices Guide tablist pattern:
 *   - Clicking a tab updates `aria-selected` and the roving `tabindex`.
 *   - Arrow keys cycle through tabs (wrap-around at the ends).
 *   - Home / End jump to the first / last tab.
 *   - The `hidden` attribute on each tabpanel toggles in sync with selection.
 *
 * Query-client and render modules are fully mocked so each spec exercises
 * only the tablist state machine — no real fetches, no DOM rendering noise.
 */

const {
  fetchSummarySpy,
  fetchTopEventsSpy,
  fetchTimeseriesSpy,
  renderSummarySpy,
  renderTopTableSpy,
  renderTimeseriesChartSpy,
} = vi.hoisted(() => ({
  fetchSummarySpy: vi.fn(),
  fetchTopEventsSpy: vi.fn(),
  fetchTimeseriesSpy: vi.fn(),
  renderSummarySpy: vi.fn(),
  renderTopTableSpy: vi.fn(),
  renderTimeseriesChartSpy: vi.fn(),
}));

vi.mock("../metrics-query-client.js", () => ({
  fetchSummary: fetchSummarySpy,
  fetchTopEvents: fetchTopEventsSpy,
  fetchTimeseries: fetchTimeseriesSpy,
}));

vi.mock("../render-summary.js", () => ({
  renderSummary: renderSummarySpy,
}));

vi.mock("../render-top-table.js", () => ({
  renderTopTable: renderTopTableSpy,
}));

vi.mock("../render-timeseries-chart.js", () => ({
  renderTimeseriesChart: renderTimeseriesChartSpy,
}));

import { $ } from "../../lib/globals.js";
import {
  _resetMetricsDashboardForTests,
  initMetricsDashboard,
} from "../metrics-dashboard.js";

type TabId = "MetricsTabApi" | "MetricsTabUi" | "MetricsTabDomain";
type PanelId = "MetricsPanelApi" | "MetricsPanelUi" | "MetricsPanelDomain";

const DASHBOARD_HTML = `
  <main id="MetricsDashboard" aria-busy="false">
    <button id="MetricsRefreshNowBtn" type="button"></button>
    <button class="MetricsWindowButton" data-window="day" aria-pressed="true"></button>
    <button class="MetricsWindowButton" data-window="week" aria-pressed="false"></button>
    <button class="MetricsWindowButton" data-window="month" aria-pressed="false"></button>
    <button class="MetricsWindowButton" data-window="year" aria-pressed="false"></button>
    <div id="MetricsTablist" role="tablist">
      <button id="MetricsTabApi"    role="tab" aria-selected="true"  aria-controls="MetricsPanelApi"    tabindex="0"  data-category="api"></button>
      <button id="MetricsTabUi"     role="tab" aria-selected="false" aria-controls="MetricsPanelUi"     tabindex="-1" data-category="ui"></button>
      <button id="MetricsTabDomain" role="tab" aria-selected="false" aria-controls="MetricsPanelDomain" tabindex="-1" data-category="domain"></button>
    </div>
    <section id="MetricsPanelApi" role="tabpanel" tabindex="0">
      <div id="MetricsPanelApi-summary"></div>
      <select id="MetricsTimeseriesEventApi"></select>
      <table id="MetricsTopTableApi"><tbody></tbody></table>
    </section>
    <section id="MetricsPanelUi" role="tabpanel" tabindex="0" hidden>
      <div id="MetricsPanelUi-summary"></div>
      <select id="MetricsTimeseriesEventUi"></select>
      <table id="MetricsTopTableUi"><tbody></tbody></table>
    </section>
    <section id="MetricsPanelDomain" role="tabpanel" tabindex="0" hidden>
      <div id="MetricsPanelDomain-summary"></div>
      <select id="MetricsTimeseriesEventDomain"></select>
      <table id="MetricsTopTableDomain"><tbody></tbody></table>
    </section>
    <div id="MetricsErrorBanner" class="hidden"></div>
  </main>
`;

function makeNoopXhr(): JQuery.jqXHR {
  const chainable = {
    done: vi.fn().mockReturnThis(),
    fail: vi.fn().mockReturnThis(),
    always: vi.fn().mockReturnThis(),
    abort: vi.fn(),
  };
  return chainable as unknown as JQuery.jqXHR;
}

function getTab(tabId: TabId): HTMLButtonElement {
  return document.getElementById(tabId) as HTMLButtonElement;
}

function getPanel(panelId: PanelId): HTMLElement {
  return document.getElementById(panelId) as HTMLElement;
}

describe("metrics-dashboard tablist a11y", () => {
  beforeEach(() => {
    document.body.innerHTML = DASHBOARD_HTML;
    Object.defineProperty(document, "visibilityState", {
      value: "visible",
      configurable: true,
    });

    fetchSummarySpy.mockReset();
    fetchTopEventsSpy.mockReset();
    fetchTimeseriesSpy.mockReset();
    renderSummarySpy.mockReset();
    renderTopTableSpy.mockReset();
    renderTimeseriesChartSpy.mockReset();

    fetchSummarySpy.mockImplementation(() => makeNoopXhr());
    fetchTopEventsSpy.mockImplementation(() => makeNoopXhr());
    fetchTimeseriesSpy.mockImplementation(() => makeNoopXhr());

    vi.useFakeTimers();
    initMetricsDashboard();
  });

  afterEach(() => {
    _resetMetricsDashboardForTests();
    vi.useRealTimers();
    document.body.innerHTML = "";
  });

  it("clicking a tab updates aria-selected and roving tabindex", () => {
    expect(getTab("MetricsTabApi").getAttribute("aria-selected")).toBe("true");
    expect(getTab("MetricsTabApi").getAttribute("tabindex")).toBe("0");
    expect(getTab("MetricsTabUi").getAttribute("aria-selected")).toBe("false");
    expect(getTab("MetricsTabUi").getAttribute("tabindex")).toBe("-1");

    getTab("MetricsTabUi").click();

    expect(getTab("MetricsTabApi").getAttribute("aria-selected")).toBe("false");
    expect(getTab("MetricsTabApi").getAttribute("tabindex")).toBe("-1");
    expect(getTab("MetricsTabUi").getAttribute("aria-selected")).toBe("true");
    expect(getTab("MetricsTabUi").getAttribute("tabindex")).toBe("0");
    expect(getTab("MetricsTabDomain").getAttribute("aria-selected")).toBe(
      "false",
    );
    expect(getTab("MetricsTabDomain").getAttribute("tabindex")).toBe("-1");
  });

  it("ArrowRight on the active tab moves focus to the next tab", () => {
    getTab("MetricsTabApi").focus();
    $("#MetricsTabApi").trigger($.Event("keydown", { key: "ArrowRight" }));

    expect(getTab("MetricsTabUi").getAttribute("aria-selected")).toBe("true");
    expect(getTab("MetricsTabUi").getAttribute("tabindex")).toBe("0");
    expect(document.activeElement).toBe(getTab("MetricsTabUi"));
  });

  it("ArrowLeft on the first tab wraps to the last", () => {
    getTab("MetricsTabApi").focus();
    $("#MetricsTabApi").trigger($.Event("keydown", { key: "ArrowLeft" }));

    expect(getTab("MetricsTabDomain").getAttribute("aria-selected")).toBe(
      "true",
    );
    expect(getTab("MetricsTabDomain").getAttribute("tabindex")).toBe("0");
    expect(document.activeElement).toBe(getTab("MetricsTabDomain"));
  });

  it("Home key activates the first tab", () => {
    // Start with the Domain tab active so Home has work to do.
    getTab("MetricsTabDomain").click();
    expect(getTab("MetricsTabDomain").getAttribute("aria-selected")).toBe(
      "true",
    );

    getTab("MetricsTabDomain").focus();
    $("#MetricsTabDomain").trigger($.Event("keydown", { key: "Home" }));

    expect(getTab("MetricsTabApi").getAttribute("aria-selected")).toBe("true");
    expect(getTab("MetricsTabApi").getAttribute("tabindex")).toBe("0");
    expect(document.activeElement).toBe(getTab("MetricsTabApi"));
  });

  it("End key activates the last tab", () => {
    getTab("MetricsTabApi").focus();
    $("#MetricsTabApi").trigger($.Event("keydown", { key: "End" }));

    expect(getTab("MetricsTabDomain").getAttribute("aria-selected")).toBe(
      "true",
    );
    expect(getTab("MetricsTabDomain").getAttribute("tabindex")).toBe("0");
    expect(document.activeElement).toBe(getTab("MetricsTabDomain"));
  });

  it("hidden attribute toggles on tabpanels in sync with selection", () => {
    expect(getPanel("MetricsPanelApi").hasAttribute("hidden")).toBe(false);
    expect(getPanel("MetricsPanelUi").hasAttribute("hidden")).toBe(true);
    expect(getPanel("MetricsPanelDomain").hasAttribute("hidden")).toBe(true);

    getTab("MetricsTabUi").click();

    expect(getPanel("MetricsPanelApi").hasAttribute("hidden")).toBe(true);
    expect(getPanel("MetricsPanelUi").hasAttribute("hidden")).toBe(false);
    expect(getPanel("MetricsPanelDomain").hasAttribute("hidden")).toBe(true);

    getTab("MetricsTabDomain").click();

    expect(getPanel("MetricsPanelApi").hasAttribute("hidden")).toBe(true);
    expect(getPanel("MetricsPanelUi").hasAttribute("hidden")).toBe(true);
    expect(getPanel("MetricsPanelDomain").hasAttribute("hidden")).toBe(false);
  });

  it("changing the per-panel select fires fetchTimeseries with the chosen event", () => {
    const selectElement = document.getElementById(
      "MetricsTimeseriesEventApi",
    ) as HTMLSelectElement;
    const option = document.createElement("option");
    option.value = "utub_opened";
    option.textContent = "utub_opened";
    selectElement.appendChild(option);
    selectElement.value = "utub_opened";

    $("#MetricsTimeseriesEventApi").trigger(
      "change.metricsDashboardTimeseries",
    );

    expect(fetchTimeseriesSpy).toHaveBeenCalledTimes(1);
    expect(fetchTimeseriesSpy.mock.calls[0][0]).toEqual({
      eventName: "utub_opened",
      window: "day",
      resolution: "hour",
    });
  });
});
