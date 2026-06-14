/**
 * Admin metrics dashboard controller.
 *
 * Owns the lifecycle of the admin metrics dashboard page (`pages/admin_metrics.html`):
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
 *   6. Section tablist (API / UI / Domain) with ARIA APG behavior (arrow-key
 *      navigation, roving tabindex, panel show/hide). The active panel's
 *      cached payload re-renders on tab activation; polling keeps all three
 *      caches warm so switching tabs is instant.
 *   7. Per-panel timeseries event selector (`<select>` rendered from the
 *      cached top-events list). Picking a different event fires the
 *      timeseries XHR and re-renders the panel's chart.
 *   8. "Last flush N seconds ago" badge — a 1 s wall-clock ticker updates
 *      `#MetricsLastFlush` based on the elapsed time since
 *      `summary.last_flush_at`. The visible text refreshes every tick;
 *      aria-live announcements fire only when the elapsed bucket transitions
 *      (just_now → seconds → minutes → stale).
 *
 * Per-section render functions (top table, summary, timeseries chart) live in
 * sibling modules (`render-top-table.ts`, `render-summary.ts`,
 * `render-timeseries-chart.ts`).
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
 *   - `_topCache` stores the last successful `TopEventsResponseSchema` for
 *     each category so tab switches do not require a network round trip and
 *     the per-panel `<select>` can be re-rendered on every successful fetch
 *     without re-issuing a request.
 */

import type { Schema } from "../types/api-helpers.d.ts";
import type { FlowId } from "../types/metrics-flows.js";
import { FLOW_IDS } from "../types/metrics-flows.js";
import {
  RESOURCES,
  RESOURCES_BY_CATEGORY,
  type ResourceName,
} from "../types/metrics-resources.js";

import { APP_CONFIG } from "../lib/config.js";
import { $ } from "../lib/globals.js";
import { is429Handled } from "../lib/ajax.js";

import { renderFlowGrid } from "./flow-card.js";
import {
  fetchFlow,
  fetchGroupedTimeseries,
  fetchSummary,
  fetchTimeseries,
  fetchTopEvents,
} from "./metrics-query-client.js";
import {
  _resetPaneResizersForTests,
  initPaneResizers,
} from "./pane-resizer.js";
import { renderPipelineHealthChart } from "./render-pipeline-health-chart.js";
import { renderSummary } from "./render-summary.js";
import { renderTimeseriesChart } from "./render-timeseries-chart.js";
import { renderTopTable } from "./render-top-table.js";

export type MetricsWindow = "day" | "week" | "month" | "year";

// Single source of truth for the tab-identifier strings that cross the
// template↔TS boundary: the template renders `data-tab="flows"` (etc.) and this
// module reads `dataset.tab` and compares against these values. `api`/`ui`/
// `domain` mirror the backend `EventCategory`; `flows`/`pipeline_health` are
// frontend-only dashboard views with no backend equivalent.
const TAB = {
  API: "api",
  UI: "ui",
  DOMAIN: "domain",
  FLOWS: "flows",
  PIPELINE_HEALTH: "pipeline_health",
} as const;
type MetricsCategory = typeof TAB.API | typeof TAB.UI | typeof TAB.DOMAIN;
type MetricsTabId =
  | MetricsCategory
  | typeof TAB.FLOWS
  | typeof TAB.PIPELINE_HEALTH;
type TopEventsResponseSchema = Schema<"TopEventsResponseSchema">;
type FlowResponseSchema = Schema<"FlowResponseSchema">;
type LastFlushBucket =
  | "just_now"
  | "seconds"
  | "minutes"
  | "stale_minutes"
  | "stale_hours";
type LastEventBucket = "just_now" | "seconds" | "minutes" | "hours";

interface InFlightRequests {
  topApi: JQuery.jqXHR | null;
  topUi: JQuery.jqXHR | null;
  topDomain: JQuery.jqXHR | null;
  tsApi: JQuery.jqXHR | null;
  tsUi: JQuery.jqXHR | null;
  tsDomain: JQuery.jqXHR | null;
  summary: JQuery.jqXHR | null;
  pipelineHealth: JQuery.jqXHR | null;
  flowCreateUtub: JQuery.jqXHR | null;
  flowAddUrl: JQuery.jqXHR | null;
  flowRegister: JQuery.jqXHR | null;
  flowLogin: JQuery.jqXHR | null;
}

interface CategoryPanelIds {
  tbody: string;
  chart: string;
  select: string;
  tab: string;
  panel: string;
  resourceFilter: string;
  deviceFilter: string;
  substringFilter: string;
}

// Display label per `Resource` enum value. Keys must stay aligned with the
// generated `RESOURCES` const — the boot-time `populateResourceFilter` walk
// reads this map for every option label, so a missing key would render an
// empty `<option>`.
const RESOURCE_LABELS: Record<ResourceName, string> = {
  [RESOURCES.UTUB]: APP_CONFIG.strings.METRICS_TOP_RESOURCE_UTUB,
  [RESOURCES.URL]: APP_CONFIG.strings.METRICS_TOP_RESOURCE_URL,
  [RESOURCES.TAG]: APP_CONFIG.strings.METRICS_TOP_RESOURCE_TAG,
  [RESOURCES.MEMBER]: APP_CONFIG.strings.METRICS_TOP_RESOURCE_MEMBER,
  [RESOURCES.AUTH]: APP_CONFIG.strings.METRICS_TOP_RESOURCE_AUTH,
  [RESOURCES.SEARCH]: APP_CONFIG.strings.METRICS_TOP_RESOURCE_SEARCH,
  [RESOURCES.FORM]: APP_CONFIG.strings.METRICS_TOP_RESOURCE_FORM,
  [RESOURCES.DECK]: APP_CONFIG.strings.METRICS_TOP_RESOURCE_DECK,
  [RESOURCES.NAV]: APP_CONFIG.strings.METRICS_TOP_RESOURCE_NAV,
  [RESOURCES.ERROR]: APP_CONFIG.strings.METRICS_TOP_RESOURCE_ERROR,
  [RESOURCES.CONTACT]: APP_CONFIG.strings.METRICS_TOP_RESOURCE_CONTACT,
  [RESOURCES.ADMIN]: APP_CONFIG.strings.METRICS_TOP_RESOURCE_ADMIN,
  [RESOURCES.OTHER]: APP_CONFIG.strings.METRICS_TOP_RESOURCE_OTHER,
};

const POLL_INTERVAL_MS = 60_000;
const VISIBILITY_REFETCH_THRESHOLD_MS = 5_000;
const BADGE_TICK_INTERVAL_MS = 1_000;
// When any per-tab filter (resource or substring) is active, bump the top
// request's `limit` so the client-side substring filter has a wider pool of
// rows to narrow. 100 matches the server-side cap on `TopEventsQuerySchema.limit`.
const FILTERED_TOP_LIMIT = 100;
// Substring input is debounced via `performance.now()` so repeated keystrokes
// collapse to one re-render. Monotonic vs `Date.now()` so a system-clock step
// cannot cause a debounced re-render to fire late or never.
const SUBSTRING_DEBOUNCE_MS = 150;
// Shared bucket thresholds: "just_now" until 5 s elapsed, "seconds" until 60 s,
// then "minutes" until the badge-specific upper bound. After that, each badge
// diverges — see FLUSH_STALE_AT_MS (worker liveness) and EVENT_HOURS_AT_MS
// (data freshness).
const BADGE_BUCKET_SECONDS_MS = 5_000;
const BADGE_BUCKET_MINUTES_MS = 60_000;
// Last flush goes "stale" at 2 min: the worker runs every 60 s, so anything
// older than two cron ticks indicates a genuine problem with the pipeline.
const FLUSH_STALE_AT_MS = 120_000;
const FLUSH_STALE_HOURS_AT_MS = 3_600_000;
// Last event uses hours as a unit beyond 1 h — but NEVER paints itself stale,
// because hours-old data is normal during low-traffic stretches.
const EVENT_HOURS_AT_MS = 3_600_000;
const BADGE_STALE_CLASS = "MetricsBadgeStale";

