/**
 * Row-click + keyboard activation behavior for the admin metrics dashboard.
 *
 * Covers:
 *   - Clicking a Top Endpoints row drives the same fetchTimeseries pipeline
 *     as picking from the per-panel <select>.
 *   - Enter / Space on a focused row activate the same path.
 *   - Empty-state rows and click targets outside event rows are ignored.
 *   - API category click forwards endpoint + method dataset metadata so the
 *     server-side filter applies (the select option carries that metadata).
 *
 * The render-top-table.js module is intentionally NOT mocked here so real
 * rows (with the new data-event-name, tabindex, aria-label) are built and
 * the click handlers exercise actual DOM bubbling.
 */

const {
  fetchSummarySpy,
  fetchTopEventsSpy,
  fetchTimeseriesSpy,
  renderSummarySpy,
  renderTimeseriesChartSpy,
} = vi.hoisted(() => ({
  fetchSummarySpy: vi.fn(),
  fetchTopEventsSpy: vi.fn(),
  fetchTimeseriesSpy: vi.fn(),
  renderSummarySpy: vi.fn(),
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

vi.mock("../render-timeseries-chart.js", () => ({
  renderTimeseriesChart: renderTimeseriesChartSpy,
}));

import { createMockJqXHRChainable } from "../../__tests__/helpers/mock-jquery.js";
import { $ } from "../../lib/globals.js";
import {
  _resetMetricsDashboardForTests,
  initMetricsDashboard,
} from "../metrics-dashboard.js";

const DASHBOARD_HTML = `
  <main id="MetricsDashboard" aria-busy="false">
    <button id="MetricsRefreshNowBtn" type="button"></button>
    <span id="MetricsLastFlush"><span id="MetricsLastFlushText"></span></span>
    <span id="MetricsLastFlushAnnouncement"></span>
    <button class="MetricsWindowButton" data-window="day" aria-pressed="true"></button>
    <button class="MetricsWindowButton" data-window="week" aria-pressed="false"></button>
    <button class="MetricsWindowButton" data-window="month" aria-pressed="false"></button>
    <button class="MetricsWindowButton" data-window="year" aria-pressed="false"></button>
    <div id="MetricsTablist" role="tablist">
      <button id="MetricsTabApi"    role="tab" aria-selected="true"  data-category="api"></button>
      <button id="MetricsTabUi"     role="tab" aria-selected="false" data-category="ui"></button>
      <button id="MetricsTabDomain" role="tab" aria-selected="false" data-category="domain"></button>
    </div>
    <section id="MetricsSummary"><div id="MetricsSummaryGrid"></div></section>
    <section id="MetricsPanelApi" role="tabpanel" tabindex="0">
      <select id="MetricsTimeseriesEventApi"></select>
      <table id="MetricsTopTableApi" class="top-table"><thead></thead><tbody></tbody></table>
    </section>
    <section id="MetricsPanelUi" role="tabpanel" tabindex="0" hidden>
      <select id="MetricsTimeseriesEventUi"></select>
      <table id="MetricsTopTableUi" class="top-table"><thead></thead><tbody></tbody></table>
    </section>
    <section id="MetricsPanelDomain" role="tabpanel" tabindex="0" hidden>
      <select id="MetricsTimeseriesEventDomain"></select>
      <table id="MetricsTopTableDomain" class="top-table"><thead></thead><tbody></tbody></table>
    </section>
    <div id="MetricsErrorBanner" class="hidden"></div>
  </main>
`;

interface MockTopEvent {
  event_name: string;
  category: "api" | "ui" | "domain";
  description: string;
  total_count: number;
  previous_count: number;
}

function makeTopEventsResponse(events: MockTopEvent[]): {
  window: string;
  category: string;
  events: MockTopEvent[];
} {
  return { window: "day", category: events[0]?.category ?? "ui", events };
}

function primeUiPanelWithEvents(events: MockTopEvent[]): void {
  fetchTopEventsSpy.mockImplementation(
    ({ category }: { category: "api" | "ui" | "domain" }) => {
      const matching = category === "ui" ? events : [];
      return createMockJqXHRChainable({
        done: (cb: unknown) => {
          (cb as (response: unknown) => void)(makeTopEventsResponse(matching));
        },
      });
    },
  );
  initMetricsDashboard();
  // The dashboard now auto-selects the highest-ranked event on initial load
  // and fires a timeseries fetch. Tests that assert click/keyboard-driven
  // fetches need a clean spy state, so consume the auto-fetch here.
  fetchTimeseriesSpy.mockClear();
}

function getUiPanelTbody(): HTMLTableSectionElement {
  return document.querySelector(
    "#MetricsTopTableUi tbody",
  ) as HTMLTableSectionElement;
}

describe("metrics-dashboard top-table row clicks", () => {
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
    renderTimeseriesChartSpy.mockReset();

    fetchSummarySpy.mockImplementation(() => createMockJqXHRChainable());
    fetchTimeseriesSpy.mockImplementation(() => createMockJqXHRChainable());

    vi.useFakeTimers();
  });

  afterEach(() => {
    _resetMetricsDashboardForTests();
    vi.useRealTimers();
    document.body.innerHTML = "";
  });

  it("clicking a UI row fires fetchTimeseries with the row's event name", () => {
    primeUiPanelWithEvents([
      {
        event_name: "utub_opened",
        category: "ui",
        description: "UTub opened",
        total_count: 100,
        previous_count: 80,
      },
    ]);

    const row = getUiPanelTbody().querySelector(
      "tr.MetricsTopTableRow",
    ) as HTMLTableRowElement;
    expect(row.dataset.eventName).toBe("utub_opened");

    row.click();

    expect(fetchTimeseriesSpy).toHaveBeenCalledTimes(1);
    expect(fetchTimeseriesSpy.mock.calls[0][0]).toMatchObject({
      eventName: "utub_opened",
      window: "day",
      resolution: "hour",
    });
  });

  it("clicking a UI row sets aria-current on the clicked row and clears it from siblings", () => {
    primeUiPanelWithEvents([
      {
        event_name: "utub_opened",
        category: "ui",
        description: "UTub opened",
        total_count: 100,
        previous_count: 80,
      },
      {
        event_name: "ui_url_copy",
        category: "ui",
        description: "URL copied",
        total_count: 50,
        previous_count: 40,
      },
    ]);

    // Auto-default selection puts aria-current on the highest-ranked row;
    // clicking row 2 should move it.
    const rows = Array.from(
      getUiPanelTbody().querySelectorAll<HTMLTableRowElement>(
        "tr.MetricsTopTableRow",
      ),
    );
    expect(rows[0].getAttribute("aria-current")).toBe("true");
    expect(rows[1].getAttribute("aria-current")).toBeNull();

    rows[1].click();

    // The re-render replaces the row nodes, so re-query.
    const afterRows = Array.from(
      getUiPanelTbody().querySelectorAll<HTMLTableRowElement>(
        "tr.MetricsTopTableRow",
      ),
    );
    expect(afterRows[0].getAttribute("aria-current")).toBeNull();
    expect(afterRows[1].getAttribute("aria-current")).toBe("true");
  });

  it("Enter on a focused row fires fetchTimeseries", () => {
    primeUiPanelWithEvents([
      {
        event_name: "utub_opened",
        category: "ui",
        description: "UTub opened",
        total_count: 100,
        previous_count: 80,
      },
    ]);

    const row = getUiPanelTbody().querySelector(
      "tr.MetricsTopTableRow",
    ) as HTMLTableRowElement;
    $(row).trigger($.Event("keydown", { key: "Enter" }));

    expect(fetchTimeseriesSpy).toHaveBeenCalledTimes(1);
    expect(fetchTimeseriesSpy.mock.calls[0][0]).toMatchObject({
      eventName: "utub_opened",
    });
  });

  it("Space on a focused row fires fetchTimeseries and preventsDefault", () => {
    primeUiPanelWithEvents([
      {
        event_name: "utub_opened",
        category: "ui",
        description: "UTub opened",
        total_count: 100,
        previous_count: 80,
      },
    ]);

    const row = getUiPanelTbody().querySelector(
      "tr.MetricsTopTableRow",
    ) as HTMLTableRowElement;
    const preventDefaultSpy = vi.fn();
    $(row).trigger(
      $.Event("keydown", { key: " ", preventDefault: preventDefaultSpy }),
    );

    expect(preventDefaultSpy).toHaveBeenCalled();
    expect(fetchTimeseriesSpy).toHaveBeenCalledTimes(1);
  });

  it("other keys on a row do not fire fetchTimeseries", () => {
    primeUiPanelWithEvents([
      {
        event_name: "utub_opened",
        category: "ui",
        description: "UTub opened",
        total_count: 100,
        previous_count: 80,
      },
    ]);

    const row = getUiPanelTbody().querySelector(
      "tr.MetricsTopTableRow",
    ) as HTMLTableRowElement;
    $(row).trigger($.Event("keydown", { key: "Tab" }));
    $(row).trigger($.Event("keydown", { key: "ArrowDown" }));

    expect(fetchTimeseriesSpy).not.toHaveBeenCalled();
  });

  it("clicking inside the empty-state row is ignored", () => {
    primeUiPanelWithEvents([]);

    const emptyRow = getUiPanelTbody().querySelector(
      "tr.MetricsTopTableEmptyRow",
    ) as HTMLTableRowElement | null;
    expect(emptyRow).not.toBeNull();
    emptyRow?.click();

    expect(fetchTimeseriesSpy).not.toHaveBeenCalled();
  });

  it("clicking an API row forwards endpoint + method dataset to fetchTimeseries", () => {
    fetchTopEventsSpy.mockImplementation(
      ({ category }: { category: "api" | "ui" | "domain" }) => {
        const events =
          category === "api"
            ? [
                {
                  event_name: "GET /utubs/<int:utub_id>",
                  category: "api" as const,
                  description: "/utubs/<int:utub_id>",
                  total_count: 250,
                  previous_count: 200,
                },
              ]
            : [];
        return createMockJqXHRChainable({
          done: (cb: unknown) => {
            (cb as (response: unknown) => void)(makeTopEventsResponse(events));
          },
        });
      },
    );
    initMetricsDashboard();
    // Auto-select on initial load fires one timeseries fetch; clear so the
    // subsequent click assertion sees exactly the click's call.
    fetchTimeseriesSpy.mockClear();

    const apiTbody = document.querySelector(
      "#MetricsTopTableApi tbody",
    ) as HTMLTableSectionElement;
    const row = apiTbody.querySelector(
      "tr.MetricsTopTableRow",
    ) as HTMLTableRowElement;
    expect(row.dataset.eventName).toBe("GET /utubs/<int:utub_id>");

    row.click();

    expect(fetchTimeseriesSpy).toHaveBeenCalledTimes(1);
    expect(fetchTimeseriesSpy.mock.calls[0][0]).toMatchObject({
      eventName: "api_hit",
      endpoint: "/utubs/<int:utub_id>",
      method: "GET",
      window: "day",
      resolution: "hour",
    });
  });
});

describe("metrics-dashboard auto-default timeseries selection", () => {
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
    renderTimeseriesChartSpy.mockReset();

    fetchSummarySpy.mockImplementation(() => createMockJqXHRChainable());
    fetchTimeseriesSpy.mockImplementation(() => createMockJqXHRChainable());

    vi.useFakeTimers();
  });

  afterEach(() => {
    _resetMetricsDashboardForTests();
    vi.useRealTimers();
    document.body.innerHTML = "";
  });

  it("auto-selects the highest-ranked UI event on initial load and fires fetchTimeseries", () => {
    fetchTopEventsSpy.mockImplementation(
      ({ category }: { category: "api" | "ui" | "domain" }) => {
        const events =
          category === "ui"
            ? [
                {
                  event_name: "utub_opened",
                  category: "ui" as const,
                  description: "UTub opened",
                  total_count: 200,
                  previous_count: 150,
                },
                {
                  event_name: "ui_url_copy",
                  category: "ui" as const,
                  description: "URL copied",
                  total_count: 50,
                  previous_count: 40,
                },
              ]
            : [];
        return createMockJqXHRChainable({
          done: (cb: unknown) => {
            (cb as (response: unknown) => void)(makeTopEventsResponse(events));
          },
        });
      },
    );

    initMetricsDashboard();

    const uiSelect = document.getElementById(
      "MetricsTimeseriesEventUi",
    ) as HTMLSelectElement;
    expect(uiSelect.value).toBe("utub_opened");
    expect(fetchTimeseriesSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        eventName: "utub_opened",
        window: "day",
        resolution: "hour",
      }),
    );

    const firstRow = document.querySelector(
      "#MetricsTopTableUi tbody tr.MetricsTopTableRow",
    ) as HTMLTableRowElement;
    expect(firstRow.getAttribute("aria-current")).toBe("true");
  });

  it("changing the window re-fires fetchTimeseries even when the user's pick is still valid", () => {
    // Same event present in both day and week responses so the user's pick is
    // never invalidated by polling — only the window-change should re-trigger.
    fetchTopEventsSpy.mockImplementation(
      ({
        category,
        window,
      }: {
        category: "api" | "ui" | "domain";
        window: string;
      }) => {
        const events =
          category === "ui"
            ? [
                {
                  event_name: "utub_opened",
                  category: "ui" as const,
                  description: "UTub opened",
                  total_count: window === "week" ? 1400 : 200,
                  previous_count: 150,
                },
              ]
            : [];
        return createMockJqXHRChainable({
          done: (cb: unknown) => {
            (cb as (response: unknown) => void)({
              window,
              category,
              events,
            });
          },
          // Synchronously settle so the chart-window tracker is set before
          // the window-change assertion runs.
          always: (cb: unknown) => {
            (cb as () => void)();
          },
        });
      },
    );
    // Synchronously settle the timeseries .done so the chart-window tracker
    // is populated for the day window before we switch.
    let timeseriesCallCount = 0;
    fetchTimeseriesSpy.mockImplementation(({ window }: { window: string }) => {
      timeseriesCallCount += 1;
      return createMockJqXHRChainable({
        done: (cb: unknown) => {
          (cb as (response: unknown) => void)({
            event_name: "utub_opened",
            window,
            resolution: "hour",
            buckets: [],
          });
        },
        always: (cb: unknown) => {
          (cb as () => void)();
        },
      });
    });

    initMetricsDashboard();
    // 1 fetch from initial auto-select (UI category, day window).
    expect(timeseriesCallCount).toBe(1);
    expect(fetchTimeseriesSpy.mock.calls[0][0]).toMatchObject({
      window: "day",
    });

    // Switch from Day to Week — the user's selection (utub_opened) is still
    // in the week response, but the chart was fetched for day, so it must
    // re-fetch for week.
    const weekButton = document.querySelector(
      '.MetricsWindowButton[data-window="week"]',
    ) as HTMLButtonElement;
    weekButton.click();

    expect(timeseriesCallCount).toBe(2);
    expect(fetchTimeseriesSpy.mock.calls[1][0]).toMatchObject({
      eventName: "utub_opened",
      window: "week",
    });
  });

  it("does not call fetchTimeseries when the top events list is empty", () => {
    fetchTopEventsSpy.mockImplementation(() =>
      createMockJqXHRChainable({
        done: (cb: unknown) => {
          (cb as (response: unknown) => void)(makeTopEventsResponse([]));
        },
      }),
    );

    initMetricsDashboard();

    expect(fetchTimeseriesSpy).not.toHaveBeenCalled();
  });
});
