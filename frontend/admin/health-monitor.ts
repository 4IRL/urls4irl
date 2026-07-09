/**
 * Health-snapshot polling controller for the admin /admin/health page.
 *
 * Fetches the server-rendered health snapshot fragment and swaps it into
 * #AdminHealthSnapshot using native jQuery AJAX (via fetchAndSwap):
 *   - immediate fetch on init
 *   - 30-second interval poll
 *   - visibility-aware: pauses when the tab is hidden, fires an immediate
 *     fetch and resumes on return
 *
 * The snapshot URL is read from the `data-snapshot-url` attribute on
 * #AdminHealthSnapshot (set by the Jinja template via url_for).
 *
 * Returns a disposer that stops the poll clock and detaches the
 * visibilitychange listener (page code ignores it; tests use it to keep
 * monitors from accumulating across cases).
 */

import { fetchAndSwap } from "./fragment-swap.js";

export const HEALTH_SNAPSHOT_REGION_ID = "AdminHealthSnapshot";
export const HEALTH_POLL_INTERVAL_MS = 30_000;

export function initHealthMonitor({
  pollIntervalMs = HEALTH_POLL_INTERVAL_MS,
}: { pollIntervalMs?: number } = {}): () => void {
  const snapshotRegion = document.getElementById(HEALTH_SNAPSHOT_REGION_ID);
  if (snapshotRegion === null) {
    return () => {};
  }

  const snapshotUrl = snapshotRegion.dataset.snapshotUrl;
  if (!snapshotUrl) {
    return () => {};
  }

  const doFetch = (): void => {
    fetchAndSwap({ url: snapshotUrl, targetEl: snapshotRegion });
  };

  let pollTimer: number | null = null;

  const startPolling = (): void => {
    if (pollTimer !== null) {
      return;
    }
    pollTimer = window.setInterval(doFetch, pollIntervalMs);
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
      doFetch();
      startPolling();
    }
  };

  doFetch();
  document.addEventListener("visibilitychange", onVisibilityChange);
  startPolling();

  return (): void => {
    stopPolling();
    document.removeEventListener("visibilitychange", onVisibilityChange);
  };
}