const DASHBOARD_ROOT_ID = "MetricsDashboard";
const REFRESH_BUTTON_ID = "MetricsRefreshNowBtn";
const ERROR_BANNER_ID = "MetricsErrorBanner";
const LAST_FLUSH_BADGE_ID = "MetricsLastFlush";
const LAST_FLUSH_TEXT_ID = "MetricsLastFlushText";
const LAST_FLUSH_ANNOUNCEMENT_ID = "MetricsLastFlushAnnouncement";
const LAST_EVENT_BADGE_ID = "MetricsLastEvent";
const LAST_EVENT_TEXT_ID = "MetricsLastEventText";
const LAST_EVENT_ANNOUNCEMENT_ID = "MetricsLastEventAnnouncement";
const WINDOW_BUTTON_CLASS = "MetricsWindowButton";
const TABLIST_ID = "MetricsTablist";
const TAB_ROLE_SELECTOR = '[role="tab"]';

const CATEGORY_PANEL_IDS: Record<MetricsCategory, CategoryPanelIds> = {
  api: {
    tbody: "MetricsTopTableApi",
    chart: "MetricsChartApi",
    select: "MetricsTimeseriesEventApi",
    tab: "MetricsTabApi",
    panel: "MetricsPanelApi",
    resourceFilter: "MetricsTopResourceFilter-api",
    deviceFilter: "MetricsTopDeviceFilter-api",
    substringFilter: "MetricsTopSubstringFilter-api",
  },
  ui: {
    tbody: "MetricsTopTableUi",
    chart: "MetricsChartUi",
    select: "MetricsTimeseriesEventUi",
    tab: "MetricsTabUi",
    panel: "MetricsPanelUi",
    resourceFilter: "MetricsTopResourceFilter-ui",
    deviceFilter: "MetricsTopDeviceFilter-ui",
    substringFilter: "MetricsTopSubstringFilter-ui",
  },
  domain: {
    tbody: "MetricsTopTableDomain",
    chart: "MetricsChartDomain",
    select: "MetricsTimeseriesEventDomain",
    tab: "MetricsTabDomain",
    panel: "MetricsPanelDomain",
    resourceFilter: "MetricsTopResourceFilter-domain",
    deviceFilter: "MetricsTopDeviceFilter-domain",
    substringFilter: "MetricsTopSubstringFilter-domain",
  },
};

// All three categories are kept warm by polling so tab switching is instant.
// Each `.done(...)` writes to `_topCache` and re-renders the panel.
// Tablist navigation order also matches DOM order: API → UI → Domain.
const CATEGORIES: readonly MetricsCategory[] = [TAB.API, TAB.UI, TAB.DOMAIN];

// All tabs in DOM order. Flows and Pipeline Health are tabs but not categories
// — each has its own panel + fetch path, separate from the per-category
// top-events / timeseries flow. Keeping them out of `CATEGORIES` avoids having
// to add null-branches for the category-specific caches (`_topCache`, filters,
// charts) every time a category iteration is needed. Pipeline Health is always
// the last tab; Flows precedes it, matching the DOM order in
// `pages/admin_metrics.html`.
const TAB_IDS: readonly MetricsTabId[] = [
  ...CATEGORIES,
  TAB.FLOWS,
  TAB.PIPELINE_HEALTH,
];

const PIPELINE_HEALTH_TAB_ID: string = "MetricsTabPipelineHealth";
const PIPELINE_HEALTH_PANEL_ID: string = "MetricsPanelPipelineHealth";
const FLOWS_TAB_ID: string = "MetricsTabFlows";
const FLOWS_PANEL_ID: string = "MetricsPanelFlows";
const FLOWS_GRID_ID: string = "MetricsFlowGrid";
const FLOWS_ANNOUNCEMENT_ID: string = "MetricsPanelFlowsAnnouncement";

// Maps each FlowId to its dedicated in-flight slot so per-flow XHRs are aborted
// independently (mirrors TOP_SLOT_BY_CATEGORY).
const FLOW_SLOT_BY_FLOW_ID: Record<
  FlowId,
  "flowCreateUtub" | "flowAddUrl" | "flowRegister" | "flowLogin"
> = {
  [FLOW_IDS.CREATE_UTUB]: "flowCreateUtub",
  [FLOW_IDS.ADD_URL_TO_UTUB]: "flowAddUrl",
  [FLOW_IDS.REGISTER]: "flowRegister",
  [FLOW_IDS.LOGIN]: "flowLogin",
};

function getTabAndPanelIds(tabId: MetricsTabId): {
  tab: string;
  panel: string;
} {
  if (tabId === TAB.PIPELINE_HEALTH) {
    return { tab: PIPELINE_HEALTH_TAB_ID, panel: PIPELINE_HEALTH_PANEL_ID };
  }
  if (tabId === TAB.FLOWS) {
    return { tab: FLOWS_TAB_ID, panel: FLOWS_PANEL_ID };
  }
  return {
    tab: CATEGORY_PANEL_IDS[tabId].tab,
    panel: CATEGORY_PANEL_IDS[tabId].panel,
  };
}

let _pollIntervalId: ReturnType<typeof setInterval> | null = null;
let _lastFetchPerf: number = 0;
let _currentWindow: MetricsWindow = "day";
let _currentCategory: MetricsCategory = TAB.API;
// The currently-visible tab. Distinct from `_currentCategory` (which only ever
// holds true `MetricsCategory` values) so the Flows-fetch gate can key on tab
// visibility without widening the category type. Set unconditionally for every
// tab in `handleTabClick`.
let _activeTab: MetricsTabId = TAB.API;
let _inFlight: InFlightRequests = {
  topApi: null,
  topUi: null,
  topDomain: null,
  tsApi: null,
  tsUi: null,
  tsDomain: null,
  summary: null,
  pipelineHealth: null,
  flowCreateUtub: null,
  flowAddUrl: null,
  flowRegister: null,
  flowLogin: null,
};
// Last successful `/flow` response per flow id, so a tab switch back to Flows
// renders instantly from cache. Populated by `fetchFlows`.
let _flowCache: Partial<Record<FlowId, FlowResponseSchema>> = {};

const TOP_SLOT_BY_CATEGORY: Record<
  MetricsCategory,
  "topApi" | "topUi" | "topDomain"
> = {
  api: "topApi",
  ui: "topUi",
  domain: "topDomain",
};
// Per-category slots so a background prefetch for an inactive tab is not
// aborted when the active tab's request settles.
const TS_SLOT_BY_CATEGORY: Record<
  MetricsCategory,
  "tsApi" | "tsUi" | "tsDomain"
> = {
  api: "tsApi",
  ui: "tsUi",
  domain: "tsDomain",
};
const _topCache: Map<MetricsCategory, TopEventsResponseSchema> = new Map();
// Tracks the user's most-recent event selection per category. Source of truth
// for the top-table row highlight (aria-current), used both when a polling
// refresh re-renders the table and when the user switches tabs.
const _selectedEventByCategory: Map<MetricsCategory, string> = new Map();
// Per-tab filter state. Both maps survive tab switches inside one session;
// `_resetMetricsDashboardForTests` clears them.
const _resourceFilterByCategory: Map<MetricsCategory, ResourceName> = new Map();
const _deviceFilterByCategory: Map<MetricsCategory, 1 | 2> = new Map();
const _substringFilterByCategory: Map<MetricsCategory, string> = new Map();
// Debounce handles per category; cleared whenever a fresh keystroke arrives.
const _substringDebounceTimerByCategory: Map<
  MetricsCategory,
  ReturnType<typeof setTimeout>
> = new Map();
const _deviceFilterDebounceTimerByCategory: Map<
  MetricsCategory,
  ReturnType<typeof setTimeout>
