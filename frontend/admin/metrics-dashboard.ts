/**
 * Admin metrics dashboard controller.
 *
 * Owns the lifecycle of the dashboard page introduced in Step 2's template:
 *
 *   1. Initial fetch on `initMetricsDashboard()`.
 *   2. A 60 s polling interval that re-fetches all active panels.
 *   3. Manual Refresh button that aborts in-flight XHRs and restarts the
 *      interval.
 *   4. Window-selector buttons (Day / Week / Month / Year) that switch the
 *      query window and refetch.
 *   5. `visibilitychange` handling — polling halts when the tab is hidden and
 *      refetches on return if more than `VISIBILITY_REFETCH_THRESHOLD_MS` of
 *      monotonic time has elapsed since the last fetch.
 *
 * Per-section render functions (top table, summary) live in sibling modules
 * (`render-top-table.ts`, `render-summary.ts`). The timeseries chart is wired
 * to the panel state in Step 8 — Step 7 only handles summary + top-events.
 *
 * Implementation notes:
 *   - `_lastFetchPerf` uses `performance.now()` (monotonic, page-load-relative)
 *     because the visibility refetch threshold compares two in-page measurements.
 *     A wall-clock `Date.now()` would be susceptible to system clock drift and
 *     can run backwards (NTP step), which would produce negative deltas here.
 *   - `_inFlight` tracks the active jqXHR for each query so the Refresh button
 *     (and future event-selector switches) can abort cleanly.
 *   - The Refresh button uses `aria-disabled='true'` + `pointer-events: none`
 *     while in-flight; the button stays focusable for screen readers but
 *     ignores activation.
 */

import { APP_CONFIG } from "../lib/config.js";
import { $ } from "../lib/globals.js";
import { is429Handled } from "../lib/ajax.js";

import { fetchSummary, fetchTopEvents } from "./metrics-query-client.js";
import { renderSummary } from "./render-summary.js";
import { renderTopTable } from "./render-top-table.js";

type MetricsWindow = "day" | "week" | "month" | "year";
type MetricsCategory = "api" | "ui" | "domain";

interface InFlightRequests {
  top: JQuery.jqXHR | null;
  ts: JQuery.jqXHR | null;
  summary: JQuery.jqXHR | null;
}

const POLL_INTERVAL_MS = 60_000;
const VISIBILITY_REFETCH_THRESHOLD_MS = 5_000;

const DASHBOARD_ROOT_ID = "MetricsDashboard";
const REFRESH_BUTTON_ID = "MetricsRefreshNowBtn";
const ERROR_BANNER_ID = "MetricsErrorBanner";
const WINDOW_BUTTON_CLASS = "MetricsWindowButton";

const CATEGORY_PANEL_IDS: Record<
  MetricsCategory,
  { summary: string; tbody: string }
> = {
  api: { summary: "MetricsPanelApi-summary", tbody: "MetricsTopTableApi" },
  ui: { summary: "MetricsPanelUi-summary", tbody: "MetricsTopTableUi" },
  domain: {
    summary: "MetricsPanelDomain-summary",
    tbody: "MetricsTopTableDomain",
  },
};

// All three categories are kept warm by polling so tab switching is instant
// (Step 8 caches the results; Step 7 simply renders each panel on every fetch).
const ALL_CATEGORIES: readonly MetricsCategory[] = ["api", "ui", "domain"];

let _pollIntervalId: ReturnType<typeof setInterval> | null = null;
let _lastFetchPerf: number = 0;
let _currentWindow: MetricsWindow = "day";
let _inFlight: InFlightRequests = { top: null, ts: null, summary: null };

function getElementByIdOrNull<ElementT extends HTMLElement>(
  elementId: string,
): ElementT | null {
  return document.getElementById(elementId) as ElementT | null;
}

function setBannerVisible({ visible }: { visible: boolean }): void {
  const banner = getElementByIdOrNull<HTMLElement>(ERROR_BANNER_ID);
  if (banner === null) {
    return;
  }
  if (visible) {
    banner.classList.remove("hidden");
    banner.textContent = APP_CONFIG.strings.METRICS_FETCH_FAILED_BANNER;
  } else {
    banner.classList.add("hidden");
    banner.textContent = "";
  }
}

function setDashboardBusy({ busy }: { busy: boolean }): void {
  const root = getElementByIdOrNull<HTMLElement>(DASHBOARD_ROOT_ID);
  if (root === null) {
    return;
  }
  root.setAttribute("aria-busy", busy ? "true" : "false");
}

function setRefreshButtonInFlight({ inFlight }: { inFlight: boolean }): void {
  const button = getElementByIdOrNull<HTMLButtonElement>(REFRESH_BUTTON_ID);
  if (button === null) {
    return;
  }
  if (inFlight) {
    button.setAttribute("aria-disabled", "true");
    button.style.pointerEvents = "none";
  } else {
    button.removeAttribute("aria-disabled");
    button.style.pointerEvents = "";
  }
}

function abortInFlightRequests(): void {
  for (const key of ["top", "ts", "summary"] as const) {
    const xhr = _inFlight[key];
    if (xhr !== null) {
      xhr.abort();
      _inFlight[key] = null;
    }
  }
}

/**
 * Fire summary + per-category top-events for the current window. Each
 * `.done` callback renders the appropriate DOM region; `.fail` shows the
 * error banner (unless the 429 prefilter already replaced the page); every
 * settled response refreshes `_lastFetchPerf` for the visibility-refetch
 * heuristic.
 *
 * Step 7 deliberately omits the timeseries fetch — the per-event selector
 * arrives in Step 8 and there is no stable "default event" to query before
 * the user picks one.
 */
