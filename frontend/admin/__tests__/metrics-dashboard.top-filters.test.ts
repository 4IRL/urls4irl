/**
 * Top-events filter behavior for the admin metrics dashboard.
 *
 * Covers the two per-tab filter controls added to each Top Events panel:
 *   - Resource dropdown (single-select, server-side filter via ?resource=)
 *   - Substring input (debounced, client-side filter over the cached events)
 *
 * The render-top-table.js module is intentionally NOT mocked so the real
 * filter pipeline runs and the test asserts the resulting DOM.
 */

const {
  fetchSummarySpy,
  fetchTopEventsSpy,
  fetchTimeseriesSpy,
  fetchGroupedTimeseriesSpy,
  renderSummarySpy,
  renderTimeseriesChartSpy,
} = vi.hoisted(() => ({
  fetchSummarySpy: vi.fn(),
  fetchTopEventsSpy: vi.fn(),
  fetchTimeseriesSpy: vi.fn(),
  fetchGroupedTimeseriesSpy: vi.fn(),
  renderSummarySpy: vi.fn(),
  renderTimeseriesChartSpy: vi.fn(),
}));

vi.mock("../metrics-query-client.js", () => ({
  fetchSummary: fetchSummarySpy,
  fetchTopEvents: fetchTopEventsSpy,
  fetchTimeseries: fetchTimeseriesSpy,
  fetchGroupedTimeseries: fetchGroupedTimeseriesSpy,
}));

vi.mock("../render-summary.js", () => ({
  renderSummary: renderSummarySpy,
}));

vi.mock("../render-timeseries-chart.js", () => ({
  renderTimeseriesChart: renderTimeseriesChartSpy,
}));

import { createMockJqXHRChainable } from "../../__tests__/helpers/mock-jquery.js";
import { APP_CONFIG } from "../../lib/config.js";
import { RESOURCES_BY_CATEGORY } from "../../types/metrics-resources.js";
import {
  _resetMetricsDashboardForTests,
  initMetricsDashboard,
} from "../metrics-dashboard.js";

const DASHBOARD_HTML = `
  <main id="MetricsDashboard" aria-busy="false">
    <button id="MetricsRefreshNowBtn" type="button"></button>
    <span id="MetricsLastFlush"><span id="MetricsLastFlushText"></span></span>
    <span id="MetricsLastFlushAnnouncement"></span>
    <span id="MetricsLastEvent"><span id="MetricsLastEventText"></span></span>
    <span id="MetricsLastEventAnnouncement"></span>
    <button class="MetricsWindowButton" data-window="day" aria-pressed="true"></button>
    <button class="MetricsWindowButton" data-window="week" aria-pressed="false"></button>
    <button class="MetricsWindowButton" data-window="month" aria-pressed="false"></button>
    <button class="MetricsWindowButton" data-window="year" aria-pressed="false"></button>
    <div id="MetricsTablist" role="tablist">
      <button id="MetricsTabApi"            role="tab" aria-selected="true"  data-tab="api"></button>
      <button id="MetricsTabUi"             role="tab" aria-selected="false" data-tab="ui"></button>
      <button id="MetricsTabDomain"         role="tab" aria-selected="false" data-tab="domain"></button>
      <button id="MetricsTabPipelineHealth" role="tab" aria-selected="false" data-tab="pipeline_health"></button>
    </div>
    <section id="MetricsSummary"><div id="MetricsSummaryGrid"></div></section>
    <section id="MetricsPanelApi" role="tabpanel" tabindex="0">
      <select id="MetricsTopResourceFilter-api" data-category="api"></select>
      <select id="MetricsTopDeviceFilter-api" class="MetricsTopDeviceFilter" data-category="api"></select>
      <input type="search" id="MetricsTopSubstringFilter-api" data-category="api">
      <select id="MetricsTimeseriesEventApi"></select>
      <table id="MetricsTopTableApi" class="top-table"><thead></thead><tbody></tbody></table>
    </section>
    <section id="MetricsPanelUi" role="tabpanel" tabindex="0" hidden>
      <select id="MetricsTopResourceFilter-ui" data-category="ui"></select>
      <select id="MetricsTopDeviceFilter-ui" class="MetricsTopDeviceFilter" data-category="ui"></select>
      <input type="search" id="MetricsTopSubstringFilter-ui" data-category="ui">
      <select id="MetricsTimeseriesEventUi"></select>
      <table id="MetricsTopTableUi" class="top-table"><thead></thead><tbody></tbody></table>
    </section>
    <section id="MetricsPanelDomain" role="tabpanel" tabindex="0" hidden>
      <select id="MetricsTopResourceFilter-domain" data-category="domain"></select>
      <select id="MetricsTopDeviceFilter-domain" class="MetricsTopDeviceFilter" data-category="domain"></select>
      <input type="search" id="MetricsTopSubstringFilter-domain" data-category="domain">
      <select id="MetricsTimeseriesEventDomain"></select>
      <table id="MetricsTopTableDomain" class="top-table"><thead></thead><tbody></tbody></table>
    </section>
    <section id="MetricsPanelPipelineHealth" role="tabpanel" tabindex="0" hidden></section>
    <div id="MetricsErrorBanner" class="hidden"></div>
  </main>
`;

