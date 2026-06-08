/**
 * "Last flush N seconds ago" badge behavior for the admin metrics dashboard.
 *
 * The badge re-renders every 1 s while the tab is visible, computing elapsed
 * time as `Date.now() - _lastFlushAtMs`. The visible text updates every tick;
 * the aria-live sink is written only when the elapsed bucket transitions
 * (just_now → seconds → minutes → stale).
 *
 * Query-client and render modules are mocked so each spec exercises only the
 * badge state machine. `vi.useFakeTimers()` is installed in `beforeEach` so
 * advancing time is fully deterministic; `Date.now()` returns the fake clock
 * under fake timers, which is what the badge reads.
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

import { createMockJqXHRChainable } from "../../__tests__/helpers/mock-jquery.js";
import {
  _renderLastFlushBadgeForTests,
  _resetMetricsDashboardForTests,
  _setLastFlushAtMsForTests,
  initMetricsDashboard,
} from "../metrics-dashboard.js";

const BADGE_ID = "MetricsLastFlush";
const ANNOUNCEMENT_ID = "MetricsLastFlushAnnouncement";
const STALE_CLASS = "MetricsBadgeStale";

const DASHBOARD_HTML = `
  <main id="MetricsDashboard" aria-busy="false">
    <header>
      <span id="${BADGE_ID}" aria-live="off"></span>
      <span id="${ANNOUNCEMENT_ID}" class="visually-hidden" aria-live="polite"></span>
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

function getBadge(): HTMLElement {
  return document.getElementById(BADGE_ID) as HTMLElement;
}

function getAnnouncement(): HTMLElement {
  return document.getElementById(ANNOUNCEMENT_ID) as HTMLElement;
}

describe("metrics-dashboard last-flush badge", () => {
  beforeEach(() => {
    document.body.innerHTML = DASHBOARD_HTML;

    fetchSummarySpy.mockReset();
    fetchTopEventsSpy.mockReset();
    fetchTimeseriesSpy.mockReset();
    renderSummarySpy.mockReset();
    renderTopTableSpy.mockReset();
    renderTimeseriesChartSpy.mockReset();

    fetchSummarySpy.mockImplementation(() => createMockJqXHRChainable());
    fetchTopEventsSpy.mockImplementation(() => createMockJqXHRChainable());
    fetchTimeseriesSpy.mockImplementation(() => createMockJqXHRChainable());

    vi.useFakeTimers();
  });

  afterEach(() => {
    _resetMetricsDashboardForTests();
    vi.useRealTimers();
    document.body.innerHTML = "";
  });

  it("renders empty text when last_flush_at is null", () => {
    _setLastFlushAtMsForTests(null);
    _renderLastFlushBadgeForTests();

    expect(getBadge().textContent).toBe("");
    expect(getBadge().classList.contains(STALE_CLASS)).toBe(false);
  });

  it("renders 'just now' when elapsed < 5s", () => {
    _setLastFlushAtMsForTests(Date.now() - 2_000);
    _renderLastFlushBadgeForTests();

    expect(getBadge().textContent).toBe("Last flush: just now");
    expect(getAnnouncement().textContent).toBe("Last flush: just now");
  });

  it("crosses to 'N seconds ago' at 5s", () => {
    _setLastFlushAtMsForTests(Date.now() - 6_000);
    _renderLastFlushBadgeForTests();

    expect(getBadge().textContent).toBe("Last flush: 6 seconds ago");
    expect(getBadge().classList.contains(STALE_CLASS)).toBe(false);
  });

  it("crosses to 'N minutes ago' at 60s", () => {
    _setLastFlushAtMsForTests(Date.now() - 125_000);
    _renderLastFlushBadgeForTests();

    expect(getBadge().textContent).toBe("Last flush: 2 minutes ago");
    expect(getBadge().classList.contains(STALE_CLASS)).toBe(false);
  });

  it("applies stale class at >= 1h", () => {
    _setLastFlushAtMsForTests(Date.now() - 7_200_000);
    _renderLastFlushBadgeForTests();

    expect(getBadge().textContent).toBe("Last flush: 2 hours ago (stale)");
    expect(getBadge().classList.contains(STALE_CLASS)).toBe(true);
  });

  it("removes the stale class on transition back to a non-stale bucket", () => {
    _setLastFlushAtMsForTests(Date.now() - 7_200_000);
    _renderLastFlushBadgeForTests();
    expect(getBadge().classList.contains(STALE_CLASS)).toBe(true);

    _setLastFlushAtMsForTests(Date.now() - 2_000);
    _renderLastFlushBadgeForTests();
    expect(getBadge().classList.contains(STALE_CLASS)).toBe(false);
  });

  it("writes to the aria-live sink only on bucket transitions, not every second", () => {
    // Anchor 10 s in the past so we're firmly in the `seconds` bucket.
    const flushAt = Date.now() - 10_000;
    _setLastFlushAtMsForTests(flushAt);

    // First render: bucket transitions null → "seconds", announcement fires.
    _renderLastFlushBadgeForTests();
    expect(getAnnouncement().textContent).toBe("Last flush: 10 seconds ago");

    // Clear the sink so re-writes are detectable.
    getAnnouncement().textContent = "";

    // Advance 5 fake seconds within the same bucket; render each tick.
    for (let tickIndex = 0; tickIndex < 5; tickIndex += 1) {
      vi.advanceTimersByTime(1_000);
      _renderLastFlushBadgeForTests();
    }

    // The visible badge updated (11 → 15 seconds) but the announcement sink
    // was NOT written again — still empty from the manual clear above.
    expect(getBadge().textContent).toBe("Last flush: 15 seconds ago");
    expect(getAnnouncement().textContent).toBe("");
  });

  it("starts the ticker on init and updates the badge every second", () => {
    _setLastFlushAtMsForTests(Date.now() - 1_000);

    initMetricsDashboard();
    // The init call invokes renderLastFlushBadge immediately.
    expect(getBadge().textContent).toBe("Last flush: just now");

    // Crossing the 5 s threshold flips the bucket; the next tick after that
    // should reflect "N seconds ago".
    vi.advanceTimersByTime(5_000);
    expect(getBadge().textContent).toContain("seconds");
  });

  it("stops the ticker on visibilitychange hidden and resumes on visible", () => {
    _setLastFlushAtMsForTests(Date.now() - 1_000);
    initMetricsDashboard();

    // Hide the tab — ticker stops.
    Object.defineProperty(document, "visibilityState", {
      value: "hidden",
      configurable: true,
    });
    document.dispatchEvent(new Event("visibilitychange"));

    // Clear the badge to detect future writes.
    getBadge().textContent = "";
    vi.advanceTimersByTime(5_000);
    // No tick should have fired while hidden.
    expect(getBadge().textContent).toBe("");

    // Show the tab — ticker resumes and renders immediately.
    Object.defineProperty(document, "visibilityState", {
      value: "visible",
      configurable: true,
    });
    document.dispatchEvent(new Event("visibilitychange"));
    expect(getBadge().textContent).not.toBe("");
  });
});
