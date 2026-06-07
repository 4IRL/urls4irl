/**
 * Window-selector behavior for the admin metrics dashboard controller.
 *
 * Clicking a window button (Day/Week/Month/Year) must:
 *   1. Flip `aria-pressed="true"` on the clicked button and `"false"` on the
 *      other three.
 *   2. Trigger a refetch against the new window value (visible as a fresh
 *      `fetchSummary({ window: "<new>" })` call).
 */

const {
  fetchSummarySpy,
  fetchTopEventsSpy,
  renderSummarySpy,
  renderTopTableSpy,
} = vi.hoisted(() => ({
  fetchSummarySpy: vi.fn(),
  fetchTopEventsSpy: vi.fn(),
  renderSummarySpy: vi.fn(),
  renderTopTableSpy: vi.fn(),
}));

vi.mock("../metrics-query-client.js", () => ({
  fetchSummary: fetchSummarySpy,
  fetchTopEvents: fetchTopEventsSpy,
  fetchTimeseries: vi.fn(),
}));

vi.mock("../render-summary.js", () => ({
  renderSummary: renderSummarySpy,
}));

vi.mock("../render-top-table.js", () => ({
  renderTopTable: renderTopTableSpy,
}));

import {
  _resetMetricsDashboardForTests,
  initMetricsDashboard,
} from "../metrics-dashboard.js";

const DASHBOARD_HTML = `
  <main id="MetricsDashboard" aria-busy="false">
    <button id="MetricsRefreshNowBtn" type="button"></button>
    <button id="MetricsWindowDay"   class="MetricsWindowButton" data-window="day"   aria-pressed="true"></button>
    <button id="MetricsWindowWeek"  class="MetricsWindowButton" data-window="week"  aria-pressed="false"></button>
    <button id="MetricsWindowMonth" class="MetricsWindowButton" data-window="month" aria-pressed="false"></button>
    <button id="MetricsWindowYear"  class="MetricsWindowButton" data-window="year"  aria-pressed="false"></button>
    <section id="MetricsPanelApi">
      <div id="MetricsPanelApi-summary"></div>
      <table id="MetricsTopTableApi"><tbody></tbody></table>
    </section>
    <section id="MetricsPanelUi">
      <div id="MetricsPanelUi-summary"></div>
      <table id="MetricsTopTableUi"><tbody></tbody></table>
    </section>
    <section id="MetricsPanelDomain">
      <div id="MetricsPanelDomain-summary"></div>
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

describe("metrics-dashboard window-selector", () => {
  beforeEach(() => {
    document.body.innerHTML = DASHBOARD_HTML;
    Object.defineProperty(document, "visibilityState", {
      value: "visible",
      configurable: true,
    });

    fetchSummarySpy.mockReset();
    fetchTopEventsSpy.mockReset();
    renderSummarySpy.mockReset();
    renderTopTableSpy.mockReset();

    fetchSummarySpy.mockImplementation(() => makeNoopXhr());
    fetchTopEventsSpy.mockImplementation(() => makeNoopXhr());

    vi.useFakeTimers();
  });

  afterEach(() => {
    _resetMetricsDashboardForTests();
    vi.useRealTimers();
    document.body.innerHTML = "";
  });

  it("clicking a window button updates aria-pressed and refetches with the new window", () => {
    initMetricsDashboard();

    // Initial fetch on init runs against the default window.
    expect(fetchSummarySpy).toHaveBeenCalledTimes(1);
    expect(fetchSummarySpy.mock.calls[0][0]).toEqual({ window: "day" });

    const dayButton = document.getElementById(
      "MetricsWindowDay",
    ) as HTMLButtonElement;
    const weekButton = document.getElementById(
      "MetricsWindowWeek",
    ) as HTMLButtonElement;
    const monthButton = document.getElementById(
      "MetricsWindowMonth",
    ) as HTMLButtonElement;
    const yearButton = document.getElementById(
      "MetricsWindowYear",
    ) as HTMLButtonElement;

    weekButton.click();

    expect(dayButton.getAttribute("aria-pressed")).toBe("false");
    expect(weekButton.getAttribute("aria-pressed")).toBe("true");
    expect(monthButton.getAttribute("aria-pressed")).toBe("false");
    expect(yearButton.getAttribute("aria-pressed")).toBe("false");

    expect(fetchSummarySpy).toHaveBeenCalledTimes(2);
    expect(fetchSummarySpy.mock.calls[1][0]).toEqual({ window: "week" });

    // Top-events refetched per category with the new window value too.
    const topCallsAfterWeekClick = fetchTopEventsSpy.mock.calls.slice(3);
    expect(topCallsAfterWeekClick).toHaveLength(3);
    for (const topCallArgs of topCallsAfterWeekClick) {
      expect(topCallArgs[0].window).toBe("week");
    }
  });
});
