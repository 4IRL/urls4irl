import htmx from "htmx.org";

export const HEALTH_SNAPSHOT_REGION_ID = "AdminHealthSnapshot";
export const HEALTH_REFRESH_EVENT = "refresh-health";
export const HEALTH_POLL_INTERVAL_MS = 30_000;

/**
 * Poll the health snapshot fragment every 30 seconds, pausing while the
 * tab is hidden and refreshing immediately on return.
 *
 * The polling clock lives here (not in an `hx-trigger="every 30s"`
 * attribute) so visibility pause/resume is deterministic and CSP-safe —
 * htmx event filters would require eval, which the app's CSP forbids.
 * The region declares `hx-trigger="load, refresh-health"` and this module
 * dispatches the `refresh-health` event on each tick.
 *
 * Returns a disposer that stops the poll clock and detaches the
 * visibilitychange listener (page code ignores it; tests use it to keep
 * monitors from accumulating across cases).
 */
export function initHealthMonitor({
  pollIntervalMs = HEALTH_POLL_INTERVAL_MS,
}: { pollIntervalMs?: number } = {}): () => void {
  const snapshotRegion = document.getElementById(HEALTH_SNAPSHOT_REGION_ID);
  if (snapshotRegion === null) {
    return () => {};
  }

  let pollTimer: number | null = null;

  const startPolling = (): void => {
    if (pollTimer !== null) {
      return;
    }
    pollTimer = window.setInterval(() => {
      htmx.trigger(snapshotRegion, HEALTH_REFRESH_EVENT);
    }, pollIntervalMs);
  };

  const stopPolling = (): void => {
    if (pollTimer === null) {
      return;
    }
    window.clearInterval(pollTimer);
    pollTimer = null;
  };

  const onVisibilityChange = (): void => {
    if (document.hidden) {
      stopPolling();
    } else {
      htmx.trigger(snapshotRegion, HEALTH_REFRESH_EVENT);
      startPolling();
    }
  };

  document.addEventListener("visibilitychange", onVisibilityChange);
  startPolling();

  return (): void => {
    stopPolling();
    document.removeEventListener("visibilitychange", onVisibilityChange);
  };
}