function fetchAll(): void {
  abortInFlightRequests();
  setDashboardBusy({ busy: true });
  setRefreshButtonInFlight({ inFlight: true });

  const summaryRequest = fetchSummary({ window: _currentWindow });
  _inFlight.summary = summaryRequest;
  summaryRequest
    .done((response) => {
      setBannerVisible({ visible: false });
      for (const category of ALL_CATEGORIES) {
        const summaryRoot = getElementByIdOrNull<HTMLElement>(
          CATEGORY_PANEL_IDS[category].summary,
        );
        if (summaryRoot !== null) {
          renderSummary({ root: summaryRoot, response, category });
        }
      }
    })
    .fail((xhr) => {
      if (is429Handled(xhr)) {
        return;
      }
      // Abort signals from `abortInFlightRequests()` arrive as `.fail()` with
      // a readyState of 0 — those aren't real failures, just cancellations,
      // so suppress the banner for them.
      if (xhr.readyState === 0) {
        return;
      }
      setBannerVisible({ visible: true });
    })
    .always(() => {
      _inFlight.summary = null;
      _lastFetchPerf = performance.now();
      onSettleAny();
    });

  for (const category of ALL_CATEGORIES) {
    const topRequest = fetchTopEvents({
      window: _currentWindow,
      category,
    });
    if (category === "api") {
      _inFlight.top = topRequest;
    }
    topRequest
      .done((response) => {
        setBannerVisible({ visible: false });
        const tbody = (
          getElementByIdOrNull<HTMLTableElement>(
            CATEGORY_PANEL_IDS[category].tbody,
          ) ?? null
        )?.querySelector("tbody");
        if (tbody !== null && tbody !== undefined) {
          renderTopTable({
            tbody: tbody as HTMLTableSectionElement,
            events: response.events,
          });
        }
      })
      .fail((xhr) => {
        if (is429Handled(xhr)) {
          return;
        }
        if (xhr.readyState === 0) {
          return;
        }
        setBannerVisible({ visible: true });
      })
      .always(() => {
        if (category === "api") {
          _inFlight.top = null;
        }
        _lastFetchPerf = performance.now();
        onSettleAny();
      });
  }
}

/**
 * Clear UI in-flight indicators when no requests remain pending. Both
 * `aria-busy` on the dashboard root and the Refresh button's `aria-disabled`
 * track the union of all three in-flight requests.
 */
function onSettleAny(): void {
  const anyInFlight =
    _inFlight.top !== null ||
    _inFlight.ts !== null ||
    _inFlight.summary !== null;
  if (!anyInFlight) {
    setDashboardBusy({ busy: false });
    setRefreshButtonInFlight({ inFlight: false });
  }
}

function startPolling(): void {
  if (_pollIntervalId !== null) {
    clearInterval(_pollIntervalId);
  }
  _pollIntervalId = setInterval(fetchAll, POLL_INTERVAL_MS);
}

function stopPolling(): void {
  if (_pollIntervalId !== null) {
    clearInterval(_pollIntervalId);
    _pollIntervalId = null;
  }
}

function handleVisibilityChange(): void {
  if (document.visibilityState === "hidden") {
    stopPolling();
    return;
  }
  if (document.visibilityState === "visible") {
    const elapsedMs = performance.now() - _lastFetchPerf;
    if (elapsedMs > VISIBILITY_REFETCH_THRESHOLD_MS) {
      fetchAll();
    }
    startPolling();
  }
}

function handleRefreshClick(event: JQuery.TriggeredEvent): void {
  const button = event.currentTarget as HTMLButtonElement;
  if (button.getAttribute("aria-disabled") === "true") {
    return;
  }
  fetchAll();
  startPolling();
}

function handleWindowChange({ window }: { window: MetricsWindow }): void {
  _currentWindow = window;
  const windowButtons = document.getElementsByClassName(WINDOW_BUTTON_CLASS);
  for (
    let buttonIndex = 0;
    buttonIndex < windowButtons.length;
    buttonIndex += 1
  ) {
    const buttonElement = windowButtons[buttonIndex] as HTMLButtonElement;
    const buttonWindow = buttonElement.dataset.window;
    buttonElement.setAttribute(
      "aria-pressed",
      buttonWindow === window ? "true" : "false",
    );
  }
  fetchAll();
  startPolling();
}

function handleWindowButtonClick(event: JQuery.TriggeredEvent): void {
  const button = event.currentTarget as HTMLButtonElement;
  const selectedWindow = button.dataset.window as MetricsWindow | undefined;
  if (selectedWindow === undefined) {
    return;
  }
  handleWindowChange({ window: selectedWindow });
}

export function initMetricsDashboard(): void {
  const dashboardRoot = getElementByIdOrNull<HTMLElement>(DASHBOARD_ROOT_ID);
  if (dashboardRoot === null) {
    return;
  }

  $(`.${WINDOW_BUTTON_CLASS}`).offAndOnExact("click", handleWindowButtonClick);
  $(`#${REFRESH_BUTTON_ID}`).offAndOnExact("click", handleRefreshClick);

  document.addEventListener("visibilitychange", handleVisibilityChange);

  fetchAll();
  startPolling();
}

/**
 * Test-only helper. Resets module-local state between tests so each spec runs
 * against a clean lifecycle. Not used in production — the dashboard is a
 * single-page surface initialized once per page load.
 */
export function _resetMetricsDashboardForTests(): void {
  stopPolling();
  abortInFlightRequests();
  _lastFetchPerf = 0;
  _currentWindow = "day";
  _inFlight = { top: null, ts: null, summary: null };
  document.removeEventListener("visibilitychange", handleVisibilityChange);
}