> = new Map();
// Records the window each category's chart was last fetched against. When the
// user changes window (Day → Week, etc.), `_currentWindow` advances but each
// panel's chart still shows old-window data until the timeseries re-fetches —
// so `ensureDefaultSelection` re-triggers the change handler whenever this
// map's value diverges from `_currentWindow`, even when the user's event
// selection is still valid.
const _chartFetchedWindowByCategory: Map<MetricsCategory, MetricsWindow> =
  new Map();

// Badge state. Both `_lastFlushAtMs` and `_lastEventAtMs` are wall-clock epochs
// parsed from the server's `summary.last_flush_at` / `summary.last_event_at`,
// so the elapsed delta MUST be computed with `Date.now()` — `performance.now()`
// is page-load-relative and would yield a nonsense delta when subtracted from
// a wall-clock value.
let _badgeIntervalId: ReturnType<typeof setInterval> | null = null;
let _lastFlushAtMs: number | null = null;
let _lastAnnouncedFlushBucket: LastFlushBucket | null = null;
let _lastEventAtMs: number | null = null;
let _lastAnnouncedEventBucket: LastEventBucket | null = null;

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

// Flow XHR settle-state is tracked separately from the global dashboard busy
// path (DD-10): set/clear `aria-busy` on the Flows panel only, so the
// per-flow loading spinner reveals without coupling to the root dashboard
// fetch. When `busy` clears, the panel-scoped `aria-busy` attribute is removed
// entirely so the `[aria-busy="true"]` spinner selector stops matching.
function setFlowsPanelBusy({ busy }: { busy: boolean }): void {
  const panel = getElementByIdOrNull<HTMLElement>(FLOWS_PANEL_ID);
  if (panel === null) {
    return;
  }
  if (busy) {
    panel.setAttribute("aria-busy", "true");
  } else {
    panel.removeAttribute("aria-busy");
  }
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

// Per-tab label for the second column header of the Top Events table. The
// column shows different content per tab (HTTP endpoints on API; event names
// on UI/Domain), so the header text follows suit instead of saying "Endpoint"
// everywhere.
function topTableNameHeader({
  category,
}: {
  category: MetricsCategory;
}): string {
  if (category === TAB.API) {
    return APP_CONFIG.strings.METRICS_TOP_TABLE_HEADER_ENDPOINT;
  }
  if (category === TAB.DOMAIN) {
    return APP_CONFIG.strings.METRICS_TOP_TABLE_HEADER_ACTION;
  }
  return APP_CONFIG.strings.METRICS_TOP_TABLE_HEADER_EVENT;
}

function effectiveTopLimit({
  category,
}: {
  category: MetricsCategory;
}): number {
  const hasResource = _resourceFilterByCategory.has(category);
  const hasSubstring = (_substringFilterByCategory.get(category) ?? "") !== "";
  const hasDevice = _deviceFilterByCategory.has(category);
  return hasResource || hasSubstring || hasDevice ? FILTERED_TOP_LIMIT : 10;
}

/**
 * Populate a panel's resource `<select>` with the "All" option plus one option
 * per resource in `RESOURCES_BY_CATEGORY[category]`. Restores any previously-
 * applied selection so the dropdown stays consistent across re-renders.
 */
function populateResourceFilter({
  category,
}: {
  category: MetricsCategory;
}): void {
  const selectElement = getElementByIdOrNull<HTMLSelectElement>(
    CATEGORY_PANEL_IDS[category].resourceFilter,
  );
  if (selectElement === null) {
    return;
  }
  while (selectElement.firstChild !== null) {
    selectElement.removeChild(selectElement.firstChild);
  }
  const allOption = document.createElement("option");
  allOption.value = "";
  allOption.textContent = APP_CONFIG.strings.METRICS_TOP_RESOURCE_ALL;
  selectElement.appendChild(allOption);
  for (const resource of RESOURCES_BY_CATEGORY[category]) {
    const option = document.createElement("option");
    option.value = resource;
    option.textContent = RESOURCE_LABELS[resource];
    selectElement.appendChild(option);
  }
  const currentResource = _resourceFilterByCategory.get(category);
  selectElement.value = currentResource ?? "";
}

/**
 * Populate a panel's device `<select>` with the "All devices" option plus
 * Mobile and Desktop options. Restores any previously-applied selection so the
 * dropdown stays consistent across re-renders.
 */
function populateDeviceFilter({
  category,
}: {
  category: MetricsCategory;
}): void {
  const selectElement = getElementByIdOrNull<HTMLSelectElement>(
    CATEGORY_PANEL_IDS[category].deviceFilter,
  );
  if (selectElement === null) {
    return;
  }
  while (selectElement.firstChild !== null) {
    selectElement.removeChild(selectElement.firstChild);
  }
  const allOption = document.createElement("option");
  allOption.value = "";
  allOption.textContent = APP_CONFIG.strings.METRICS_TOP_DEVICE_ALL;
  selectElement.appendChild(allOption);
  const mobileOption = document.createElement("option");
  mobileOption.value = String(APP_CONFIG.constants.DEVICE_TYPE.MOBILE);
  mobileOption.textContent = APP_CONFIG.strings.METRICS_TOP_DEVICE_MOBILE;
  selectElement.appendChild(mobileOption);
  const desktopOption = document.createElement("option");
  desktopOption.value = String(APP_CONFIG.constants.DEVICE_TYPE.DESKTOP);
  desktopOption.textContent = APP_CONFIG.strings.METRICS_TOP_DEVICE_DESKTOP;
  selectElement.appendChild(desktopOption);
  const currentDevice = _deviceFilterByCategory.get(category);
  selectElement.value =
    currentDevice !== undefined ? String(currentDevice) : "";
}

function refetchTopForCategory({
  category,
}: {
  category: MetricsCategory;
}): void {
  const slot = TOP_SLOT_BY_CATEGORY[category];
  const previousRequest = _inFlight[slot];
  if (previousRequest !== null) {
    previousRequest.abort();
    _inFlight[slot] = null;
  }
  setDashboardBusy({ busy: true });
  setRefreshButtonInFlight({ inFlight: true });
  const resource = _resourceFilterByCategory.get(category) ?? null;
  const deviceType = _deviceFilterByCategory.get(category) ?? null;
  const request = fetchTopEvents({
    window: _currentWindow,
    category,
    resource,
    deviceType,
    limit: effectiveTopLimit({ category }),
  });
  _inFlight[slot] = request;
  request
    .done((response) => {
      setBannerVisible({ visible: false });
      _topCache.set(category, response);
      renderCategoryPanelFromCache({ category });
      ensureDefaultSelection({ category, response });
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
      _inFlight[slot] = null;
      _lastFetchPerf = performance.now();
      onSettleAny();
    });
}

function handleResourceFilterChange(event: JQuery.TriggeredEvent): void {
  const selectElement = event.currentTarget as HTMLSelectElement;
  const dataCategory = selectElement.dataset.category as
    | MetricsCategory
    | undefined;
  if (dataCategory === undefined) {
    return;
  }
  if (selectElement.value === "") {
    _resourceFilterByCategory.delete(dataCategory);
  } else {
    _resourceFilterByCategory.set(
      dataCategory,
      selectElement.value as ResourceName,
    );
  }
  refetchTopForCategory({ category: dataCategory });
}

// Device-filter debounce window: collapse rapid `<select>` changes (e.g. when
// the user spins through the dropdown with arrow keys) into a single refetch.
// 50ms is short enough to feel instant on a single change yet long enough to
// suppress repeat fires from native dropdown keyboard navigation.
const DEVICE_FILTER_DEBOUNCE_MS = 50;

function handleDeviceFilterChange(event: JQuery.TriggeredEvent): void {
  const selectElement = event.currentTarget as HTMLSelectElement;
  const dataCategory = selectElement.dataset.category as
    | MetricsCategory
    | undefined;
  if (dataCategory === undefined) {
    return;
  }
  const rawValue = selectElement.value;

  const existingTimer = _deviceFilterDebounceTimerByCategory.get(dataCategory);
  if (existingTimer !== undefined) {
    clearTimeout(existingTimer);
  }
  const timer = setTimeout(() => {
    _deviceFilterDebounceTimerByCategory.delete(dataCategory);
    if (rawValue === "") {
      _deviceFilterByCategory.delete(dataCategory);
    } else {
      const parsedValue = Number(rawValue) as 1 | 2;
      _deviceFilterByCategory.set(dataCategory, parsedValue);
    }
    refetchTopForCategory({ category: dataCategory });
    const tsSelect = getElementByIdOrNull<HTMLSelectElement>(
      CATEGORY_PANEL_IDS[dataCategory].select,
    );
    if (tsSelect !== null && tsSelect.value !== "") {
      $(tsSelect).trigger("change");
    }
  }, DEVICE_FILTER_DEBOUNCE_MS);
  _deviceFilterDebounceTimerByCategory.set(dataCategory, timer);
}

function handleSubstringFilterInput(event: JQuery.TriggeredEvent): void {
  const inputElement = event.currentTarget as HTMLInputElement;
  const dataCategory = inputElement.dataset.category as
    | MetricsCategory
    | undefined;
  if (dataCategory === undefined) {
    return;
  }
  const previousQuery = _substringFilterByCategory.get(dataCategory) ?? "";
  const nextQuery = inputElement.value;
  _substringFilterByCategory.set(dataCategory, nextQuery);

  const previousTimer = _substringDebounceTimerByCategory.get(dataCategory);
  if (previousTimer !== undefined) {
    clearTimeout(previousTimer);
  }
  // If toggling between "any filter active" and "no filter active", the
  // effective limit changes, so a refetch is required to widen / restore
  // the server's row pool. A pure-typing change inside the same active-state
  // is debounced into a client-side re-render only.
  //
  // The previously/now-active comparison is evaluated *inside* the timer so
  // it reads the resource-filter state at fire time. If the user toggles a
  // resource chip between keystroke and the timer firing, the refetch-vs-
  // rerender decision must reflect the chip state as of the timer fire.
  const timer = setTimeout(() => {
    _substringDebounceTimerByCategory.delete(dataCategory);
    const previouslyActive =
      previousQuery !== "" ||
      _resourceFilterByCategory.has(dataCategory) ||
      _deviceFilterByCategory.has(dataCategory);
    const nowActive =
      nextQuery !== "" ||
      _resourceFilterByCategory.has(dataCategory) ||
      _deviceFilterByCategory.has(dataCategory);
    const limitWillChange = previouslyActive !== nowActive;
    if (limitWillChange) {
      refetchTopForCategory({ category: dataCategory });
      return;
    }
    renderCategoryPanelFromCache({ category: dataCategory });
  }, SUBSTRING_DEBOUNCE_MS);
  _substringDebounceTimerByCategory.set(dataCategory, timer);
}

function abortInFlightRequests(): void {
  for (const key of [
    "topApi",
    "topUi",
    "topDomain",
    "tsApi",
    "tsUi",
    "tsDomain",
    "summary",
    "pipelineHealth",
    "flowCreateUtub",
    "flowAddUrl",
    "flowRegister",
    "flowLogin",
  ] as const) {
    const xhr = _inFlight[key];
    if (xhr !== null) {
      xhr.abort();
      _inFlight[key] = null;
    }
  }
}

/**
 * Render the per-panel `<select>` from the cached top-events list. The select
 * is rebuilt in place on every successful top fetch so the option set reflects
 * the latest window/category. The currently-selected event name (if any) is
 * preserved across rebuilds when the event still appears in the new options.
 *
 * WCAG 4.1.2: `<select>` requires a programmatically associated label. We
 * apply `aria-label` here (not in Jinja) because the select is JS-rendered.
 */
function renderTimeseriesSelect({
  category,
  response,
  filterQuery,
}: {
  category: MetricsCategory;
  response: TopEventsResponseSchema;
  filterQuery?: string;
}): void {
  const selectElement = getElementByIdOrNull<HTMLSelectElement>(
    CATEGORY_PANEL_IDS[category].select,
  );
  if (selectElement === null) {
    return;
  }

  const previousValue = selectElement.value;
  while (selectElement.firstChild !== null) {
    selectElement.removeChild(selectElement.firstChild);
  }
  selectElement.setAttribute(
    "aria-label",
    APP_CONFIG.strings.METRICS_TIMESERIES_SELECT_ARIA,
  );

  const normalizedNeedle =
    filterQuery !== undefined ? filterQuery.trim().toLowerCase() : "";
  const visibleEvents =
    normalizedNeedle === ""
      ? response.events
      : response.events.filter(
          (event) =>
            event.event_name.toLowerCase().includes(normalizedNeedle) ||
            event.description.toLowerCase().includes(normalizedNeedle),
        );

  for (const event of visibleEvents) {
    const optionElement = document.createElement("option");
    optionElement.value = event.event_name;
    optionElement.textContent = event.event_name;
    // For the API tab, `event_name` is the "<METHOD> <url_pattern>" string
    // built by query_service for display — the real DB event_name is always
    // "api_hit", and the (endpoint, method) pair lives in flat columns. We
    // stash all three on the option so the timeseries handler can issue a
    // properly-filtered query without re-parsing the displayed label.
    if (category === TAB.API) {
      const [methodPart] = event.event_name.split(" ", 1);
      optionElement.dataset.eventName = "api_hit";
      if (event.api_endpoint !== null && event.api_endpoint !== undefined) {
        optionElement.dataset.endpoint = event.api_endpoint;
      }
      optionElement.dataset.method = methodPart;
    } else {
      optionElement.dataset.eventName = event.event_name;
    }
    selectElement.appendChild(optionElement);
  }

  // Restore the previously-selected event when possible so polling refreshes
  // (and substring narrowing where the selection still matches) do not silently
  // change the active timeseries series.
  if (previousValue !== "") {
    const matchingEvent = visibleEvents.find(
      (event) => event.event_name === previousValue,
    );
    if (matchingEvent !== undefined) {
      selectElement.value = previousValue;
    }
  }
}

/**
 * Apply a cached top-events payload to a category's panel: re-render the top
 * table, refresh the `<select>` options, and rebind the change handler via
 * `offAndOnExact` so duplicate bindings cannot accumulate across re-renders.
 */
function renderCategoryPanelFromCache({
  category,
}: {
  category: MetricsCategory;
}): void {
  const cachedResponse = _topCache.get(category);
  if (cachedResponse === undefined) {
    return;
  }

  const substringFilter = _substringFilterByCategory.get(category) ?? "";

  const tableElement = getElementByIdOrNull<HTMLTableElement>(
    CATEGORY_PANEL_IDS[category].tbody,
  );
  const tbody = tableElement?.querySelector("tbody") ?? null;
  if (tbody !== null) {
    renderTopTable({
      tbody: tbody as HTMLTableSectionElement,
      events: cachedResponse.events,
      selectedEventName: _selectedEventByCategory.get(category) ?? null,
      filterQuery: substringFilter,
      nameHeader: topTableNameHeader({ category }),
    });
  }

  renderTimeseriesSelect({
    category,
    response: cachedResponse,
    filterQuery: substringFilter,
  });
  $(`#${CATEGORY_PANEL_IDS[category].select}`).offAndOnExact(
    "change.metricsDashboardTimeseries",
    handleTimeseriesSelectChange,
  );
}

/**
 * Render the timeseries chart for the active panel into its `<svg>` container.
 */
function renderActivePanelTimeseries({
  category,
  response,
}: {
  category: MetricsCategory;
  response: Schema<"TimeseriesResponseSchema">;
}): void {
  const svgElement = document.getElementById(
    CATEGORY_PANEL_IDS[category].chart,
  );
  if (svgElement === null) {
    return;
  }
  renderTimeseriesChart({
    svg: svgElement as unknown as SVGSVGElement,
    response,
  });
}

/**
 * Auto-select the highest-ranked event for a category when no user selection
 * exists yet, or when the previous selection no longer appears in the latest
 * top events. Triggers `change` so the existing timeseries pipeline fetches
 * and renders the chart — this is what makes a chart visible on first page
 * load without requiring the user to pick from the dropdown or click a row.
 *
 * Skipped when:
 *   - The events list is empty (also clears stale selection state).
 *   - The user's current selection still appears in the latest response.
 */
function ensureDefaultSelection({
  category,
  response,
}: {
  category: MetricsCategory;
  response: TopEventsResponseSchema;
}): void {
  if (response.events.length === 0) {
    _selectedEventByCategory.delete(category);
    _chartFetchedWindowByCategory.delete(category);
    return;
  }
  const currentSelection = _selectedEventByCategory.get(category);
  const selectionStillPresent =
    currentSelection !== undefined &&
    response.events.some((event) => event.event_name === currentSelection);
  const chartWindowMatchesCurrent =
    _chartFetchedWindowByCategory.get(category) === _currentWindow;
  // Skip only when the user's current selection is still in the response AND
  // the chart's data already matches the active window. Either condition
  // failing — selection invalidated by polling, or window changed under us —
  // means we need to fire a fresh fetch.
  if (selectionStillPresent && chartWindowMatchesCurrent) {
    return;
  }
  const eventNameToSelect = selectionStillPresent
    ? // selectionStillPresent already guarantees currentSelection is defined
      // and matches an event_name in `response.events`.
      (currentSelection as string)
    : response.events[0].event_name;
  const selectElement = getElementByIdOrNull<HTMLSelectElement>(
    CATEGORY_PANEL_IDS[category].select,
  );
  if (selectElement === null) {
    return;
  }
  selectElement.value = eventNameToSelect;
  $(selectElement).trigger("change");
}

/**
 * Re-render the top table for a category from cache with the requested row
 * highlighted. Used after select changes / row clicks to update aria-current
 * without re-fetching events.
 */
function applyRowSelectionHighlight({
  category,
  selectedEventName,
}: {
  category: MetricsCategory;
  selectedEventName: string;
}): void {
  const cachedResponse = _topCache.get(category);
  if (cachedResponse === undefined) {
    return;
  }
  const tableElement = getElementByIdOrNull<HTMLTableElement>(
    CATEGORY_PANEL_IDS[category].tbody,
  );
  const tbody = tableElement?.querySelector("tbody") ?? null;
  if (tbody === null) {
    return;
  }
  renderTopTable({
    tbody: tbody as HTMLTableSectionElement,
    events: cachedResponse.events,
    selectedEventName,
    filterQuery: _substringFilterByCategory.get(category) ?? "",
    nameHeader: topTableNameHeader({ category }),
  });
}

/**
 * Handle a click anywhere inside the top-table tbody. Resolve the clicked row
 * to its `data-event-name`, then drive the panel's `<select>` (set value +
 * trigger change) so the existing timeseries fetch + render pipeline runs.
 * Clicks on the empty-state row are ignored (it has no `MetricsTopTableRow`
 * class and no `data-event-name`).
 */
function handleTopRowClick(event: JQuery.TriggeredEvent): void {
  const tbody = event.currentTarget as HTMLTableSectionElement;
  const tableElement = tbody.parentElement as HTMLTableElement | null;
  if (tableElement === null) {
    return;
  }
  const row = (event.target as HTMLElement).closest<HTMLTableRowElement>(
    "tr.MetricsTopTableRow",
  );
  if (row === null) {
    return;
  }
  const eventName = row.dataset.eventName;
  if (eventName === undefined) {
    return;
  }
  const category = CATEGORIES.find(
    (candidate) => CATEGORY_PANEL_IDS[candidate].tbody === tableElement.id,
  );
  if (category === undefined) {
    return;
  }
  const selectElement = getElementByIdOrNull<HTMLSelectElement>(
    CATEGORY_PANEL_IDS[category].select,
  );
  if (selectElement === null) {
    return;
  }
  // The row's display value comes from the cached events list, which also
  // populated the select options — so the matching option should always
  // exist. Guard anyway in case caches drift mid-poll.
  const matchingOption = Array.from(selectElement.options).find(
    (option) => option.value === eventName,
  );
  if (matchingOption === undefined) {
    return;
  }
  selectElement.value = eventName;
  $(selectElement).trigger("change");
}

/**
 * Keyboard activation for top-table rows. Enter and Space both fire the same
 * action as a mouse click, matching the ARIA Authoring Practices Guide for
 * activating a focusable, non-button widget.
 */
function handleTopRowKeydown(event: JQuery.TriggeredEvent): void {
  const key = event.key;
  if (key !== "Enter" && key !== " ") {
    return;
  }
  event.preventDefault();
  handleTopRowClick(event);
}

function handleTimeseriesSelectChange(event: JQuery.TriggeredEvent): void {
  const selectElement = event.currentTarget as HTMLSelectElement;
  if (selectElement.value === "") {
    return;
  }
  const selectedOption = selectElement.options[selectElement.selectedIndex];
  // `data-event-name` is the actual DB event name (always "api_hit" for the
  // API tab, the real event for UI/Domain). When unset (old DOM), fall back
  // to the option's text value so tests stubbing minimal options still work.
  const eventName = selectedOption?.dataset.eventName ?? selectElement.value;
  const apiEndpoint = selectedOption?.dataset.endpoint;
  const apiMethod = selectedOption?.dataset.method;
  // The select's `id` is `MetricsTimeseriesEvent<Category>` — strip the prefix
  // to recover the category. Falls back to the active category if the prefix
  // does not match (defensive — should not happen with the static IDs above).
  const categoryFromId = CATEGORIES.find(
    (candidate) => selectElement.id === CATEGORY_PANEL_IDS[candidate].select,
  );
  const category = categoryFromId ?? _currentCategory;

  // Persist the selection so polling refreshes and tab switches keep the
  // matching row highlighted.
  _selectedEventByCategory.set(category, selectElement.value);
  applyRowSelectionHighlight({
    category,
    selectedEventName: selectElement.value,
  });

  const tsSlot = TS_SLOT_BY_CATEGORY[category];
  if (_inFlight[tsSlot] !== null) {
    _inFlight[tsSlot].abort();
    _inFlight[tsSlot] = null;
  }

  // Capture the window at fetch-initiation time so a window switch arriving
  // before .done resolves doesn't mis-attribute this response to the new
  // window in `_chartFetchedWindowByCategory`.
  const fetchedWindow = _currentWindow;
  const deviceType = _deviceFilterByCategory.get(category) ?? null;
  const timeseriesRequest = fetchTimeseries({
    eventName,
    window: fetchedWindow,
    resolution: "hour",
    endpoint: apiEndpoint,
    method: apiMethod,
    deviceType,
  });
  _inFlight[tsSlot] = timeseriesRequest;
  timeseriesRequest
    .done((response) => {
      setBannerVisible({ visible: false });
      renderActivePanelTimeseries({ category, response });
      _chartFetchedWindowByCategory.set(category, fetchedWindow);
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
      _inFlight[tsSlot] = null;
      _lastFetchPerf = performance.now();
      onSettleAny();
    });
}

/**
 * Fire summary + grouped pipeline-health + per-category top-events for the
 * current window. Each `.done` callback writes to the per-category cache
 * and re-renders the active panel; `.fail` shows the error banner (unless
 * the 429 prefilter already replaced the page); every settled response
 * refreshes `_lastFetchPerf` for the visibility-refetch heuristic.
 *
 * The Pipeline Health card always uses `_currentWindow` and DELIBERATELY
 * ignores the per-tab device filter — the card's whole point is to surface
 * mobile-vs-desktop chattiness as a cross-tab signal.
 *
 * Timeseries (per-category) is fetched lazily — only when the user picks
 * an event from a panel's `<select>`. There is no stable default event to
 * query on poll.
 */
// Re-render the Flows grid from the per-flow cache. Cards fill in as each
// `/flow` XHR settles; flows without a cached response are skipped.
function renderFlowsPanel(): void {
  const grid = getElementByIdOrNull<HTMLElement>(FLOWS_GRID_ID);
  if (grid === null) {
    return;
  }
  renderFlowGrid({ container: grid, responsesByFlowId: _flowCache });
}

/**
 * Fan out the four per-flow `/flow` XHRs (one per FlowId). Sets panel-scoped
 * `aria-busy` while any request is in flight and clears it after ALL four
 * settle, then announces completion on the aria-live span (DD-25 / DD-26).
 *
 * Deliberately separate from `fetchAll`'s global busy / `onSettleAny` path:
 * flow settle-state lives only on `#MetricsPanelFlows` (DD-10).
 */
function fetchFlows(): void {
  const flowIds = Object.values(FLOW_IDS);
  setFlowsPanelBusy({ busy: true });
  let pending = flowIds.length;

  const onFlowSettle = (): void => {
    pending -= 1;
    if (pending > 0) {
      return;
    }
    setFlowsPanelBusy({ busy: false });
    const announcement = getElementByIdOrNull<HTMLElement>(
      FLOWS_ANNOUNCEMENT_ID,
    );
    if (announcement !== null) {
      announcement.textContent = APP_CONFIG.strings.METRICS_FLOWS_LOADED;
    }
  };

  for (const flowId of flowIds) {
    const slotName = FLOW_SLOT_BY_FLOW_ID[flowId];
    const flowRequest = fetchFlow({ flowId, window: _currentWindow });
    _inFlight[slotName] = flowRequest;
    flowRequest
      .done((response) => {
        setBannerVisible({ visible: false });
        _flowCache[flowId] = response;
        renderFlowsPanel();
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
        _inFlight[slotName] = null;
        _lastFetchPerf = performance.now();
        onFlowSettle();
      });
  }
}

function fetchAll(): void {
  abortInFlightRequests();
  setDashboardBusy({ busy: true });
  setRefreshButtonInFlight({ inFlight: true });

  const summaryRequest = fetchSummary({ window: _currentWindow });
  _inFlight.summary = summaryRequest;
  summaryRequest
    .done((response) => {
      setBannerVisible({ visible: false });
      const summaryRoot =
        getElementByIdOrNull<HTMLElement>("MetricsSummaryGrid");
      if (summaryRoot !== null) {
        renderSummary({ root: summaryRoot, response });
      }
      _lastFlushAtMs =
        response.last_flush_at !== null
          ? Date.parse(response.last_flush_at)
          : null;
      _lastEventAtMs =
        response.last_event_at !== null
          ? Date.parse(response.last_event_at)
          : null;
      renderLastFlushBadge();
      renderLastEventBadge();
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

  // Pipeline Health card request — grouped timeseries over
  // (batch_size_bucket, transport, device_type). The card always uses
  // `_currentWindow` and DELIBERATELY ignores the per-tab device filter so
  // mobile-vs-desktop chattiness shows up as a cross-tab signal. Server-side
  // GROUP BY collapses time buckets within the window, and the renderer
  // sums them per column to produce the four stacked bars.
  const pipelineHealthRequest = fetchGroupedTimeseries({
    eventName: "api_metrics_ingest_batch",
    groupBy: ["batch_size_bucket", "transport", "device_type"],
    window: _currentWindow,
  });
  _inFlight.pipelineHealth = pipelineHealthRequest;
  const requestedWindow = _currentWindow;
  pipelineHealthRequest
    .done((response) => {
      setBannerVisible({ visible: false });
      const pipelineHealthSvg = getElementByIdOrNull<HTMLElement>(
        "MetricsPipelineHealthChart",
      ) as unknown as SVGSVGElement | null;
      if (pipelineHealthSvg !== null) {
        renderPipelineHealthChart({
          svg: pipelineHealthSvg,
          response,
          window: requestedWindow,
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
      _inFlight.pipelineHealth = null;
      _lastFetchPerf = performance.now();
      onSettleAny();
    });

  // Fire all three category requests simultaneously. $.ajax is async and
  // returns immediately, so each iteration dispatches a request without
  // waiting for the previous one to settle. Each request is stored in its own
  // `_inFlight` slot (keyed by slot name) so they can be aborted independently.
  // Pre-warming all panels here means switching tabs never triggers a fresh
  // round-trip — data is already cached in `_topCache` by the time the user
  // clicks.
  for (const category of CATEGORIES) {
    const resource = _resourceFilterByCategory.get(category) ?? null;
    const deviceType = _deviceFilterByCategory.get(category) ?? null;
    const topRequest = fetchTopEvents({
      window: _currentWindow,
      category,
      resource,
      deviceType,
      limit: effectiveTopLimit({ category }),
    });
    const slotName = TOP_SLOT_BY_CATEGORY[category];
    _inFlight[slotName] = topRequest;
    topRequest
      .done((response) => {
        setBannerVisible({ visible: false });
        _topCache.set(category, response);
        renderCategoryPanelFromCache({ category });
        ensureDefaultSelection({ category, response });
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
        _inFlight[slotName] = null;
        _lastFetchPerf = performance.now();
        onSettleAny();
      });
  }

  // Gate the per-flow fan-out on the active tab (DD-21): the ~4 flow requests
  // only fire while the Flows tab is visible, not every 60 s tick. `_activeTab`
  // is the single source of truth here — `_currentCategory` never equals
  // "flows", so gating on it would be dead code.
  if (_activeTab === TAB.FLOWS) {
    fetchFlows();
  }
}

/**
 * Clear UI in-flight indicators when no requests remain pending. Both
 * `aria-busy` on the dashboard root and the Refresh button's `aria-disabled`
 * track the union of all in-flight requests.
 *
 * Flow slots (flowCreateUtub, flowAddUrl, flowRegister, flowLogin) excluded —
 * tracked via #MetricsPanelFlows aria-busy instead.
 */
function onSettleAny(): void {
  const anyInFlight =
    _inFlight.topApi !== null ||
    _inFlight.topUi !== null ||
    _inFlight.topDomain !== null ||
    _inFlight.tsApi !== null ||
    _inFlight.tsUi !== null ||
    _inFlight.tsDomain !== null ||
    _inFlight.summary !== null ||
    _inFlight.pipelineHealth !== null;
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

/**
 * Update `#MetricsLastFlush` with elapsed time since the worker's last liveness
 * stamp (`metrics:flush:last_success_epoch`), which advances every minute the
 * worker runs successfully — regardless of traffic. Called every
 * `BADGE_TICK_INTERVAL_MS` while the tab is visible.
 *
 * The 2-min "stale" threshold means the worker has missed at least two cron
 * ticks, which warrants admin attention. `Date.now()` (NOT `performance.now()`)
 * is correct because `_lastFlushAtMs` is `Date.parse(response.last_flush_at)`,
 * a wall-clock epoch supplied by the server; subtracting a page-load-relative
 * `performance.now()` from a wall-clock epoch would produce a meaningless
 * delta.
 *
 * The visible badge text refreshes every tick. The visually-hidden aria-live
 * sink (`#MetricsLastFlushAnnouncement`) is written only when the bucket
 * transitions, so screen-reader users hear at most a handful of announcements
 * per flush cycle rather than every-second chatter.
 */
function renderLastFlushBadge(): void {
  const badge = getElementByIdOrNull<HTMLElement>(LAST_FLUSH_BADGE_ID);
  const textNode = getElementByIdOrNull<HTMLElement>(LAST_FLUSH_TEXT_ID);
  if (badge === null || textNode === null) {
    return;
  }

  if (_lastFlushAtMs === null) {
    // The flush sentinel is absent on fresh stacks (no flush has run yet)
    // and after any operation that clears Redis (container restart, manual
    // `make metrics-clear-*`). An empty badge in that state reads as a bug;
    // surface the unknown state explicitly instead.
    textNode.textContent = APP_CONFIG.strings.METRICS_LAST_FLUSH_UNKNOWN;
    badge.classList.remove(BADGE_STALE_CLASS);
    return;
  }

  const elapsedMs = Date.now() - _lastFlushAtMs;
  let text: string;
  let bucket: LastFlushBucket;
  if (elapsedMs < BADGE_BUCKET_SECONDS_MS) {
    text = APP_CONFIG.strings.METRICS_LAST_FLUSH_JUST_NOW;
    bucket = "just_now";
  } else if (elapsedMs < BADGE_BUCKET_MINUTES_MS) {
    text = APP_CONFIG.strings.METRICS_LAST_FLUSH_SECONDS.replace(
      "{{ n }}",
      String(Math.floor(elapsedMs / 1_000)),
    );
    bucket = "seconds";
  } else if (elapsedMs < FLUSH_STALE_AT_MS) {
    text = APP_CONFIG.strings.METRICS_LAST_FLUSH_MINUTES.replace(
      "{{ n }}",
      String(Math.floor(elapsedMs / 60_000)),
    );
    bucket = "minutes";
  } else if (elapsedMs < FLUSH_STALE_HOURS_AT_MS) {
    text = APP_CONFIG.strings.METRICS_LAST_FLUSH_STALE_MINUTES.replace(
      "{{ n }}",
      String(Math.floor(elapsedMs / 60_000)),
    );
    bucket = "stale_minutes";
  } else {
    text = APP_CONFIG.strings.METRICS_LAST_FLUSH_STALE_HOURS.replace(
      "{{ n }}",
      String(Math.floor(elapsedMs / 3_600_000)),
    );
    bucket = "stale_hours";
  }

  textNode.textContent = text;
  const isStale = bucket === "stale_minutes" || bucket === "stale_hours";
  if (isStale) {
    badge.classList.add(BADGE_STALE_CLASS);
  } else {
    badge.classList.remove(BADGE_STALE_CLASS);
  }

  if (bucket !== _lastAnnouncedFlushBucket) {
    const announcement = getElementByIdOrNull<HTMLElement>(
      LAST_FLUSH_ANNOUNCEMENT_ID,
    );
    if (announcement !== null) {
      announcement.textContent = text;
    }
    _lastAnnouncedFlushBucket = bucket;
  }
}

/**
 * Update `#MetricsLastEvent` with elapsed time since the most recent
 * AnonymousMetrics bucket (server's `last_event_at`). Advances only when
 * traffic lands, so a multi-hour gap is normal during low usage — the badge
 * intentionally never paints itself "stale" since hours-old data does not
 * indicate a broken pipeline (see `renderLastFlushBadge` for that signal).
 */
function renderLastEventBadge(): void {
  const badge = getElementByIdOrNull<HTMLElement>(LAST_EVENT_BADGE_ID);
  const textNode = getElementByIdOrNull<HTMLElement>(LAST_EVENT_TEXT_ID);
  if (badge === null || textNode === null) {
    return;
  }

  if (_lastEventAtMs === null) {
    // Mirror the flush badge fallback: surface the unknown state instead of
    // blanking the badge to a green dot with no text.
    textNode.textContent = APP_CONFIG.strings.METRICS_LAST_EVENT_UNKNOWN;
    return;
  }

  const elapsedMs = Date.now() - _lastEventAtMs;
  let text: string;
  let bucket: LastEventBucket;
  if (elapsedMs < BADGE_BUCKET_SECONDS_MS) {
    text = APP_CONFIG.strings.METRICS_LAST_EVENT_JUST_NOW;
    bucket = "just_now";
  } else if (elapsedMs < BADGE_BUCKET_MINUTES_MS) {
    text = APP_CONFIG.strings.METRICS_LAST_EVENT_SECONDS.replace(
      "{{ n }}",
      String(Math.floor(elapsedMs / 1_000)),
    );
    bucket = "seconds";
  } else if (elapsedMs < EVENT_HOURS_AT_MS) {
    text = APP_CONFIG.strings.METRICS_LAST_EVENT_MINUTES.replace(
      "{{ n }}",
      String(Math.floor(elapsedMs / 60_000)),
    );
    bucket = "minutes";
  } else {
    text = APP_CONFIG.strings.METRICS_LAST_EVENT_HOURS.replace(
      "{{ n }}",
      String(Math.floor(elapsedMs / 3_600_000)),
    );
    bucket = "hours";
  }

  textNode.textContent = text;

  if (bucket !== _lastAnnouncedEventBucket) {
    const announcement = getElementByIdOrNull<HTMLElement>(
      LAST_EVENT_ANNOUNCEMENT_ID,
    );
    if (announcement !== null) {
      announcement.textContent = text;
    }
    _lastAnnouncedEventBucket = bucket;
  }
}

function tickBothBadges(): void {
  renderLastFlushBadge();
  renderLastEventBadge();
}

function startBadgeTicker(): void {
  if (_badgeIntervalId !== null) {
    clearInterval(_badgeIntervalId);
  }
  _badgeIntervalId = setInterval(tickBothBadges, BADGE_TICK_INTERVAL_MS);
  tickBothBadges();
}

function stopBadgeTicker(): void {
  if (_badgeIntervalId !== null) {
    clearInterval(_badgeIntervalId);
    _badgeIntervalId = null;
  }
}

function handleVisibilityChange(): void {
  if (document.visibilityState === "hidden") {
    stopPolling();
    stopBadgeTicker();
    return;
  }
  if (document.visibilityState === "visible") {
    const elapsedMs = performance.now() - _lastFetchPerf;
    if (elapsedMs > VISIBILITY_REFETCH_THRESHOLD_MS) {
      fetchAll();
    }
    startPolling();
    startBadgeTicker();
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

/**
 * Set ARIA tab/panel state for the requested category: clicked tab becomes
 * `aria-selected="true"` with `tabindex="0"`, all others become
 * `aria-selected="false"` with `tabindex="-1"` (roving tabindex pattern).
 * Hide every panel except the active one, then focus the active panel so
 * keyboard users land inside the section content after switching.
 */
function handleTabClick({
  tabId: _domTabId,
  tab,
}: {
  tabId: string;
  tab: MetricsTabId;
}): void {
  // `_activeTab` tracks the visible tab for EVERY tab (categories,
  // pipeline_health, flows). `_currentCategory` keeps only true category
  // values — guarded against ever receiving "pipeline_health" / "flows".
  _activeTab = tab;
  if (tab !== TAB.PIPELINE_HEALTH && tab !== TAB.FLOWS) {
    _currentCategory = tab;
  }

  for (const candidateTab of TAB_IDS) {
    const isActive = candidateTab === tab;
    const ids = getTabAndPanelIds(candidateTab);
    const tabElement = getElementByIdOrNull<HTMLButtonElement>(ids.tab);
    if (tabElement !== null) {
      tabElement.setAttribute("aria-selected", isActive ? "true" : "false");
      tabElement.setAttribute("tabindex", isActive ? "0" : "-1");
    }

    const panelElement = getElementByIdOrNull<HTMLElement>(ids.panel);
    if (panelElement !== null) {
      if (isActive) {
        panelElement.removeAttribute("hidden");
      } else {
        panelElement.setAttribute("hidden", "");
      }
    }
  }

  // For category tabs, re-render the active panel from cache so the latest
  // top-events list and select options are visible immediately after the
  // switch. Pipeline Health renders from the grouped-timeseries XHR fired by
  // `fetchAll`; Flows renders from `_flowCache` (its own XHRs), so neither
  // needs a category-cache re-render here.
  if (tab !== TAB.PIPELINE_HEALTH && tab !== TAB.FLOWS) {
    renderCategoryPanelFromCache({ category: tab });
  }

  // First activation of the Flows tab fires the fan-out immediately rather
  // than waiting up to 60 s for the next `fetchAll` tick. Subsequent switches
  // re-render from the warm cache.
  if (tab === TAB.FLOWS) {
    if (Object.keys(_flowCache).length === 0) {
      fetchFlows();
    } else {
      renderFlowsPanel();
    }
  }

  const activePanel = getElementByIdOrNull<HTMLElement>(
    getTabAndPanelIds(tab).panel,
  );
  activePanel?.focus();
}

function handleTabButtonClick(event: JQuery.TriggeredEvent): void {
  const tabElement = event.currentTarget as HTMLButtonElement;
  const tab = tabElement.dataset.tab as MetricsTabId | undefined;
  if (tab === undefined) {
    return;
  }
  handleTabClick({ tabId: tabElement.id, tab });
}

/**
 * Arrow-key navigation for the tablist, matching the ARIA Authoring Practices
 * Guide tablist pattern: Left/Right cycle through tabs with wrap-around,
 * Home/End jump to the first/last tab. Each handled key calls
 * `preventDefault()` to suppress the browser's default keystroke behavior
 * (e.g. horizontal scroll on Left/Right).
 */
// keydown (not keyup) — ARIA APG tablist spec; intentional deviation from repo's keyup convention
function handleTabKeydown(event: JQuery.TriggeredEvent): void {
  const key = event.key as string | undefined;
  if (
    key !== "ArrowLeft" &&
    key !== "ArrowRight" &&
    key !== "Home" &&
    key !== "End"
  ) {
    return;
  }

  const tabElement = event.currentTarget as HTMLButtonElement;
  const currentTab = tabElement.dataset.tab as MetricsTabId | undefined;
  if (currentTab === undefined) {
    return;
  }
  const currentIndex = TAB_IDS.indexOf(currentTab);
  if (currentIndex === -1) {
    return;
  }

  let nextIndex: number;
  if (key === "ArrowLeft") {
    nextIndex = (currentIndex - 1 + TAB_IDS.length) % TAB_IDS.length;
  } else if (key === "ArrowRight") {
    nextIndex = (currentIndex + 1) % TAB_IDS.length;
  } else if (key === "Home") {
    nextIndex = 0;
  } else {
    nextIndex = TAB_IDS.length - 1;
  }

  event.preventDefault();

  const nextTab = TAB_IDS[nextIndex];
  const nextTabIds = getTabAndPanelIds(nextTab);
  const nextTabElement = getElementByIdOrNull<HTMLButtonElement>(
    nextTabIds.tab,
  );
  handleTabClick({
    tabId: nextTabIds.tab,
    tab: nextTab,
  });
  // After `handleTabClick` focuses the panel, return focus to the activated
  // tab so the user can keep navigating with arrow keys without re-tabbing
  // out of the panel. Matches ARIA APG: keyboard activation keeps focus on
  // the tab; mouse activation moves focus to the panel.
  nextTabElement?.focus();
}

export function initMetricsDashboard(): void {
  const dashboardRoot = getElementByIdOrNull<HTMLElement>(DASHBOARD_ROOT_ID);
  if (dashboardRoot === null) {
    return;
  }

  $(`.${WINDOW_BUTTON_CLASS}`).offAndOnExact("click", handleWindowButtonClick);
  $(`#${REFRESH_BUTTON_ID}`).offAndOnExact("click", handleRefreshClick);
  $(`#${TABLIST_ID} ${TAB_ROLE_SELECTOR}`).offAndOnExact(
    "click",
    handleTabButtonClick,
  );
  $(`#${TABLIST_ID} ${TAB_ROLE_SELECTOR}`).offAndOnExact(
    "keydown.metricsDashboardTabs",
    handleTabKeydown,
  );

  // Bind the per-panel `<select>` change handlers up-front so the timeseries
  // fetch fires even if the panel's options were rendered server-side (or by
  // a test fixture) before any top-events fetch completes.
  for (const category of CATEGORIES) {
    $(`#${CATEGORY_PANEL_IDS[category].select}`).offAndOnExact(
      "change.metricsDashboardTimeseries",
      handleTimeseriesSelectChange,
    );

    // Bind row click + keydown on each panel's tbody so clicking (or pressing
    // Enter/Space on) a row drives the same fetch path as picking from the
    // select. tbody is server-rendered (empty) at init time; renderTopTable
    // appends rows later — events bubble from those new rows to the bound
    // tbody, so a single binding at init covers all subsequent renders.
    const tableElement = getElementByIdOrNull<HTMLTableElement>(
      CATEGORY_PANEL_IDS[category].tbody,
    );
    const tbody = tableElement?.querySelector("tbody") ?? null;
    if (tbody !== null) {
      $(tbody).offAndOnExact("click.metricsDashboardTopRow", handleTopRowClick);
      $(tbody).offAndOnExact(
        "keydown.metricsDashboardTopRow",
        handleTopRowKeydown,
      );
    }

    populateResourceFilter({ category });
    $(`#${CATEGORY_PANEL_IDS[category].resourceFilter}`).offAndOnExact(
      "change.metricsDashboardResourceFilter",
      handleResourceFilterChange,
    );
    populateDeviceFilter({ category });
    $(`#${CATEGORY_PANEL_IDS[category].deviceFilter}`).offAndOnExact(
      "change.metricsDashboardDeviceFilter",
      handleDeviceFilterChange,
    );
    $(`#${CATEGORY_PANEL_IDS[category].substringFilter}`).offAndOnExact(
      "input.metricsDashboardSubstringFilter",
      handleSubstringFilterInput,
    );
  }

  document.addEventListener("visibilitychange", handleVisibilityChange);

  initPaneResizers();

  fetchAll();
  startPolling();
  startBadgeTicker();
}

/**
 * Test-only helper. Resets module-local state between tests so each spec runs
 * against a clean lifecycle. Not used in production — the dashboard is a
 * single-page surface initialized once per page load.
 */
export function _resetMetricsDashboardForTests(): void {
  stopPolling();
  stopBadgeTicker();
  abortInFlightRequests();
  _lastFetchPerf = 0;
  _currentWindow = "day";
  _currentCategory = TAB.API;
  _activeTab = TAB.API;
  _inFlight = {
    topApi: null,
    topUi: null,
    topDomain: null,
    tsApi: null,
    tsUi: null,
    tsDomain: null,
    summary: null,
    pipelineHealth: null,
    flowCreateUtub: null,
    flowAddUrl: null,
    flowRegister: null,
    flowLogin: null,
  };
  _flowCache = {};
  _topCache.clear();
  _selectedEventByCategory.clear();
  _chartFetchedWindowByCategory.clear();
  _resourceFilterByCategory.clear();
  _substringFilterByCategory.clear();
  for (const pendingTimer of _substringDebounceTimerByCategory.values()) {
    clearTimeout(pendingTimer);
  }
  _substringDebounceTimerByCategory.clear();
  _deviceFilterDebounceTimerByCategory.forEach((timer) => clearTimeout(timer));
  _deviceFilterDebounceTimerByCategory.clear();
  _deviceFilterByCategory.clear();
  _lastFlushAtMs = null;
  _lastAnnouncedFlushBucket = null;
  _lastEventAtMs = null;
  _lastAnnouncedEventBucket = null;
  document.removeEventListener("visibilitychange", handleVisibilityChange);
  _resetPaneResizersForTests();
}

/**
 * Test-only badge helpers. Vitest specs need to set the wall-clock anchor
 * directly and then invoke the renderer (or read the announcement state)
 * without going through a full mocked fetch cycle.
 */
export function _setLastFlushAtMsForTests(value: number | null): void {
  _lastFlushAtMs = value;
}

export function _renderLastFlushBadgeForTests(): void {
  renderLastFlushBadge();
}

export function _setLastEventAtMsForTests(value: number | null): void {
  _lastEventAtMs = value;
}

export function _renderLastEventBadgeForTests(): void {
  renderLastEventBadge();
}
