/**
 * Polling + visibility + Refresh button behavior for the admin metrics
 * dashboard controller.
 *
 * The query-client and render modules are fully mocked so the spec exercises
 * only the lifecycle logic: interval cadence, visibilitychange halt/resume,
 * and Refresh-button abort semantics.
 *
 * CRITICAL: `vi.useFakeTimers()` is installed in `beforeEach` BEFORE
 * `initMetricsDashboard()` is invoked. The initial `fetchAll()` call inside
 * `initMetricsDashboard()` would escape fake-timer control if the install
 * order is reversed, causing the "polls every 60s" assertion to under-count.
 */

const {
  fetchSummarySpy,
  fetchTopEventsSpy,
  fetchGroupedTimeseriesSpy,
  renderSummarySpy,
  renderTopTableSpy,
} = vi.hoisted(() => ({
  fetchSummarySpy: vi.fn(),
  fetchTopEventsSpy: vi.fn(),
  fetchGroupedTimeseriesSpy: vi.fn(),
  renderSummarySpy: vi.fn(),
  renderTopTableSpy: vi.fn(),
}));

/**
 * Build a jqXHR-like object that synchronously fires `.always()` callbacks
 * when they are registered. Lifecycle tests need `.always()` to run so the
 * in-flight state clears, but they DON'T need `.done()` / `.fail()` to fire
 * — those are exercised by the render-fn tests, not here.
 *
 * `abort` is included so the Refresh button can call it during the abort path.
 */
function makeSettlingXhr(abortFn: () => void = () => {}): JQuery.jqXHR {
  const chainable = {
    done: vi.fn().mockReturnThis(),
    fail: vi.fn().mockReturnThis(),
    always: vi.fn().mockImplementation((callback: () => void) => {
      callback();
      return chainable;
    }),
    abort: abortFn,
  };
  return chainable as unknown as JQuery.jqXHR;
}

