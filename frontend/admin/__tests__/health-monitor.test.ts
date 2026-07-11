/**
 * Polling + visibility lifecycle tests for the health-monitor controller.
 *
 * fragment-swap is fully mocked so the spec exercises only the setInterval
 * cadence and the visibilitychange pause/resume semantics.
 * vi.useFakeTimers() is installed in beforeEach BEFORE initHealthMonitor() is
 * called so the initial startPolling() call is tracked by the fake-timer
 * infrastructure.
 */

const { fetchAndSwapSpy } = vi.hoisted(() => ({
  fetchAndSwapSpy: vi.fn(),
}));

vi.mock("../fragment-swap.js", () => ({
  fetchAndSwap: fetchAndSwapSpy,
}));

import {
  HEALTH_SNAPSHOT_REGION_ID,
  initHealthMonitor,
} from "../health-monitor.js";

const SNAPSHOT_URL = "/admin/health/snapshot";
const SNAPSHOT_REGION_HTML = `<div id="${HEALTH_SNAPSHOT_REGION_ID}" data-snapshot-url="${SNAPSHOT_URL}"></div>`;

function setDocumentHidden(hidden: boolean): void {
  Object.defineProperty(document, "hidden", {
    value: hidden,
    configurable: true,
  });
}

describe("health-monitor polling lifecycle", () => {
  let disposeMonitor: (() => void) | null = null;

  function initMonitorForTest(options?: { pollIntervalMs?: number }): void {
    disposeMonitor =
      options === undefined ? initHealthMonitor() : initHealthMonitor(options);
  }

  beforeEach(() => {
    document.body.innerHTML = SNAPSHOT_REGION_HTML;
    setDocumentHidden(false);
    fetchAndSwapSpy.mockReset();
    vi.useFakeTimers();
  });

  afterEach(() => {
    if (disposeMonitor !== null) {
      disposeMonitor();
      disposeMonitor = null;
    }
    vi.useRealTimers();
    document.body.innerHTML = "";
  });

  it("fires fetchAndSwap immediately on init", () => {
    initMonitorForTest({ pollIntervalMs: 1_000 });

    expect(fetchAndSwapSpy).toHaveBeenCalledTimes(1);
  });

  it("calls fetchAndSwap with the snapshot region element and snapshot URL on init", () => {
    initMonitorForTest({ pollIntervalMs: 1_000 });

    const snapshotRegion = document.getElementById(HEALTH_SNAPSHOT_REGION_ID);
    expect(fetchAndSwapSpy).toHaveBeenCalledWith(
      expect.objectContaining({ url: SNAPSHOT_URL, targetEl: snapshotRegion }),
    );
  });

  it("fires fetchAndSwap once more per interval tick after the initial call", () => {
    initMonitorForTest({ pollIntervalMs: 1_000 });

    // 1 call on init
    expect(fetchAndSwapSpy).toHaveBeenCalledTimes(1);

    vi.advanceTimersByTime(1_000);
    expect(fetchAndSwapSpy).toHaveBeenCalledTimes(2);

    vi.advanceTimersByTime(1_000);
    expect(fetchAndSwapSpy).toHaveBeenCalledTimes(3);
  });

  it("stops firing fetches when document becomes hidden", () => {
    initMonitorForTest({ pollIntervalMs: 1_000 });

    vi.advanceTimersByTime(1_000);
    // 2 calls: 1 on init + 1 interval tick
    expect(fetchAndSwapSpy).toHaveBeenCalledTimes(2);

    setDocumentHidden(true);
    document.dispatchEvent(new Event("visibilitychange"));

    vi.advanceTimersByTime(5_000);
    expect(fetchAndSwapSpy).toHaveBeenCalledTimes(2);
  });

  it("fires an immediate fetch and resumes polling when document becomes visible again", () => {
    initMonitorForTest({ pollIntervalMs: 1_000 });

    setDocumentHidden(true);
    document.dispatchEvent(new Event("visibilitychange"));

    vi.advanceTimersByTime(3_000);
    // Only the initial init call; polling is paused while hidden
    expect(fetchAndSwapSpy).toHaveBeenCalledTimes(1);

    setDocumentHidden(false);
    document.dispatchEvent(new Event("visibilitychange"));

    // One immediate fetch fires on the visibility-return event.
    expect(fetchAndSwapSpy).toHaveBeenCalledTimes(2);

    // The interval is now running; each subsequent tick produces another fetch.
    vi.advanceTimersByTime(1_000);
    expect(fetchAndSwapSpy).toHaveBeenCalledTimes(3);

    vi.advanceTimersByTime(1_000);
    expect(fetchAndSwapSpy).toHaveBeenCalledTimes(4);
  });

  it("does not call fetchAndSwap when the snapshot region element is absent from the DOM", () => {
    document.body.innerHTML = "";

    initMonitorForTest({ pollIntervalMs: 1_000 });

    vi.advanceTimersByTime(5_000);
    expect(fetchAndSwapSpy).not.toHaveBeenCalled();
  });

  it("does not call fetchAndSwap when data-snapshot-url attribute is missing", () => {
    document.body.innerHTML = `<div id="${HEALTH_SNAPSHOT_REGION_ID}"></div>`;

    initMonitorForTest({ pollIntervalMs: 1_000 });

    vi.advanceTimersByTime(5_000);
    expect(fetchAndSwapSpy).not.toHaveBeenCalled();
  });

  it("uses the default poll interval when no argument is provided", () => {
    initMonitorForTest();

    // 1 call on init
    expect(fetchAndSwapSpy).toHaveBeenCalledTimes(1);

    vi.advanceTimersByTime(30_000);
    expect(fetchAndSwapSpy).toHaveBeenCalledTimes(2);
  });
});
