/**
 * Badge behavior for the admin metrics dashboard.
 *
 * Two sibling badges share the 1 s ticker:
 *
 *   - `#MetricsLastFlush` — elapsed since the worker liveness sentinel.
 *     Goes "stale" at 2 min (two missed cron ticks); a non-trivial gap is a
 *     real signal that the worker is dead.
 *   - `#MetricsLastEvent` — elapsed since the most recent AnonymousMetrics
 *     bucket. Never paints itself stale because hours-old data is normal
 *     during low-traffic stretches.
 *
 * Each badge has its own `*Text` and `*Announcement` slots so the visible text
 * refreshes every tick while the aria-live sink fires only on bucket
 * transitions. Query-client and render modules are mocked so each spec
 * exercises only the badge state machine. `vi.useFakeTimers()` is installed in
 * `beforeEach` so advancing time is deterministic; `Date.now()` returns the
 * fake clock under fake timers.
 */

const {
  fetchSummarySpy,
  fetchTopEventsSpy,
  fetchTimeseriesSpy,
  fetchGroupedTimeseriesSpy,
  renderSummarySpy,
  renderTopTableSpy,
  renderTimeseriesChartSpy,
} = vi.hoisted(() => ({
  fetchSummarySpy: vi.fn(),
  fetchTopEventsSpy: vi.fn(),
  fetchTimeseriesSpy: vi.fn(),
  fetchGroupedTimeseriesSpy: vi.fn(),
  renderSummarySpy: vi.fn(),
  renderTopTableSpy: vi.fn(),
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

vi.mock("../render-top-table.js", () => ({
  renderTopTable: renderTopTableSpy,
}));

vi.mock("../render-timeseries-chart.js", () => ({
  renderTimeseriesChart: renderTimeseriesChartSpy,
}));

import { createMockJqXHRChainable } from "../../__tests__/helpers/mock-jquery.js";
import {
  _renderLastEventBadgeForTests,
  _renderLastFlushBadgeForTests,
  _resetMetricsDashboardForTests,
  _setLastEventAtMsForTests,
  _setLastFlushAtMsForTests,
  initMetricsDashboard,
} from "../metrics-dashboard.js";

const FLUSH_BADGE_ID = "MetricsLastFlush";
const FLUSH_BADGE_TEXT_ID = "MetricsLastFlushText";
const FLUSH_ANNOUNCEMENT_ID = "MetricsLastFlushAnnouncement";
const EVENT_BADGE_ID = "MetricsLastEvent";
const EVENT_BADGE_TEXT_ID = "MetricsLastEventText";
const EVENT_ANNOUNCEMENT_ID = "MetricsLastEventAnnouncement";
const STALE_CLASS = "MetricsBadgeStale";

const DASHBOARD_HTML = `
  <main id="MetricsDashboard" aria-busy="false">
    <header>
      <span id="${FLUSH_BADGE_ID}" class="flush-badge" aria-live="off">
        <span class="dot" aria-hidden="true"></span>
        <span id="${FLUSH_BADGE_TEXT_ID}"></span>
      </span>
      <span id="${EVENT_BADGE_ID}" class="flush-badge" aria-live="off">
        <span class="dot" aria-hidden="true"></span>
        <span id="${EVENT_BADGE_TEXT_ID}"></span>
      </span>
      <span id="${FLUSH_ANNOUNCEMENT_ID}" class="visually-hidden" aria-live="polite"></span>
      <span id="${EVENT_ANNOUNCEMENT_ID}" class="visually-hidden" aria-live="polite"></span>
      <button id="MetricsRefreshNowBtn" type="button"></button>
    </header>
    <button class="MetricsWindowButton" data-window="day" aria-pressed="true"></button>
    <button class="MetricsWindowButton" data-window="week" aria-pressed="false"></button>
    <button class="MetricsWindowButton" data-window="month" aria-pressed="false"></button>
    <button class="MetricsWindowButton" data-window="year" aria-pressed="false"></button>
    <div id="MetricsTablist" role="tablist">
      <button id="MetricsTabApi"    role="tab" aria-selected="true"  tabindex="0"  data-category="api"></button>
      <button id="MetricsTabUi"     role="tab" aria-selected="false" tabindex="-1" data-category="ui"></button>
      <button id="MetricsTabDomain" role="tab" aria-selected="false" tabindex="-1" data-category="domain"></button>
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
    <div id="MetricsErrorBanner" class="hidden"></div>
  </main>
`;

function getElement(id: string): HTMLElement {
  return document.getElementById(id) as HTMLElement;
}

describe("metrics-dashboard last-flush badge", () => {
  beforeEach(() => {
    document.body.innerHTML = DASHBOARD_HTML;

    fetchSummarySpy.mockReset();
    fetchTopEventsSpy.mockReset();
    fetchTimeseriesSpy.mockReset();
    fetchGroupedTimeseriesSpy.mockReset();
    renderSummarySpy.mockReset();
    renderTopTableSpy.mockReset();
    renderTimeseriesChartSpy.mockReset();

    fetchSummarySpy.mockImplementation(() => createMockJqXHRChainable());
    fetchTopEventsSpy.mockImplementation(() => createMockJqXHRChainable());
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

  it("renders 'Last flush unknown' when last_flush_at is null", () => {
    _setLastFlushAtMsForTests(null);
    _renderLastFlushBadgeForTests();

    expect(getElement(FLUSH_BADGE_TEXT_ID).textContent).toBe(
      "Last flush unknown",
    );
    expect(getElement(FLUSH_BADGE_ID).classList.contains(STALE_CLASS)).toBe(
      false,
    );
  });

  it("renders 'just now' when elapsed < 5s", () => {
    _setLastFlushAtMsForTests(Date.now() - 2_000);
    _renderLastFlushBadgeForTests();

    expect(getElement(FLUSH_BADGE_TEXT_ID).textContent).toBe(
      "Last flush just now",
    );
    expect(getElement(FLUSH_ANNOUNCEMENT_ID).textContent).toBe(
      "Last flush just now",
    );
  });

  it("crosses to 'Ns ago' at 5s without stale class", () => {
    _setLastFlushAtMsForTests(Date.now() - 6_000);
    _renderLastFlushBadgeForTests();

    expect(getElement(FLUSH_BADGE_TEXT_ID).textContent).toBe(
      "Last flush 6s ago",
    );
    expect(getElement(FLUSH_BADGE_ID).classList.contains(STALE_CLASS)).toBe(
      false,
    );
  });

  it("renders 'Nm ago' fresh between 60s and 119s", () => {
    _setLastFlushAtMsForTests(Date.now() - 90_000);
    _renderLastFlushBadgeForTests();

    expect(getElement(FLUSH_BADGE_TEXT_ID).textContent).toBe(
      "Last flush 1m ago",
    );
    expect(getElement(FLUSH_BADGE_ID).classList.contains(STALE_CLASS)).toBe(
      false,
    );
  });

  it("applies stale class with minutes unit at 2 minutes (two missed cron ticks)", () => {
    _setLastFlushAtMsForTests(Date.now() - 125_000);
    _renderLastFlushBadgeForTests();

    expect(getElement(FLUSH_BADGE_TEXT_ID).textContent).toBe(
      "Last flush 2m ago (stale)",
    );
    expect(getElement(FLUSH_BADGE_ID).classList.contains(STALE_CLASS)).toBe(
      true,
    );
  });

  it("applies stale class with hours unit at >= 1h", () => {
    _setLastFlushAtMsForTests(Date.now() - 7_200_000);
    _renderLastFlushBadgeForTests();

    expect(getElement(FLUSH_BADGE_TEXT_ID).textContent).toBe(
      "Last flush 2h ago (stale)",
    );
    expect(getElement(FLUSH_BADGE_ID).classList.contains(STALE_CLASS)).toBe(
      true,
    );
  });

  it("removes the stale class on transition back to a non-stale bucket", () => {
    _setLastFlushAtMsForTests(Date.now() - 7_200_000);
    _renderLastFlushBadgeForTests();
    expect(getElement(FLUSH_BADGE_ID).classList.contains(STALE_CLASS)).toBe(
      true,
    );

    _setLastFlushAtMsForTests(Date.now() - 2_000);
    _renderLastFlushBadgeForTests();
    expect(getElement(FLUSH_BADGE_ID).classList.contains(STALE_CLASS)).toBe(
      false,
    );
  });

  it("writes to the aria-live sink only on bucket transitions, not every second", () => {
    const flushAt = Date.now() - 10_000;
    _setLastFlushAtMsForTests(flushAt);

    _renderLastFlushBadgeForTests();
    expect(getElement(FLUSH_ANNOUNCEMENT_ID).textContent).toBe(
      "Last flush 10s ago",
    );

    getElement(FLUSH_ANNOUNCEMENT_ID).textContent = "";

    for (let tickIndex = 0; tickIndex < 5; tickIndex += 1) {
      vi.advanceTimersByTime(1_000);
      _renderLastFlushBadgeForTests();
    }

    expect(getElement(FLUSH_BADGE_TEXT_ID).textContent).toBe(
      "Last flush 15s ago",
    );
    expect(getElement(FLUSH_ANNOUNCEMENT_ID).textContent).toBe("");
  });

  it("starts the ticker on init and updates the badge every second", () => {
    _setLastFlushAtMsForTests(Date.now() - 1_000);

    initMetricsDashboard();
    expect(getElement(FLUSH_BADGE_TEXT_ID).textContent).toBe(
      "Last flush just now",
    );

    vi.advanceTimersByTime(5_000);
    expect(getElement(FLUSH_BADGE_TEXT_ID).textContent).toContain("s ago");
  });

  it("stops the ticker on visibilitychange hidden and resumes on visible", () => {
    _setLastFlushAtMsForTests(Date.now() - 1_000);
    initMetricsDashboard();

    Object.defineProperty(document, "visibilityState", {
      value: "hidden",
      configurable: true,
    });
    document.dispatchEvent(new Event("visibilitychange"));

    getElement(FLUSH_BADGE_TEXT_ID).textContent = "";
    vi.advanceTimersByTime(5_000);
    expect(getElement(FLUSH_BADGE_TEXT_ID).textContent).toBe("");

    Object.defineProperty(document, "visibilityState", {
      value: "visible",
      configurable: true,
    });
    document.dispatchEvent(new Event("visibilitychange"));
    expect(getElement(FLUSH_BADGE_TEXT_ID).textContent).not.toBe("");
  });
});

describe("metrics-dashboard last-event badge", () => {
  beforeEach(() => {
    document.body.innerHTML = DASHBOARD_HTML;

    fetchSummarySpy.mockReset();
    fetchTopEventsSpy.mockReset();
    fetchTimeseriesSpy.mockReset();
    fetchGroupedTimeseriesSpy.mockReset();
    renderSummarySpy.mockReset();
    renderTopTableSpy.mockReset();
    renderTimeseriesChartSpy.mockReset();

    fetchSummarySpy.mockImplementation(() => createMockJqXHRChainable());
    fetchTopEventsSpy.mockImplementation(() => createMockJqXHRChainable());
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

  it("renders 'Last event unknown' when last_event_at is null", () => {
    _setLastEventAtMsForTests(null);
    _renderLastEventBadgeForTests();

    expect(getElement(EVENT_BADGE_TEXT_ID).textContent).toBe(
      "Last event unknown",
    );
  });

  it("renders 'Last event just now' when elapsed < 5s", () => {
    _setLastEventAtMsForTests(Date.now() - 2_000);
    _renderLastEventBadgeForTests();

    expect(getElement(EVENT_BADGE_TEXT_ID).textContent).toBe(
      "Last event just now",
    );
  });

  it("renders 'Last event Ns ago' between 5s and 60s", () => {
    _setLastEventAtMsForTests(Date.now() - 30_000);
    _renderLastEventBadgeForTests();

    expect(getElement(EVENT_BADGE_TEXT_ID).textContent).toBe(
      "Last event 30s ago",
    );
  });

  it("renders 'Last event Nm ago' between 1m and 1h", () => {
    _setLastEventAtMsForTests(Date.now() - 47 * 60_000);
    _renderLastEventBadgeForTests();

    expect(getElement(EVENT_BADGE_TEXT_ID).textContent).toBe(
      "Last event 47m ago",
    );
  });

  it("renders 'Last event Nh ago' at >= 1h WITHOUT applying stale class", () => {
    _setLastEventAtMsForTests(Date.now() - 7_200_000);
    _renderLastEventBadgeForTests();

    expect(getElement(EVENT_BADGE_TEXT_ID).textContent).toBe(
      "Last event 2h ago",
    );
    expect(getElement(EVENT_BADGE_ID).classList.contains(STALE_CLASS)).toBe(
      false,
    );
  });

  it("writes to the aria-live sink only on bucket transitions", () => {
    _setLastEventAtMsForTests(Date.now() - 10_000);
    _renderLastEventBadgeForTests();
    expect(getElement(EVENT_ANNOUNCEMENT_ID).textContent).toBe(
      "Last event 10s ago",
    );

    getElement(EVENT_ANNOUNCEMENT_ID).textContent = "";

    for (let tickIndex = 0; tickIndex < 5; tickIndex += 1) {
      vi.advanceTimersByTime(1_000);
      _renderLastEventBadgeForTests();
    }

    expect(getElement(EVENT_BADGE_TEXT_ID).textContent).toBe(
      "Last event 15s ago",
    );
    expect(getElement(EVENT_ANNOUNCEMENT_ID).textContent).toBe("");
  });

  it("ticks both badges from a single setInterval", () => {
    _setLastFlushAtMsForTests(Date.now() - 1_000);
    _setLastEventAtMsForTests(Date.now() - 30_000);
    initMetricsDashboard();

    expect(getElement(FLUSH_BADGE_TEXT_ID).textContent).toBe(
      "Last flush just now",
    );
    expect(getElement(EVENT_BADGE_TEXT_ID).textContent).toBe(
      "Last event 30s ago",
    );

    vi.advanceTimersByTime(5_000);

    expect(getElement(FLUSH_BADGE_TEXT_ID).textContent).toContain("s ago");
    expect(getElement(EVENT_BADGE_TEXT_ID).textContent).toBe(
      "Last event 35s ago",
    );
  });
});
