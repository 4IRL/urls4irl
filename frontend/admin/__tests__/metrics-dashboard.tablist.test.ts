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
  fetchGroupedTimeseriesSpy,
  fetchFlowSpy,
  renderSummarySpy,
  renderTopTableSpy,
  renderTimeseriesChartSpy,
  renderFlowGridSpy,
} = vi.hoisted(() => ({
  fetchSummarySpy: vi.fn(),
  fetchTopEventsSpy: vi.fn(),
  fetchTimeseriesSpy: vi.fn(),
  fetchGroupedTimeseriesSpy: vi.fn(),
  fetchFlowSpy: vi.fn(),
  renderSummarySpy: vi.fn(),
  renderTopTableSpy: vi.fn(),
  renderTimeseriesChartSpy: vi.fn(),
  renderFlowGridSpy: vi.fn(),
}));

vi.mock("../metrics-query-client.js", () => ({
  fetchSummary: fetchSummarySpy,
  fetchTopEvents: fetchTopEventsSpy,
  fetchTimeseries: fetchTimeseriesSpy,
  fetchGroupedTimeseries: fetchGroupedTimeseriesSpy,
  fetchFlow: fetchFlowSpy,
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

vi.mock("../flow-card.js", () => ({
  renderFlowGrid: renderFlowGridSpy,
}));

import { createMockJqXHRChainable } from "../../__tests__/helpers/mock-jquery.js";
import { $ } from "../../lib/globals.js";
import {
  _resetMetricsDashboardForTests,
  initMetricsDashboard,
} from "../metrics-dashboard.js";

type TabId =
  | "MetricsTabApi"
  | "MetricsTabUi"
  | "MetricsTabDomain"
  | "MetricsTabPipelineHealth"
  | "MetricsTabFlows";
type PanelId =
  | "MetricsPanelApi"
  | "MetricsPanelUi"
  | "MetricsPanelDomain"
  | "MetricsPanelPipelineHealth"
  | "MetricsPanelFlows";

const DASHBOARD_HTML = `
  <main id="MetricsDashboard" aria-busy="false">
    <button id="MetricsRefreshNowBtn" type="button"></button>
    <button class="MetricsWindowButton" data-window="day" aria-pressed="true"></button>
    <button class="MetricsWindowButton" data-window="week" aria-pressed="false"></button>
    <button class="MetricsWindowButton" data-window="month" aria-pressed="false"></button>
    <button class="MetricsWindowButton" data-window="year" aria-pressed="false"></button>
    <div id="MetricsTablist" role="tablist">
      <button id="MetricsTabApi"            role="tab" aria-selected="true"  aria-controls="MetricsPanelApi"            tabindex="0"  data-tab="api"></button>
      <button id="MetricsTabUi"             role="tab" aria-selected="false" aria-controls="MetricsPanelUi"             tabindex="-1" data-tab="ui"></button>
      <button id="MetricsTabDomain"         role="tab" aria-selected="false" aria-controls="MetricsPanelDomain"         tabindex="-1" data-tab="domain"></button>
      <button id="MetricsTabFlows"          role="tab" aria-selected="false" aria-controls="MetricsPanelFlows"          tabindex="-1" data-tab="flows"></button>
      <button id="MetricsTabPipelineHealth" role="tab" aria-selected="false" aria-controls="MetricsPanelPipelineHealth" tabindex="-1" data-tab="pipeline_health"></button>
    </div>
    <section id="MetricsSummary"><div id="MetricsSummaryGrid"></div></section>
    <section id="MetricsPanelApi" role="tabpanel" tabindex="0">
      <select id="MetricsTimeseriesEventApi"></select>
      <table id="MetricsTopTableApi"><tbody></tbody></table>
    </section>
    <section id="MetricsPanelUi" role="tabpanel" tabindex="0" hidden>
      <select id="MetricsTimeseriesEventUi"></select>
      <table id="MetricsTopTableUi"><tbody></tbody></table>
    </section>
    <section id="MetricsPanelDomain" role="tabpanel" tabindex="0" hidden>
      <select id="MetricsTimeseriesEventDomain"></select>
      <table id="MetricsTopTableDomain"><tbody></tbody></table>
    </section>
    <section id="MetricsPanelFlows" role="tabpanel" tabindex="0" hidden>
      <span class="flows-loading-spinner" aria-hidden="true"></span>
      <span id="MetricsPanelFlowsAnnouncement" class="visually-hidden" aria-live="polite"></span>
      <div id="MetricsFlowGrid" class="flow-grid"></div>
    </section>
    <section id="MetricsPanelPipelineHealth" role="tabpanel" tabindex="0" hidden></section>
    <div id="MetricsErrorBanner" class="hidden"></div>
  </main>
`;

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
    fetchGroupedTimeseriesSpy.mockReset();
    fetchFlowSpy.mockReset();
    renderSummarySpy.mockReset();
    renderTopTableSpy.mockReset();
    renderTimeseriesChartSpy.mockReset();
    renderFlowGridSpy.mockReset();

    fetchSummarySpy.mockImplementation(() => createMockJqXHRChainable());
    fetchTopEventsSpy.mockImplementation(() => createMockJqXHRChainable());
    fetchTimeseriesSpy.mockImplementation(() => createMockJqXHRChainable());
    fetchGroupedTimeseriesSpy.mockImplementation(() =>
      createMockJqXHRChainable(),
    );
    fetchFlowSpy.mockImplementation(() => createMockJqXHRChainable());

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

    expect(
      getTab("MetricsTabPipelineHealth").getAttribute("aria-selected"),
    ).toBe("true");
    expect(getTab("MetricsTabPipelineHealth").getAttribute("tabindex")).toBe(
      "0",
    );
    expect(document.activeElement).toBe(getTab("MetricsTabPipelineHealth"));
  });

  it("ArrowRight from Flows moves to Pipeline Health", () => {
    getTab("MetricsTabFlows").click();
    getTab("MetricsTabFlows").focus();
    $("#MetricsTabFlows").trigger($.Event("keydown", { key: "ArrowRight" }));

    expect(
      getTab("MetricsTabPipelineHealth").getAttribute("aria-selected"),
    ).toBe("true");
    expect(getTab("MetricsTabPipelineHealth").getAttribute("tabindex")).toBe(
      "0",
    );
    expect(document.activeElement).toBe(getTab("MetricsTabPipelineHealth"));
  });

  it("Home key activates the first tab", () => {
    // Start with the last tab active so Home has work to do.
    getTab("MetricsTabPipelineHealth").click();
    expect(
      getTab("MetricsTabPipelineHealth").getAttribute("aria-selected"),
    ).toBe("true");

    getTab("MetricsTabPipelineHealth").focus();
    $("#MetricsTabPipelineHealth").trigger($.Event("keydown", { key: "Home" }));

    expect(getTab("MetricsTabApi").getAttribute("aria-selected")).toBe("true");
    expect(getTab("MetricsTabApi").getAttribute("tabindex")).toBe("0");
    expect(document.activeElement).toBe(getTab("MetricsTabApi"));
  });

  it("End key activates the last tab", () => {
    getTab("MetricsTabApi").focus();
    $("#MetricsTabApi").trigger($.Event("keydown", { key: "End" }));

    expect(
      getTab("MetricsTabPipelineHealth").getAttribute("aria-selected"),
    ).toBe("true");
    expect(getTab("MetricsTabPipelineHealth").getAttribute("tabindex")).toBe(
      "0",
    );
    expect(document.activeElement).toBe(getTab("MetricsTabPipelineHealth"));
  });

  it("ArrowRight on the last tab wraps to the first", () => {
    getTab("MetricsTabPipelineHealth").click();
    getTab("MetricsTabPipelineHealth").focus();
    $("#MetricsTabPipelineHealth").trigger(
      $.Event("keydown", { key: "ArrowRight" }),
    );

    expect(getTab("MetricsTabApi").getAttribute("aria-selected")).toBe("true");
    expect(getTab("MetricsTabApi").getAttribute("tabindex")).toBe("0");
    expect(document.activeElement).toBe(getTab("MetricsTabApi"));
  });

  it("hidden attribute toggles on tabpanels in sync with selection", () => {
    expect(getPanel("MetricsPanelApi").hasAttribute("hidden")).toBe(false);
    expect(getPanel("MetricsPanelUi").hasAttribute("hidden")).toBe(true);
    expect(getPanel("MetricsPanelDomain").hasAttribute("hidden")).toBe(true);
    expect(getPanel("MetricsPanelPipelineHealth").hasAttribute("hidden")).toBe(
      true,
    );
    expect(getPanel("MetricsPanelFlows").hasAttribute("hidden")).toBe(true);

    getTab("MetricsTabUi").click();

    expect(getPanel("MetricsPanelApi").hasAttribute("hidden")).toBe(true);
    expect(getPanel("MetricsPanelUi").hasAttribute("hidden")).toBe(false);
    expect(getPanel("MetricsPanelDomain").hasAttribute("hidden")).toBe(true);
    expect(getPanel("MetricsPanelPipelineHealth").hasAttribute("hidden")).toBe(
      true,
    );
    expect(getPanel("MetricsPanelFlows").hasAttribute("hidden")).toBe(true);

    getTab("MetricsTabFlows").click();

    expect(getPanel("MetricsPanelApi").hasAttribute("hidden")).toBe(true);
    expect(getPanel("MetricsPanelUi").hasAttribute("hidden")).toBe(true);
    expect(getPanel("MetricsPanelDomain").hasAttribute("hidden")).toBe(true);
    expect(getPanel("MetricsPanelPipelineHealth").hasAttribute("hidden")).toBe(
      true,
    );
    expect(getPanel("MetricsPanelFlows").hasAttribute("hidden")).toBe(false);
  });

  it("activating the Flows tab fires the per-flow fan-out on first load", () => {
    expect(fetchFlowSpy).not.toHaveBeenCalled();

    getTab("MetricsTabFlows").click();

    // One XHR per FlowId (create_utub, add_url_to_utub, register, login).
    expect(fetchFlowSpy).toHaveBeenCalledTimes(4);
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
      endpoint: undefined,
      method: undefined,
      deviceType: null,
    });
  });

  it("rapidly changing the per-panel select aborts the previous in-flight timeseries request", () => {
    const selectElement = document.getElementById(
      "MetricsTimeseriesEventApi",
    ) as HTMLSelectElement;
    const firstOption = document.createElement("option");
    firstOption.value = "utub_opened";
    firstOption.textContent = "utub_opened";
    selectElement.appendChild(firstOption);
    const secondOption = document.createElement("option");
    secondOption.value = "url_added";
    secondOption.textContent = "url_added";
    selectElement.appendChild(secondOption);

    const firstXhr = createMockJqXHRChainable();
    const secondXhr = createMockJqXHRChainable();
    fetchTimeseriesSpy
      .mockImplementationOnce(() => firstXhr)
      .mockImplementationOnce(() => secondXhr);

    selectElement.value = "utub_opened";
    $("#MetricsTimeseriesEventApi").trigger(
      "change.metricsDashboardTimeseries",
    );
    expect(firstXhr.abort).not.toHaveBeenCalled();

    selectElement.value = "url_added";
    $("#MetricsTimeseriesEventApi").trigger(
      "change.metricsDashboardTimeseries",
    );

    expect(firstXhr.abort).toHaveBeenCalledTimes(1);
    expect(secondXhr.abort).not.toHaveBeenCalled();
  });

  it("handleTimeseriesSelectChange .fail with non-0, non-429 status shows the error banner", () => {
    const selectElement = document.getElementById(
      "MetricsTimeseriesEventApi",
    ) as HTMLSelectElement;
    const option = document.createElement("option");
    option.value = "utub_opened";
    option.textContent = "utub_opened";
    selectElement.appendChild(option);
    selectElement.value = "utub_opened";

    const failingXhr = createMockJqXHRChainable({
      fail: (cb: unknown) => {
        const failureXhr = {
          readyState: 4,
          status: 500,
        } as unknown as JQuery.jqXHR;
        (cb as (xhr: JQuery.jqXHR) => void)(failureXhr);
      },
    });
    fetchTimeseriesSpy.mockImplementation(() => failingXhr);

    $("#MetricsTimeseriesEventApi").trigger(
      "change.metricsDashboardTimeseries",
    );

    const banner = document.getElementById("MetricsErrorBanner") as HTMLElement;
    expect(banner.classList.contains("hidden")).toBe(false);
  });
});
