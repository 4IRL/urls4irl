/**
 * Polling + visibility lifecycle tests for the health-monitor controller.
 *
 * htmx is fully mocked so the spec exercises only the setInterval cadence
 * and the visibilitychange pause/resume semantics. vi.useFakeTimers() is
 * installed in beforeEach BEFORE initHealthMonitor() is called so the
 * initial startPolling() call is counted by the fake-timer infrastructure.
 */

const { htmxTriggerSpy } = vi.hoisted(() => ({
  htmxTriggerSpy: vi.fn(),
}));

vi.mock("htmx.org", () => ({
  default: {
    trigger: htmxTriggerSpy,
  },
}));

import {
  HEALTH_REFRESH_EVENT,
  HEALTH_SNAPSHOT_REGION_ID,
  initHealthMonitor,
} from "../health-monitor.js";

const SNAPSHOT_REGION_HTML = `<div id="${HEALTH_SNAPSHOT_REGION_ID}"></div>`;

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
    htmxTriggerSpy.mockReset();
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

  it("fires htmx.trigger once per interval tick after init", () => {
    initMonitorForTest({ pollIntervalMs: 1_000 });

    expect(htmxTriggerSpy).not.toHaveBeenCalled();

    vi.advanceTimersByTime(1_000);
    expect(htmxTriggerSpy).toHaveBeenCalledTimes(1);

    vi.advanceTimersByTime(1_000);
    expect(htmxTriggerSpy).toHaveBeenCalledTimes(2);
  });

  it("calls htmx.trigger with the snapshot region element and the refresh event name", () => {
    initMonitorForTest({ pollIntervalMs: 1_000 });

    vi.advanceTimersByTime(1_000);

    const snapshotRegion = document.getElementById(HEALTH_SNAPSHOT_REGION_ID);
    expect(htmxTriggerSpy).toHaveBeenCalledWith(
      snapshotRegion,
      HEALTH_REFRESH_EVENT,
    );
  });

  it("stops firing triggers when document becomes hidden", () => {
    initMonitorForTest({ pollIntervalMs: 1_000 });

    vi.advanceTimersByTime(1_000);
    expect(htmxTriggerSpy).toHaveBeenCalledTimes(1);

    setDocumentHidden(true);
    document.dispatchEvent(new Event("visibilitychange"));

    vi.advanceTimersByTime(5_000);
    expect(htmxTriggerSpy).toHaveBeenCalledTimes(1);
  });

  it("fires an immediate trigger and resumes polling when document becomes visible again", () => {
    initMonitorForTest({ pollIntervalMs: 1_000 });

    setDocumentHidden(true);
    document.dispatchEvent(new Event("visibilitychange"));

    vi.advanceTimersByTime(3_000);
    expect(htmxTriggerSpy).not.toHaveBeenCalled();

    setDocumentHidden(false);
    document.dispatchEvent(new Event("visibilitychange"));

    // One immediate trigger fires on the visibility-return event.
    expect(htmxTriggerSpy).toHaveBeenCalledTimes(1);

    // The interval is now running; each subsequent tick produces another trigger.
    vi.advanceTimersByTime(1_000);
    expect(htmxTriggerSpy).toHaveBeenCalledTimes(2);

    vi.advanceTimersByTime(1_000);
    expect(htmxTriggerSpy).toHaveBeenCalledTimes(3);
  });

  it("does not call htmx.trigger when the snapshot region element is absent from the DOM", () => {
    document.body.innerHTML = "";

    initMonitorForTest({ pollIntervalMs: 1_000 });

    vi.advanceTimersByTime(5_000);
    expect(htmxTriggerSpy).not.toHaveBeenCalled();
  });

  it("uses the default poll interval when no argument is provided", () => {
    // Explicitly test that the zero-argument path does not throw. The default
    // interval is 30 000 ms; advance past one tick to confirm the trigger fires.
    initMonitorForTest();

    vi.advanceTimersByTime(30_000);
    expect(htmxTriggerSpy).toHaveBeenCalledTimes(1);
  });
});