vi.mock("../metrics-query-client.js", () => ({
  fetchSummary: fetchSummarySpy,
  fetchTopEvents: fetchTopEventsSpy,
  fetchTimeseries: vi.fn(),
  fetchGroupedTimeseries: fetchGroupedTimeseriesSpy,
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
    <button class="MetricsWindowButton" data-window="day" aria-pressed="true"></button>
    <button class="MetricsWindowButton" data-window="week" aria-pressed="false"></button>
    <button class="MetricsWindowButton" data-window="month" aria-pressed="false"></button>
    <button class="MetricsWindowButton" data-window="year" aria-pressed="false"></button>
    <section id="MetricsSummary"><div id="MetricsSummaryGrid"></div></section>
    <section id="MetricsPanelApi">
      <table id="MetricsTopTableApi"><tbody></tbody></table>
    </section>
    <section id="MetricsPanelUi">
      <table id="MetricsTopTableUi"><tbody></tbody></table>
    </section>
    <section id="MetricsPanelDomain">
      <table id="MetricsTopTableDomain"><tbody></tbody></table>
    </section>
    <div id="MetricsErrorBanner" class="hidden"></div>
  </main>
`;

function setDocumentVisibility(state: "visible" | "hidden"): void {
  Object.defineProperty(document, "visibilityState", {
    value: state,
    configurable: true,
  });
}

describe("metrics-dashboard polling + visibility lifecycle", () => {
  beforeEach(() => {
    document.body.innerHTML = DASHBOARD_HTML;
    setDocumentVisibility("visible");

    fetchSummarySpy.mockReset();
    fetchTopEventsSpy.mockReset();
    fetchGroupedTimeseriesSpy.mockReset();
    renderSummarySpy.mockReset();
    renderTopTableSpy.mockReset();

    fetchSummarySpy.mockImplementation(() => makeSettlingXhr());
    fetchTopEventsSpy.mockImplementation(() => makeSettlingXhr());
    fetchGroupedTimeseriesSpy.mockImplementation(() => makeSettlingXhr());

    // CRITICAL: install fake timers BEFORE initMetricsDashboard so the
    // initial fetchAll() is counted against the timer-controlled lifecycle.
    vi.useFakeTimers();
  });

  afterEach(() => {
    _resetMetricsDashboardForTests();
    vi.useRealTimers();
    document.body.innerHTML = "";
  });

  function totalFetchAllCalls(): number {
    // Each fetchAll() fires 1 summary + 3 top-events (one per category).
    // Asserting the summary call count is the cleanest proxy for "how many
    // fetchAll() rounds ran" — top-events also fires N×3 but summary fires
    // exactly once per round.
    return fetchSummarySpy.mock.calls.length;
  }

  it("polls every 60s after init", () => {
    initMetricsDashboard();
    expect(totalFetchAllCalls()).toBe(1);

    vi.advanceTimersByTime(180_000);
    expect(totalFetchAllCalls()).toBe(4);
  });

  it("stops polling when document.visibilityState becomes hidden", () => {
    initMetricsDashboard();
    expect(totalFetchAllCalls()).toBe(1);

    setDocumentVisibility("hidden");
    document.dispatchEvent(new Event("visibilitychange"));

    vi.advanceTimersByTime(300_000);
    expect(totalFetchAllCalls()).toBe(1);
  });

  it("refetches on visibility return when more than 5s have elapsed", () => {
    initMetricsDashboard();
    expect(totalFetchAllCalls()).toBe(1);

    setDocumentVisibility("hidden");
    document.dispatchEvent(new Event("visibilitychange"));

    vi.advanceTimersByTime(10_000);

    setDocumentVisibility("visible");
    document.dispatchEvent(new Event("visibilitychange"));

    expect(totalFetchAllCalls()).toBe(2);
  });

  it("does not refetch on rapid hide/show toggles within 5s", () => {
    initMetricsDashboard();
    expect(totalFetchAllCalls()).toBe(1);

    setDocumentVisibility("hidden");
    document.dispatchEvent(new Event("visibilitychange"));

    vi.advanceTimersByTime(1_000);

    setDocumentVisibility("visible");
    document.dispatchEvent(new Event("visibilitychange"));

    expect(totalFetchAllCalls()).toBe(1);
  });

  it("Refresh button aborts in-flight requests and restarts the interval", () => {
    // Use a non-settling xhr for this test so the abort path has real
    // in-flight handles to abort. We track aborts via the per-call abort fn.
    const abortSpy = vi.fn();
    fetchSummarySpy.mockImplementation(() => {
      const chainable = {
        done: vi.fn().mockReturnThis(),
        fail: vi.fn().mockReturnThis(),
        always: vi.fn().mockReturnThis(),
        abort: abortSpy,
      };
      return chainable as unknown as JQuery.jqXHR;
    });
    fetchTopEventsSpy.mockImplementation(() => {
      const chainable = {
        done: vi.fn().mockReturnThis(),
        fail: vi.fn().mockReturnThis(),
        always: vi.fn().mockReturnThis(),
        abort: vi.fn(),
      };
      return chainable as unknown as JQuery.jqXHR;
    });

    initMetricsDashboard();
    expect(totalFetchAllCalls()).toBe(1);
    expect(abortSpy).not.toHaveBeenCalled();

    // The non-settling mock leaves aria-disabled='true' after init, which
    // would normally suppress the refresh click. Manually clear it to
    // exercise the abort + restart path without coupling this test to the
    // settling-callback choreography exercised in the in-flight guard test.
    const refreshButton = document.getElementById(
      "MetricsRefreshNowBtn",
    ) as HTMLButtonElement;
    refreshButton.removeAttribute("aria-disabled");
    refreshButton.click();

    expect(abortSpy).toHaveBeenCalled();
    expect(totalFetchAllCalls()).toBe(2);

    // The polling interval was reset by the refresh — 60s after the refresh
    // click the next poll fires, regardless of when the previous interval
    // would have fired.
    refreshButton.removeAttribute("aria-disabled");
    vi.advanceTimersByTime(60_000);
    expect(totalFetchAllCalls()).toBe(3);
  });

  it("fetchTopEvents .fail with non-0, non-429 status shows the error banner", () => {
    // Summary settles cleanly; only the top-events branch fails so the test
    // targets the top-events fail handler in isolation.
    fetchSummarySpy.mockImplementation(() => makeSettlingXhr());
    fetchTopEventsSpy.mockImplementation(() => {
      const chainable = {
        done: vi.fn().mockReturnThis(),
        fail: vi.fn().mockImplementation((cb: (xhr: JQuery.jqXHR) => void) => {
          const failureXhr = {
            readyState: 4,
            status: 500,
          } as unknown as JQuery.jqXHR;
          cb(failureXhr);
          return chainable;
        }),
        always: vi.fn().mockImplementation((cb: () => void) => {
          cb();
          return chainable;
        }),
        abort: vi.fn(),
      };
      return chainable as unknown as JQuery.jqXHR;
    });

    initMetricsDashboard();

    const banner = document.getElementById("MetricsErrorBanner") as HTMLElement;
    expect(banner.classList.contains("hidden")).toBe(false);
  });

  it("fetchTopEvents .fail with 429-handled xhr does not show the banner", () => {
    fetchSummarySpy.mockImplementation(() => makeSettlingXhr());
    fetchTopEventsSpy.mockImplementation(() => {
      const chainable = {
        done: vi.fn().mockReturnThis(),
        fail: vi.fn().mockImplementation((cb: (xhr: JQuery.jqXHR) => void) => {
          // is429Handled() reads the `_429Handled` flag stamped by the global
          // ajaxPrefilter. When set, the fail handler must return early so
          // the banner stays hidden.
          const rateLimitedXhr = {
            readyState: 4,
            status: 429,
            _429Handled: true,
          } as unknown as JQuery.jqXHR;
          cb(rateLimitedXhr);
          return chainable;
        }),
        always: vi.fn().mockImplementation((cb: () => void) => {
          cb();
          return chainable;
        }),
        abort: vi.fn(),
      };
      return chainable as unknown as JQuery.jqXHR;
    });

    initMetricsDashboard();

    const banner = document.getElementById("MetricsErrorBanner") as HTMLElement;
    expect(banner.classList.contains("hidden")).toBe(true);
  });

  it("fetchTopEvents .fail with readyState 0 (abort) does not show the banner", () => {
    fetchSummarySpy.mockImplementation(() => makeSettlingXhr());
    fetchTopEventsSpy.mockImplementation(() => {
      const chainable = {
        done: vi.fn().mockReturnThis(),
        fail: vi.fn().mockImplementation((cb: (xhr: JQuery.jqXHR) => void) => {
          const abortedXhr = {
            readyState: 0,
            status: 0,
          } as unknown as JQuery.jqXHR;
          cb(abortedXhr);
          return chainable;
        }),
        always: vi.fn().mockImplementation((cb: () => void) => {
          cb();
          return chainable;
        }),
        abort: vi.fn(),
      };
      return chainable as unknown as JQuery.jqXHR;
    });

    initMetricsDashboard();

    const banner = document.getElementById("MetricsErrorBanner") as HTMLElement;
    expect(banner.classList.contains("hidden")).toBe(true);
  });

  it("Refresh aborts all three per-category top-events XHRs (api/ui/domain)", () => {
    // DD-1 regression guard. Each per-category top-events call gets a
    // dedicated abort spy so we can verify all three are cancelled when
    // Refresh fires — not just the api slot, as was the case before.
    const apiAbort = vi.fn();
    const uiAbort = vi.fn();
    const domainAbort = vi.fn();
    const topAbortByCategory: Record<string, () => void> = {
      api: apiAbort,
      ui: uiAbort,
      domain: domainAbort,
    };

    fetchSummarySpy.mockImplementation(() => {
      const chainable = {
        done: vi.fn().mockReturnThis(),
        fail: vi.fn().mockReturnThis(),
        always: vi.fn().mockReturnThis(),
        abort: vi.fn(),
      };
      return chainable as unknown as JQuery.jqXHR;
    });
    fetchTopEventsSpy.mockImplementation(
      (args: { category: "api" | "ui" | "domain" }) => {
        const chainable = {
          done: vi.fn().mockReturnThis(),
          fail: vi.fn().mockReturnThis(),
          always: vi.fn().mockReturnThis(),
          abort: topAbortByCategory[args.category],
        };
        return chainable as unknown as JQuery.jqXHR;
      },
    );

    initMetricsDashboard();
    expect(apiAbort).not.toHaveBeenCalled();
    expect(uiAbort).not.toHaveBeenCalled();
    expect(domainAbort).not.toHaveBeenCalled();

    const refreshButton = document.getElementById(
      "MetricsRefreshNowBtn",
    ) as HTMLButtonElement;
    refreshButton.removeAttribute("aria-disabled");
    refreshButton.click();

    expect(apiAbort).toHaveBeenCalledTimes(1);
    expect(uiAbort).toHaveBeenCalledTimes(1);
    expect(domainAbort).toHaveBeenCalledTimes(1);
  });

  it("Refresh button click is ignored while still in-flight (aria-disabled guard)", () => {
    // Non-settling mock so the in-flight guard stays active.
    fetchSummarySpy.mockImplementation(() => {
      const chainable = {
        done: vi.fn().mockReturnThis(),
        fail: vi.fn().mockReturnThis(),
        always: vi.fn().mockReturnThis(),
        abort: vi.fn(),
      };
      return chainable as unknown as JQuery.jqXHR;
    });
    fetchTopEventsSpy.mockImplementation(() => {
      const chainable = {
        done: vi.fn().mockReturnThis(),
        fail: vi.fn().mockReturnThis(),
        always: vi.fn().mockReturnThis(),
        abort: vi.fn(),
      };
      return chainable as unknown as JQuery.jqXHR;
    });

    initMetricsDashboard();
    const refreshButton = document.getElementById(
      "MetricsRefreshNowBtn",
    ) as HTMLButtonElement;

    // The initial fetchAll() set aria-disabled='true' synchronously because
    // the in-flight set is non-empty. A click during this state must be
    // suppressed.
    expect(refreshButton.getAttribute("aria-disabled")).toBe("true");
    refreshButton.click();

    // Only the initial fetchAll() round should have run.
    expect(totalFetchAllCalls()).toBe(1);
  });
});