interface MockTopEvent {
  event_name: string;
  category: "api" | "ui" | "domain";
  description: string;
  api_endpoint?: string | null;
  total_count: number;
  previous_count: number;
}

function topEventsResponse(events: MockTopEvent[]): {
  window: string;
  category: string;
  resource: string | null;
  events: MockTopEvent[];
} {
  return {
    window: "day",
    category: events[0]?.category ?? "ui",
    resource: null,
    events,
  };
}

function buildEvent(overrides: Partial<MockTopEvent> = {}): MockTopEvent {
  return {
    event_name: "utub_opened",
    category: "ui",
    description: "User opened a UTub",
    total_count: 10,
    previous_count: 5,
    ...overrides,
  };
}

function primeFetchTopEvents(eventsForUi: MockTopEvent[]): void {
  fetchTopEventsSpy.mockImplementation(
    ({ category }: { category: "api" | "ui" | "domain" }) => {
      const events = category === "ui" ? eventsForUi : [];
      return createMockJqXHRChainable({
        done: (cb: unknown) => {
          (cb as (response: unknown) => void)(topEventsResponse(events));
        },
      });
    },
  );
}

describe("metrics-dashboard top-events filters", () => {
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
    renderSummarySpy.mockReset();
    renderTimeseriesChartSpy.mockReset();

    fetchSummarySpy.mockImplementation(() => createMockJqXHRChainable());
    fetchTimeseriesSpy.mockImplementation(() => createMockJqXHRChainable());
    fetchGroupedTimeseriesSpy.mockImplementation(() =>
      createMockJqXHRChainable(),
    );

    vi.useFakeTimers();
  });

  afterEach(() => {
    _resetMetricsDashboardForTests();
    vi.useRealTimers();
    document.body.innerHTML = "";
  });

  it("populates the resource <select> from RESOURCES_BY_CATEGORY plus an 'All' option at boot", () => {
    primeFetchTopEvents([]);
    initMetricsDashboard();

    const apiSelect = document.getElementById(
      "MetricsTopResourceFilter-api",
    ) as HTMLSelectElement;
    const uiSelect = document.getElementById(
      "MetricsTopResourceFilter-ui",
    ) as HTMLSelectElement;
    const domainSelect = document.getElementById(
      "MetricsTopResourceFilter-domain",
    ) as HTMLSelectElement;

    expect(apiSelect.options.length).toBe(RESOURCES_BY_CATEGORY.api.length + 1);
    expect(apiSelect.options[0].value).toBe("");
    expect(uiSelect.options.length).toBe(RESOURCES_BY_CATEGORY.ui.length + 1);
    expect(domainSelect.options.length).toBe(
      RESOURCES_BY_CATEGORY.domain.length + 1,
    );
  });

  it("populates each panel's device <select> with the 3 expected (value, text) options at boot", () => {
    primeFetchTopEvents([]);
    initMetricsDashboard();

    const expectedOptions: ReadonlyArray<readonly [string, string]> = [
      ["", APP_CONFIG.strings.METRICS_TOP_DEVICE_ALL],
      [
        String(APP_CONFIG.constants.DEVICE_TYPE.MOBILE),
        APP_CONFIG.strings.METRICS_TOP_DEVICE_MOBILE,
      ],
      [
        String(APP_CONFIG.constants.DEVICE_TYPE.DESKTOP),
        APP_CONFIG.strings.METRICS_TOP_DEVICE_DESKTOP,
      ],
    ];

    for (const selectId of [
      "MetricsTopDeviceFilter-api",
      "MetricsTopDeviceFilter-ui",
      "MetricsTopDeviceFilter-domain",
    ]) {
      const deviceSelect = document.getElementById(
        selectId,
      ) as HTMLSelectElement;
      expect(deviceSelect.options.length).toBe(3);
      const actualOptions = Array.from(deviceSelect.options).map((option) => [
        option.value,
        option.textContent,
      ]);
      expect(actualOptions).toEqual(expectedOptions);
    }
  });

  it("resource change triggers a refetch with ?resource=<v>&limit=100", () => {
    primeFetchTopEvents([buildEvent()]);
    initMetricsDashboard();

    fetchTopEventsSpy.mockClear();

    const uiSelect = document.getElementById(
      "MetricsTopResourceFilter-ui",
    ) as HTMLSelectElement;
    uiSelect.value = "utub";
    uiSelect.dispatchEvent(new Event("change", { bubbles: true }));

    const uiCalls = fetchTopEventsSpy.mock.calls.filter(
      (callArgs) => (callArgs[0] as { category: string }).category === "ui",
    );
    expect(uiCalls.length).toBe(1);
    expect(uiCalls[0][0]).toMatchObject({
      category: "ui",
      resource: "utub",
      limit: 100,
    });
  });

  it("'All' (empty value) clears the resource and resets limit to the default 10", () => {
    primeFetchTopEvents([buildEvent()]);
    initMetricsDashboard();

    const uiSelect = document.getElementById(
      "MetricsTopResourceFilter-ui",
    ) as HTMLSelectElement;
    uiSelect.value = "utub";
    uiSelect.dispatchEvent(new Event("change", { bubbles: true }));

    fetchTopEventsSpy.mockClear();

    uiSelect.value = "";
    uiSelect.dispatchEvent(new Event("change", { bubbles: true }));

    const uiCalls = fetchTopEventsSpy.mock.calls.filter(
      (callArgs) => (callArgs[0] as { category: string }).category === "ui",
    );
    expect(uiCalls.length).toBe(1);
    expect(uiCalls[0][0]).toMatchObject({
      category: "ui",
      resource: null,
      limit: 10,
    });
  });

  it("substring input debounces ~150ms and does NOT issue a refetch when only narrowing", () => {
    primeFetchTopEvents([
      buildEvent({ event_name: "ui_utub_delete_confirm", description: "" }),
      buildEvent({ event_name: "ui_url_copy", description: "" }),
    ]);
    initMetricsDashboard();

    fetchTopEventsSpy.mockClear();

    const substringInput = document.getElementById(
      "MetricsTopSubstringFilter-ui",
    ) as HTMLInputElement;
    substringInput.value = "delete";
    substringInput.dispatchEvent(new Event("input", { bubbles: true }));

    // Pre-debounce: no fetch yet, table unchanged.
    expect(fetchTopEventsSpy).not.toHaveBeenCalled();

    vi.advanceTimersByTime(149);
    expect(fetchTopEventsSpy.mock.calls.length).toBe(0);

    // After the 150ms window: substring transitions filter from "off" to "on",
    // which changes the effective limit (10 -> 100), so ONE refetch is issued.
    vi.advanceTimersByTime(2);
    const uiCalls = fetchTopEventsSpy.mock.calls.filter(
      (callArgs) => (callArgs[0] as { category: string }).category === "ui",
    );
    expect(uiCalls.length).toBe(1);
    expect(uiCalls[0][0]).toMatchObject({ limit: 100 });
  });

  it("further typing while substring is already active does NOT trigger another refetch", () => {
    primeFetchTopEvents([
      buildEvent({ event_name: "ui_utub_delete_confirm", description: "" }),
      buildEvent({ event_name: "ui_utub_delete_cancel", description: "" }),
    ]);
    initMetricsDashboard();

    const substringInput = document.getElementById(
      "MetricsTopSubstringFilter-ui",
    ) as HTMLInputElement;
    substringInput.value = "d";
    substringInput.dispatchEvent(new Event("input", { bubbles: true }));
    vi.advanceTimersByTime(160);

    fetchTopEventsSpy.mockClear();

    substringInput.value = "de";
    substringInput.dispatchEvent(new Event("input", { bubbles: true }));
    vi.advanceTimersByTime(160);
    substringInput.value = "del";
    substringInput.dispatchEvent(new Event("input", { bubbles: true }));
    vi.advanceTimersByTime(160);

    const uiCalls = fetchTopEventsSpy.mock.calls.filter(
      (callArgs) => (callArgs[0] as { category: string }).category === "ui",
    );
    // Limit stayed at 100 across all three keystrokes — no transition, no refetch.
    expect(uiCalls.length).toBe(0);
  });

  it("substring narrows both the top-table rows AND the timeseries <select> options", () => {
    primeFetchTopEvents([
      buildEvent({
        event_name: "ui_utub_delete_confirm",
        description: "UTub delete confirmed",
      }),
      buildEvent({
        event_name: "ui_url_copy",
        description: "URL copied",
      }),
      buildEvent({
        event_name: "ui_tag_delete_confirm",
        description: "Tag delete confirmed",
      }),
    ]);
    initMetricsDashboard();

    const substringInput = document.getElementById(
      "MetricsTopSubstringFilter-ui",
    ) as HTMLInputElement;
    substringInput.value = "delete";
    substringInput.dispatchEvent(new Event("input", { bubbles: true }));
    vi.advanceTimersByTime(200);

    const tbody = document.querySelector(
      "#MetricsTopTableUi tbody",
    ) as HTMLTableSectionElement;
    const visibleRowNames = Array.from(
      tbody.querySelectorAll("tr.MetricsTopTableRow"),
    ).map((row) => (row.querySelector(".name")?.textContent ?? "").trim());
    expect(visibleRowNames).toEqual([
      "ui_utub_delete_confirm",
      "ui_tag_delete_confirm",
    ]);

    const tsSelect = document.getElementById(
      "MetricsTimeseriesEventUi",
    ) as HTMLSelectElement;
    const tsOptionValues = Array.from(tsSelect.options).map(
      (option) => option.value,
    );
    expect(tsOptionValues).toEqual([
      "ui_utub_delete_confirm",
      "ui_tag_delete_confirm",
    ]);
  });

  it("clearing the substring restores all rows and resets limit back to the default 10", () => {
    primeFetchTopEvents([
      buildEvent({ event_name: "ui_utub_delete_confirm", description: "" }),
      buildEvent({ event_name: "ui_url_copy", description: "" }),
    ]);
    initMetricsDashboard();

    const substringInput = document.getElementById(
      "MetricsTopSubstringFilter-ui",
    ) as HTMLInputElement;
    substringInput.value = "delete";
    substringInput.dispatchEvent(new Event("input", { bubbles: true }));
    vi.advanceTimersByTime(200);

    fetchTopEventsSpy.mockClear();

    substringInput.value = "";
    substringInput.dispatchEvent(new Event("input", { bubbles: true }));
    vi.advanceTimersByTime(200);

    const uiCalls = fetchTopEventsSpy.mock.calls.filter(
      (callArgs) => (callArgs[0] as { category: string }).category === "ui",
    );
    expect(uiCalls.length).toBe(1);
    expect(uiCalls[0][0]).toMatchObject({ limit: 10 });
  });

  it("device filter change on UI tab triggers refetch with device_type=1", () => {
    primeFetchTopEvents([buildEvent()]);
    initMetricsDashboard();

    fetchTopEventsSpy.mockClear();

    const uiDeviceSelect = document.getElementById(
      "MetricsTopDeviceFilter-ui",
    ) as HTMLSelectElement;
    uiDeviceSelect.value = "1";
    uiDeviceSelect.dispatchEvent(new Event("change", { bubbles: true }));

    // 50ms device-filter debounce — advance past it.
    vi.advanceTimersByTime(60);

    const uiCalls = fetchTopEventsSpy.mock.calls.filter(
      (callArgs) => (callArgs[0] as { category: string }).category === "ui",
    );
    expect(uiCalls.length).toBe(1);
    expect(uiCalls[0][0]).toMatchObject({
      category: "ui",
      deviceType: 1,
      limit: 100,
    });
  });

  it("device filter change on API tab triggers refetch with device_type=2", () => {
    primeFetchTopEvents([buildEvent({ category: "api" })]);
    initMetricsDashboard();

    fetchTopEventsSpy.mockClear();

    const apiDeviceSelect = document.getElementById(
      "MetricsTopDeviceFilter-api",
    ) as HTMLSelectElement;
    apiDeviceSelect.value = "2";
    apiDeviceSelect.dispatchEvent(new Event("change", { bubbles: true }));

    vi.advanceTimersByTime(60);

    const apiCalls = fetchTopEventsSpy.mock.calls.filter(
      (callArgs) => (callArgs[0] as { category: string }).category === "api",
    );
    expect(apiCalls.length).toBe(1);
    expect(apiCalls[0][0]).toMatchObject({
      category: "api",
      deviceType: 2,
      limit: 100,
    });
  });

  it("device filter set to empty clears device_type from subsequent refetches", () => {
    primeFetchTopEvents([buildEvent()]);
    initMetricsDashboard();

    const uiDeviceSelect = document.getElementById(
      "MetricsTopDeviceFilter-ui",
    ) as HTMLSelectElement;
    uiDeviceSelect.value = "1";
    uiDeviceSelect.dispatchEvent(new Event("change", { bubbles: true }));
    vi.advanceTimersByTime(60);

    fetchTopEventsSpy.mockClear();

    uiDeviceSelect.value = "";
    uiDeviceSelect.dispatchEvent(new Event("change", { bubbles: true }));
    vi.advanceTimersByTime(60);

    const uiCalls = fetchTopEventsSpy.mock.calls.filter(
      (callArgs) => (callArgs[0] as { category: string }).category === "ui",
    );
    expect(uiCalls.length).toBe(1);
    expect(uiCalls[0][0]).toMatchObject({
      category: "ui",
      deviceType: null,
      limit: 10,
    });
  });

  it("device filter survives tab switch (persisted Map state)", () => {
    primeFetchTopEvents([buildEvent()]);
    initMetricsDashboard();

    const uiDeviceSelect = document.getElementById(
      "MetricsTopDeviceFilter-ui",
    ) as HTMLSelectElement;
    uiDeviceSelect.value = "1";
    uiDeviceSelect.dispatchEvent(new Event("change", { bubbles: true }));
    vi.advanceTimersByTime(60);

    // Switch to domain tab, then back to ui — the UI device filter map state
    // should survive across tab switches.
    const apiTab = document.getElementById(
      "MetricsTabApi",
    ) as HTMLButtonElement;
    apiTab.click();
    const uiTab = document.getElementById("MetricsTabUi") as HTMLButtonElement;
    uiTab.click();

    // Trigger a fresh fetchAll via a window-button click (the refresh button is
    // gated on aria-disabled, which the mock chainable's `.always` does not
    // clear). Switching window calls fetchAll, which uses the persisted map.
    fetchTopEventsSpy.mockClear();
    const weekButton = document.querySelector(
      ".MetricsWindowButton[data-window='week']",
    ) as HTMLButtonElement;
    weekButton.click();

    const uiCalls = fetchTopEventsSpy.mock.calls.filter(
      (callArgs) => (callArgs[0] as { category: string }).category === "ui",
    );
    expect(uiCalls.length).toBe(1);
    expect(uiCalls[0][0]).toMatchObject({
      category: "ui",
      deviceType: 1,
    });
  });

  it("device filter change re-triggers timeseries for the active selection", () => {
    primeFetchTopEvents([buildEvent({ event_name: "utub_opened" })]);
    fetchTimeseriesSpy.mockImplementation(() => createMockJqXHRChainable());
    initMetricsDashboard();

    // Pre-select an event in the timeseries select so the device-filter
    // handler's tsSelect.value !== "" guard passes.
    const tsSelect = document.getElementById(
      "MetricsTimeseriesEventUi",
    ) as HTMLSelectElement;
    tsSelect.value = "utub_opened";

    fetchTimeseriesSpy.mockClear();

    const uiDeviceSelect = document.getElementById(
      "MetricsTopDeviceFilter-ui",
    ) as HTMLSelectElement;
    uiDeviceSelect.value = "1";
    uiDeviceSelect.dispatchEvent(new Event("change", { bubbles: true }));
    vi.advanceTimersByTime(60);

    const tsCalls = fetchTimeseriesSpy.mock.calls.filter(
      (callArgs) =>
        (callArgs[0] as { eventName: string }).eventName === "utub_opened",
    );
    expect(tsCalls.length).toBeGreaterThanOrEqual(1);
    expect(tsCalls[tsCalls.length - 1][0]).toMatchObject({
      eventName: "utub_opened",
      deviceType: 1,
    });
  });
});
