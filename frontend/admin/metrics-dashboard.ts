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
import { FLOW_IDS, FLOW_METADATA } from "../types/metrics-flows.js";
import {
  RESOURCES,
  RESOURCES_BY_CATEGORY,
  type ResourceName,
} from "../types/metrics-resources.js";

import { APP_CONFIG } from "../lib/config.js";
import { $ } from "../lib/globals.js";
import { is429Handled } from "../lib/ajax.js";
import { debug } from "../lib/debug.js";
import { fillTemplate } from "../lib/string-template.js";

import type {
  FlowCardCustom,
  FlowGridEntry,
  FlowInvalidDetail,
} from "./flow-card.js";
import { renderFlowGrid } from "./flow-card.js";
import { createFlowLoadQueue } from "./flow-load-queue.js";
import { renderGaugeGrid } from "./gauge-card.js";
import {
  renderLatencyDetailChart,
  renderLatencyPanel,
} from "./latency-card.js";
import {
  deleteMetricFlow,
  fetchFlow,
  fetchMetricFlows,
  fetchGaugesTimeseries,
  fetchGroupedTimeseries,
  fetchLatency as fetchLatencyClient,
  fetchLatencyTimeseries as fetchLatencyTimeseriesClient,
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

const log = debug("admin-metrics-dashboard");

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
  GAUGES: "gauges",
  LATENCY: "latency",
  PIPELINE_HEALTH: "pipeline_health",
} as const;
type MetricsCategory = typeof TAB.API | typeof TAB.UI | typeof TAB.DOMAIN;
type MetricsTabId =
  | MetricsCategory
  | typeof TAB.FLOWS
  | typeof TAB.GAUGES
  | typeof TAB.LATENCY
  | typeof TAB.PIPELINE_HEALTH;
type TopEventsResponseSchema = Schema<"TopEventsResponseSchema">;
type FlowResponseSchema = Schema<"FlowResponseSchema">;
type GaugesTimeseriesResponse = Schema<"GaugesTimeseriesResponseSchema">;
type LatencyPercentilesResponse = Schema<"LatencyPercentilesResponseSchema">;
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
  gaugesTimeseries: JQuery.jqXHR | null;
  latency: JQuery.jqXHR | null;
  latencyTimeseries: JQuery.jqXHR | null;
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
  [RESOURCES.ONBOARDING]: APP_CONFIG.strings.METRICS_TOP_RESOURCE_ONBOARDING,
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
// Named windows that reach beyond the 35-day raw-sample retention horizon. Only
// these serve the per-endpoint summary from the daily rollup (approximate) and
// must request a daily-grain timeseries; Day/Week/Month stay on the exact raw
// path. Shared by `fetchLatencyTimeseries` (resolution) and the
// `renderLatencyDetailChart` call (daily flag).
const LONG_WINDOWS: ReadonlySet<MetricsWindow> = new Set(["year"] as const);
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
// Tab order: Gauges to API to UI to Domain to Flows to Latency to Pipeline
// Health. Pipeline Health is always the last tab; Latency precedes it. This
// array is the source of truth for arrow-key / Home / End tablist navigation —
// it must match the template button order exactly.
const TAB_IDS: readonly MetricsTabId[] = [
  TAB.GAUGES,
  ...CATEGORIES,
  TAB.FLOWS,
  TAB.LATENCY,
  TAB.PIPELINE_HEALTH,
];

const PIPELINE_HEALTH_TAB_ID: string = "MetricsTabPipelineHealth";
const PIPELINE_HEALTH_PANEL_ID: string = "MetricsPanelPipelineHealth";
const FLOWS_TAB_ID: string = "MetricsTabFlows";
const FLOWS_PANEL_ID: string = "MetricsPanelFlows";
const FLOWS_GRID_ID: string = "MetricsFlowGrid";
const FLOWS_ANNOUNCEMENT_ID: string = "MetricsPanelFlowsAnnouncement";
const FLOWS_HEADING_ID: string = "MetricsFlowsHeading";
const FLOWS_COUNT_ID: string = "MetricsFlowsCount";
const FLOWS_HINT_ID: string = "MetricsFlowsHint";
const FLOWS_NOTICE_ID: string = "MetricsFlowsNotice";
const FLOWS_ACTION_ANNOUNCEMENT_ID: string = "MetricsFlowsActionAnnouncement";
const CUSTOM_FLOW_ID_PREFIX: string = "custom_";
const GAUGES_TAB_ID: string = "MetricsTabGauges";
const GAUGES_PANEL_ID: string = "MetricsPanelGauges";
const LATENCY_TAB_ID: string = "MetricsTabLatency";
const LATENCY_PANEL_ID: string = "MetricsPanelLatency";
const LATENCY_TABLE_ID: string = "MetricsLatencyTable";
const LATENCY_CHART_CONTAINER_ID: string = "MetricsLatencyChartContainer";
const LATENCY_ANNOUNCEMENT_ID: string = "MetricsPanelLatencyAnnouncement";
const GAUGES_GRID_ID: string = "MetricsGaugeGrid";
const GAUGES_ANNOUNCEMENT_ID: string = "MetricsPanelGaugesAnnouncement";
// The global per-window event-totals summary, shown above the event-category
// tabs but hidden on Flows and Gauges (neither is about window-wide event counts).
const SUMMARY_SECTION_ID: string = "MetricsSummary";

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
  if (tabId === TAB.LATENCY) {
    return { tab: LATENCY_TAB_ID, panel: LATENCY_PANEL_ID };
  }
  if (tabId === TAB.GAUGES) {
    return { tab: GAUGES_TAB_ID, panel: GAUGES_PANEL_ID };
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
// tab in `handleTabClick`. Initialized to Gauges, the default landing tab.
let _activeTab: MetricsTabId = TAB.GAUGES;
let _inFlight: InFlightRequests = {
  topApi: null,
  topUi: null,
  topDomain: null,
  tsApi: null,
  tsUi: null,
  tsDomain: null,
  summary: null,
  pipelineHealth: null,
  gaugesTimeseries: null,
  latency: null,
  latencyTimeseries: null,
};
// Last successful `/flow` response per flow id, so a tab switch back to Flows
// renders instantly from cache. Populated by the flow load queue.
const _flowCache = new Map<string, FlowResponseSchema>();
// Ids whose last result was not a response: "error" (generic failure) or the
// server's `flow_invalid` detail.
const _flowStates = new Map<string, "error" | FlowInvalidDetail>();

// Flow list state (see the plan's "List state and request ownership").
// `_flowList` is null only until a list first resolves, afterwards always the
// last good list. One shared request slot (`_flowListXhr` + kind + whether it
// owns the panel's `aria-busy`) serves both the full `load` and the `refresh`.
type FlowListEntry = Schema<"MetricFlowEntrySchema">;
type FlowListStatus = "idle" | "loading" | "failed" | "loaded";
type FlowListKind = "load" | "refresh";
let _flowList: FlowListEntry[] | null = null;
let _flowListStatus: FlowListStatus = "idle";
let _flowListXhr: JQuery.jqXHR | null = null;
let _flowListKind: FlowListKind | null = null;
let _flowListOwnsBusy: boolean = false;
// True after a list failure until the next list success; drives the inline
// `.flows-list-error` independent of the status.
let _flowListErrorShown: boolean = false;
// The list-Retry button that started the in-flight `load`, if any (DD-24).
let _flowListRetryButton: HTMLElement | null = null;
// The one custom card whose Delete confirm is open or whose DELETE is in
// flight. `title` is set when the confirm opens (for the already-deleted
// notice) and again at the Confirm click (for the deleting-card injection).
interface FlowConfirmState {
  id: string;
  phase: "open" | "deleting";
  title: string | null;
}
let _flowConfirm: FlowConfirmState | null = null;
// Inline per-card delete errors (429 / failure), keyed by flow id.
const _flowCardMessages = new Map<string, string>();
// The single in-flight DELETE; a settle whose xhr is not this one is ignored.
let _flowDeleteXhr: JQuery.jqXHR | null = null;
let _flowActionAnnounceTimer: ReturnType<typeof setTimeout> | null = null;
// Last successful batched `gauges/timeseries` response (the full envelope, not
// `GaugeSeries[]`), so a tab switch back to Gauges renders instantly from cache.
// Populated by `fetchGauges`; `null` until the first batched request settles.
let _gaugesCache: GaugesTimeseriesResponse | null = null;
// `gauge_name` of the row whose timeseries is shown in the Gauges detail area.
// `null` means no gauge is selected — the detail area shows the select-a-gauge
// prompt. Set by `handleGaugeRowClick`; survives polls so the chosen chart
// re-renders with fresh samples each tick.
let _selectedGaugeName: string | null = null;
// Last successful batched `/latency` percentile response, so a tab switch back
// to the Backend Performance tab renders instantly from cache. `null` until the
// first request settles. Populated by `fetchLatency`.
let _latencyCache: LatencyPercentilesResponse | null = null;
// The endpoint+method of the percentile-table row whose latency timeseries is
// shown in the detail area. `null` means no row is selected — the detail area
// shows the select-an-endpoint prompt. Set by `handleLatencyRowClick`; survives
// polls so the chosen chart re-fetches with fresh data each tick.
let _selectedLatencyEndpoint: string | null = null;
let _selectedLatencyMethod: string | null = null;

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
// Tracks the last-announced latency approximate-state so the screen-reader
// announcement fires only on a true transition (null counts as the initial
// state — null→true announces, null→false is a no-op clear).
let _lastAnnouncedLatencyApproximate: boolean | null = null;

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

// Gauge XHR settle-state is tracked separately from the global dashboard busy
// path (DD-7), mirroring `setFlowsPanelBusy`: set/clear `aria-busy` on the
// Gauges panel only so the `.gauges-loading-spinner` reveals without coupling
// to the root dashboard fetch. Excluded from `onSettleAny`.
function setGaugesPanelBusy({ busy }: { busy: boolean }): void {
  const panel = getElementByIdOrNull<HTMLElement>(GAUGES_PANEL_ID);
  if (panel === null) {
    return;
  }
  if (busy) {
    panel.setAttribute("aria-busy", "true");
  } else {
    panel.removeAttribute("aria-busy");
  }
}

// Latency XHR settle-state is tracked separately from the global dashboard busy
// path (mirroring `setGaugesPanelBusy`): set/clear `aria-busy` on the Latency
// panel only so the `.latency-loading-spinner` reveals without coupling to the
// root dashboard fetch. Both latency in-flight slots are excluded from
// `onSettleAny`.
function setLatencyPanelBusy({ busy }: { busy: boolean }): void {
  const panel = getElementByIdOrNull<HTMLElement>(LATENCY_PANEL_ID);
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
    "gaugesTimeseries",
    "latency",
    "latencyTimeseries",
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

/**
 * Handle a click anywhere inside the Gauges table. Resolve the clicked row to
 * its `data-gauge-name`, record it as the selected gauge, and re-render the
 * panel so that gauge's timeseries chart replaces the prompt (or the previously
 * selected gauge's chart) in the detail area, then scrolls the chart into view
 * (the table can be tall on mobile, where the detail otherwise sits off-screen).
 * Clicks outside a `.gauge-row` (e.g. the header) are ignored.
 */
function handleGaugeRowClick(event: JQuery.TriggeredEvent): void {
  const row = (event.target as HTMLElement).closest<HTMLTableRowElement>(
    "tr.gauge-row",
  );
  if (row === null) {
    return;
  }
  const gaugeName = row.dataset.gaugeName;
  if (gaugeName === undefined) {
    return;
  }
  _selectedGaugeName = gaugeName;
  renderGaugesPanel();

  // Bring the freshly rendered chart into view on both mobile and desktop. The
  // scroll only fires on this explicit user action — never on poll re-renders,
  // which would yank the viewport unexpectedly.
  const grid = getElementByIdOrNull<HTMLElement>(GAUGES_GRID_ID);
  const detail = grid?.querySelector<HTMLElement>(".gauge-detail") ?? null;
  detail?.scrollIntoView({ behavior: "smooth", block: "start" });
}

/**
 * Keyboard activation for gauge rows. Enter and Space both fire the same action
 * as a mouse click, matching the ARIA Authoring Practices Guide for activating a
 * focusable, non-button widget.
 */
function handleGaugeRowKeydown(event: JQuery.TriggeredEvent): void {
  const key = event.key;
  if (key !== "Enter" && key !== " ") {
    return;
  }
  event.preventDefault();
  handleGaugeRowClick(event);
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
interface FlowSource {
  id: string;
  title: string;
  isCustom: boolean;
  // Invalid detail seeded by the list (non-empty `errors`), else null.
  seededInvalid: FlowInvalidDetail | null;
}

function listEntryToSource({ entry }: { entry: FlowListEntry }): FlowSource {
  const hasErrors = Object.keys(entry.errors).length > 0;
  const seededInvalid: FlowInvalidDetail | null = hasErrors
    ? (entry.first_invalid ?? {
        step_index: null,
        field: "__root__",
        reason: APP_CONFIG.strings.METRICS_FLOW_NEEDS_ATTENTION_HELP,
      })
    : null;
  return {
    id: entry.id,
    title: entry.display_name,
    isCustom: !entry.is_builtin,
    seededInvalid,
  };
}

// The cards to show: the stored list when one has resolved, else the four
// built-ins from `FLOW_METADATA` (list pending or failed with nothing stored).
function getFlowSources(): FlowSource[] {
  if (_flowList !== null) {
    const sources = _flowList.map((entry) => listEntryToSource({ entry }));
    // A card being deleted stays until its DELETE settles, even when the
    // stored list omits it (DD-28).
    if (
      _flowConfirm !== null &&
      _flowConfirm.phase === "deleting" &&
      !sources.some((source) => source.id === _flowConfirm?.id)
    ) {
      sources.push({
        id: _flowConfirm.id,
        title: _flowConfirm.title ?? _flowConfirm.id,
        isCustom: true,
        seededInvalid: null,
      });
    }
    return sources;
  }
  return Object.values(FLOW_IDS).map((flowId) => ({
    id: flowId,
    title: FLOW_METADATA[flowId].displayName,
    isCustom: false,
    seededInvalid: null,
  }));
}

// Re-render the Flows grid from the per-id cache and states. Precedence per
// id, first match wins: response > `/flow` 422 invalid > list-seeded invalid >
// loading (pending) > error. A listed id with nothing renders `loading` (never
// dropped, never a fabricated error). Without a list, an id matching none
// (e.g. aborted off the Flows tab) is left out.
function buildFlowEntries(): FlowGridEntry[] {
  const entries: FlowGridEntry[] = [];
  const unlistedLoading = _flowList !== null || _flowListStatus === "loading";
  for (const source of getFlowSources()) {
    const { id, title } = source;
    const response = _flowCache.get(id);
    const flowState = _flowStates.get(id);
    let state: FlowGridEntry["state"] | null = null;
    if (response !== undefined) {
      state = { kind: "response", response };
    } else if (flowState !== undefined && flowState !== "error") {
      state = { kind: "invalid", invalid: flowState };
    } else if (source.seededInvalid !== null) {
      state = { kind: "invalid", invalid: source.seededInvalid };
    } else if (_flowLoadQueue.isPending({ id })) {
      state = { kind: "loading" };
    } else if (flowState === "error") {
      state = { kind: "error" };
    } else if (unlistedLoading) {
      state = { kind: "loading" };
    }
    if (state === null) {
      continue;
    }
    const entry: FlowGridEntry = { id, title, state };
    if (source.isCustom) {
      entry.custom = getFlowCustomState({ id });
    }
    entries.push(entry);
  }
  // A message belongs to a card that still renders.
  const renderedIds = new Set(entries.map((entry) => entry.id));
  for (const messageId of Array.from(_flowCardMessages.keys())) {
    if (!renderedIds.has(messageId)) {
      _flowCardMessages.delete(messageId);
    }
  }
  return entries;
}

function getFlowCustomState({ id }: { id: string }): FlowCardCustom {
  const confirm = _flowConfirm;
  return {
    confirm: confirm !== null && confirm.id === id ? confirm.phase : "closed",
    message: _flowCardMessages.get(id) ?? null,
    deleteLocked:
      confirm !== null && confirm.phase === "deleting" && confirm.id !== id,
  };
}

function findFlowCard({
  grid,
  id,
}: {
  grid: HTMLElement;
  id: string;
}): HTMLElement | null {
  for (const card of Array.from(
    grid.querySelectorAll<HTMLElement>(".flow-card"),
  )) {
    if (card.dataset.flowId === id) {
      return card;
    }
  }
  return null;
}

// Focusable card controls, by the data attribute that identifies them.
const FLOW_FOCUS_ATTRIBUTES: readonly string[] = [
  "data-flow-delete",
  "data-flow-retry",
  "data-flow-confirm-cancel",
  "data-flow-confirm-delete",
];

// Wrap every grid render so focus already inside a card survives it: if the
// focused element was replaced, refocus the same control in the re-resolved
// card, else that card's `section`, else `#MetricsFlowsHeading` when the card
// is gone. Never steals focus (runs only when focus was in a card before the
// render).
function renderFlowGridPreservingFocus({
  grid,
  entries,
}: {
  grid: HTMLElement;
  entries: readonly FlowGridEntry[];
}): void {
  const focused = document.activeElement;
  const focusedCard =
    focused instanceof HTMLElement
      ? focused.closest<HTMLElement>(".flow-card")
      : null;
  const focusedId = focusedCard?.dataset.flowId ?? null;
  const focusedAttribute =
    focused instanceof HTMLElement
      ? (FLOW_FOCUS_ATTRIBUTES.find((attribute) =>
          focused.hasAttribute(attribute),
        ) ?? null)
      : null;
  renderFlowGrid({ container: grid, entries });
  if (focusedId === null || document.activeElement === focused) {
    return;
  }
  const card = findFlowCard({ grid, id: focusedId });
  if (card === null) {
    getElementByIdOrNull<HTMLElement>(FLOWS_HEADING_ID)?.focus();
    return;
  }
  const control =
    focusedAttribute === null
      ? null
      : card.querySelector<HTMLElement>(`[${focusedAttribute}]`);
  (control ?? card).focus();
}

// DD-24: a focus move made after a network wait happens only if focus is on
// `body` or inside the card the outcome belongs to.
function isFocusInCardOrBody({ id }: { id: string }): boolean {
  const active = document.activeElement;
  if (active === null || active === document.body) {
    return true;
  }
  return active.closest<HTMLElement>(".flow-card")?.dataset.flowId === id;
}

function showFlowNotice({ text }: { text: string }): void {
  const notice = getElementByIdOrNull<HTMLElement>(FLOWS_NOTICE_ID);
  if (notice === null) {
    return;
  }
  notice.textContent = text;
  notice.hidden = false;
}

function clearFlowNotice(): void {
  const notice = getElementByIdOrNull<HTMLElement>(FLOWS_NOTICE_ID);
  if (notice === null) {
    return;
  }
  notice.textContent = "";
  notice.hidden = true;
}

// Clear, then set on the next tick so a repeated message is re-read.
function announceFlowAction({ text }: { text: string }): void {
  const region = getElementByIdOrNull<HTMLElement>(
    FLOWS_ACTION_ANNOUNCEMENT_ID,
  );
  if (region === null) {
    return;
  }
  region.textContent = "";
  if (_flowActionAnnounceTimer !== null) {
    clearTimeout(_flowActionAnnounceTimer);
  }
  _flowActionAnnounceTimer = setTimeout(() => {
    _flowActionAnnounceTimer = null;
    region.textContent = text;
  }, 0);
}

function getFlowTitle({ id }: { id: string }): string {
  const listed = _flowList?.find((entry) => entry.id === id);
  if (listed !== undefined) {
    return listed.display_name;
  }
  return (_flowConfirm?.id === id ? _flowConfirm.title : null) ?? id;
}

function renderFlowsToolbar(): void {
  const count = getElementByIdOrNull<HTMLElement>(FLOWS_COUNT_ID);
  const hint = getElementByIdOrNull<HTMLElement>(FLOWS_HINT_ID);
  const builtinFallback = Object.values(FLOW_IDS).length;
  let countText = APP_CONFIG.strings.METRICS_FLOWS_COUNT_LOADING;
  let showHint = false;
  if (_flowList !== null) {
    const builtin = _flowList.filter((entry) => entry.is_builtin).length;
    const custom = _flowList.length - builtin;
    countText = fillTemplate({
      template: APP_CONFIG.strings.METRICS_FLOWS_COUNT,
      values: {
        builtin: String(builtin),
        custom: String(custom),
        max: String(APP_CONFIG.constants.METRIC_FLOWS_MAX_CUSTOM),
      },
    });
    showHint = custom === 0;
  } else if (_flowListStatus === "failed") {
    countText = fillTemplate({
      template: APP_CONFIG.strings.METRICS_FLOWS_COUNT_BUILTIN_ONLY,
      values: { builtin: String(builtinFallback) },
    });
  }
  if (count !== null) {
    count.textContent = countText;
  }
  if (hint !== null) {
    hint.textContent = showHint
      ? APP_CONFIG.strings.METRICS_FLOWS_ZERO_CUSTOM_HINT
      : "";
    hint.hidden = !showHint;
  }
}

// The inline list-failure message with its Retry. Created once and updated in
// place, so focus on Retry survives the retry (DD-27); rendered iff the flag.
function renderFlowListError({ grid }: { grid: HTMLElement }): void {
  let node = grid.querySelector<HTMLElement>(":scope > .flows-list-error");
  if (!_flowListErrorShown) {
    node?.remove();
    return;
  }
  if (node === null) {
    node = document.createElement("div");
    node.className = "flows-list-error";
    const message = document.createElement("span");
    message.textContent = APP_CONFIG.strings.METRICS_FLOWS_LIST_FAILED;
    const retry = document.createElement("button");
    retry.type = "button";
    retry.className = "flow-retry-btn";
    retry.setAttribute("data-flow-list-retry", "");
    node.append(message, retry);
  }
  if (grid.lastElementChild !== node) {
    grid.appendChild(node);
  }
  const button = node.querySelector<HTMLElement>("[data-flow-list-retry]");
  if (button !== null) {
    const retrying = _flowListStatus === "loading";
    if (retrying) {
      button.setAttribute("aria-disabled", "true");
    } else {
      button.removeAttribute("aria-disabled");
    }
    const text = retrying
      ? APP_CONFIG.strings.METRICS_FLOWS_LIST_RETRYING
      : APP_CONFIG.strings.METRICS_FLOW_RETRY;
    if (button.textContent !== text) {
      button.textContent = text;
    }
  }
}

// An open confirm whose flow another admin deleted (the list no longer has
// it): close it and say so. A `deleting` confirm is left to its DELETE response.
// The card is gone after the render, which moves focus held in it to the heading.
function closeConfirmForAbsentFlow(): void {
  const confirm = _flowConfirm;
  if (confirm === null || confirm.phase !== "open" || _flowList === null) {
    return;
  }
  if (_flowList.some((entry) => entry.id === confirm.id)) {
    return;
  }
  _flowConfirm = null;
  const text = fillTemplate({
    template: APP_CONFIG.strings.METRICS_FLOW_ALREADY_DELETED,
    values: { name: confirm.title ?? confirm.id },
  });
  showFlowNotice({ text });
  announceFlowAction({ text });
}

function renderFlowsPanel(): void {
  const grid = getElementByIdOrNull<HTMLElement>(FLOWS_GRID_ID);
  if (grid === null) {
    return;
  }
  closeConfirmForAbsentFlow();
  renderFlowsToolbar();
  renderFlowGridPreservingFocus({ grid, entries: buildFlowEntries() });
  renderFlowListError({ grid });
}

// Step 7 supplies the builder-open predicate (DD-12, DD-44); loads are never
// paused until then.
function isFlowLoadPaused(): boolean {
  return false;
}

// A `flow_invalid` 422 is recognized structurally, never by trusting the body.
function getFlowInvalidDetail({
  xhr,
}: {
  xhr: JQuery.jqXHR;
}): FlowInvalidDetail | null {
  if (xhr.status !== 422) {
    return null;
  }
  const body: unknown = xhr.responseJSON;
  if (typeof body !== "object" || body === null) {
    return null;
  }
  const { error, invalid } = body as { error?: unknown; invalid?: unknown };
  if (error !== "flow_invalid") {
    return null;
  }
  if (typeof invalid !== "object" || invalid === null) {
    return null;
  }
  const { step_index, field, reason } = invalid as Record<string, unknown>;
  if (
    (typeof step_index !== "number" && step_index !== null) ||
    typeof field !== "string" ||
    typeof reason !== "string"
  ) {
    return null;
  }
  return { step_index, field, reason };
}

function issueFlowRequest({ id }: { id: string }): JQuery.jqXHR {
  let flowRequest: JQuery.jqXHR;
  try {
    flowRequest = fetchFlow({ flowId: id, window: _currentWindow });
  } catch (error) {
    _flowStates.set(id, "error");
    renderFlowsPanel();
    throw error;
  }
  flowRequest
    .done((response: FlowResponseSchema) => {
      if (!_flowLoadQueue.isCurrent({ id, xhr: flowRequest })) {
        return;
      }
      // A list-failure banner outlives successful card settles.
      if (!_flowListErrorShown) {
        setBannerVisible({ visible: false });
      }
      _flowCache.set(id, response);
      _flowStates.delete(id);
      renderFlowsPanel();
    })
    .fail((xhr: JQuery.jqXHR) => {
      if (!_flowLoadQueue.isCurrent({ id, xhr: flowRequest })) {
        return;
      }
      if (is429Handled(xhr)) {
        if (!_flowCache.has(id) && !_flowStates.has(id)) {
          _flowStates.set(id, "error");
          renderFlowsPanel();
        }
        return;
      }
      // A timeout also has readyState 0 but is a real failure (Retry-able);
      // any other readyState 0 is an abort and stays silent.
      if (xhr.readyState === 0 && xhr.statusText !== "timeout") {
        return;
      }
      if (xhr.status === 404 && id.startsWith(CUSTOM_FLOW_ID_PREFIX)) {
        removeMissingCustomFlow({ id });
        return;
      }
      const invalid = getFlowInvalidDetail({ xhr });
      if (invalid !== null) {
        _flowStates.set(id, invalid);
        _flowCache.delete(id);
        renderFlowsPanel();
        return;
      }
      _flowStates.set(id, "error");
      setBannerVisible({ visible: true });
      renderFlowsPanel();
    })
    .always(() => {
      _lastFetchPerf = performance.now();
    });
  return flowRequest;
}

// Capped queue (at most 4 `/flow` requests in flight) shared by every Flows
// fan-out. Deliberately separate from `fetchAll`'s global busy / `onSettleAny`
// path: flow settle-state lives only on `#MetricsPanelFlows` (DD-10).
const _flowLoadQueue = createFlowLoadQueue({
  issue: issueFlowRequest,
  isPaused: isFlowLoadPaused,
  onSettle: () => renderFlowsPanel(),
  onIdle: ({ cause }) => {
    // A busy-owning list request (a `load`) clears busy and announces itself
    // through the fan-out it starts; do not clear its busy early.
    if (_flowListOwnsBusy) {
      return;
    }
    setFlowsPanelBusy({ busy: false });
    if (cause !== "settled") {
      return;
    }
    const announcement = getElementByIdOrNull<HTMLElement>(
      FLOWS_ANNOUNCEMENT_ID,
    );
    if (announcement !== null) {
      announcement.textContent = APP_CONFIG.strings.METRICS_FLOWS_LOADED;
    }
  },
});

function resetFlowListSlot(): void {
  _flowListXhr = null;
  _flowListKind = null;
  _flowListOwnsBusy = false;
}

/**
 * The only way the list request is ever aborted. A no-op on an empty slot.
 * Nulls the slot before `abort()` (jQuery fires `fail` synchronously, so that
 * settle must already be non-current). An aborted `load` leaves the status
 * `idle`; an aborted refresh leaves it. Without a replacement, busy is cleared
 * silently iff the aborted request owned it. Returns what was aborted so a
 * caller can hand it over.
 */
function abortFlowListRequest({
  replacement,
}: {
  replacement: boolean;
}): { kind: FlowListKind | null; ownsBusy: boolean } | null {
  const xhr = _flowListXhr;
  if (xhr === null) {
    return null;
  }
  const aborted = { kind: _flowListKind, ownsBusy: _flowListOwnsBusy };
  _flowListXhr = null;
  if (!replacement) {
    _flowListKind = null;
    _flowListOwnsBusy = false;
  }
  xhr.abort();
  if (aborted.kind === "load") {
    _flowListStatus = "idle";
  }
  if (!replacement && aborted.ownsBusy) {
    setFlowsPanelBusy({ busy: false });
  }
  return aborted;
}

// The id whose DELETE is in flight; list purges skip it (DD-28).
function getDeletingFlowId(): string | null {
  return _flowConfirm?.phase === "deleting" ? _flowConfirm.id : null;
}

function flowListIds(): string[] {
  return (_flowList ?? []).map((entry) => entry.id);
}

// Drops every known id (cache, states, previous list) absent from a fresh
// list, except the id whose DELETE is in flight.
function purgeUnlistedFlows({
  listed,
  dropFromQueue,
}: {
  listed: Set<string>;
  dropFromQueue: boolean;
}): void {
  const deletingId = getDeletingFlowId();
  for (const knownId of new Set([
    ..._flowCache.keys(),
    ..._flowStates.keys(),
    ...flowListIds(),
  ])) {
    if (!listed.has(knownId) && knownId !== deletingId) {
      if (dropFromQueue) {
        _flowLoadQueue.dropId({ id: knownId });
      }
      _flowCache.delete(knownId);
      _flowStates.delete(knownId);
    }
  }
}

// Fan-out per the failure rule: over the stale list's ids when a list resolved
// earlier (its cards are kept), else over the four built-ins.
function applyFlowListFailure({ showBanner }: { showBanner: boolean }): void {
  _flowListStatus = "failed";
  _flowListErrorShown = true;
  if (showBanner) {
    setBannerVisible({ visible: true });
  }
  const ids = _flowList !== null ? flowListIds() : Object.values(FLOW_IDS);
  _flowLoadQueue.startFanOut({ ids });
  renderFlowsPanel();
}

/**
 * Ask the server which flows exist, then fan out one `/flow` request per
 * listed id (at most 4 in flight). Sets panel-scoped `aria-busy`, which the
 * list request owns until its settle has started the fan-out; from then on the
 * queue's `onIdle` clears it and announces (DD-25 / DD-26).
 */
function loadFlowList({
  retryButton = null,
}: { retryButton?: HTMLElement | null } = {}): void {
  setFlowsPanelBusy({ busy: true });
  abortFlowListRequest({ replacement: true });
  _flowListStatus = "loading";
  _flowListKind = "load";
  _flowListOwnsBusy = true;
  _flowListRetryButton = retryButton;
  const request = fetchMetricFlows();
  _flowListXhr = request;
  request
    .done((response) => {
      if (_flowListXhr !== request) {
        return;
      }
      resetFlowListSlot();
      const focusHeading = shouldFocusHeadingAfterListRetry();
      _flowListRetryButton = null;
      const entries = response.flows;
      const listed = new Set(entries.map((entry) => entry.id));
      purgeUnlistedFlows({ listed, dropFromQueue: false });
      _flowList = entries;
      _flowListStatus = "loaded";
      _flowListErrorShown = false;
      _flowLoadQueue.startFanOut({ ids: flowListIds() });
      renderFlowsPanel();
      if (focusHeading) {
        getElementByIdOrNull<HTMLElement>(FLOWS_HEADING_ID)?.focus();
      }
    })
    .fail((xhr: JQuery.jqXHR) => {
      if (_flowListXhr !== request) {
        return;
      }
      resetFlowListSlot();
      _flowListRetryButton = null;
      if (xhr.readyState === 0 && xhr.statusText !== "timeout") {
        // A real abort that did not go through the helper: stay silent.
        _flowListStatus = "idle";
        setFlowsPanelBusy({ busy: false });
        renderFlowsPanel();
        return;
      }
      log("list request failed", xhr.status);
      applyFlowListFailure({ showBanner: !is429Handled(xhr) });
    });
  renderFlowsPanel();
}

// DD-24: after the list-Retry succeeds, focus the heading only if focus is
// still on that Retry button or on `body` (the node is removed with the flag).
function shouldFocusHeadingAfterListRetry(): boolean {
  if (_flowListRetryButton === null) {
    return false;
  }
  const active = document.activeElement;
  return active === _flowListRetryButton || active === document.body;
}

/**
 * Re-fetch the list without a full fan-out (a `/flow` 404 discovered a deleted
 * custom flow). Plain path only: ids no longer listed are dropped, new ids are
 * enqueued; other cards are untouched. Skipped while a `load` is in flight; a
 * newer refresh aborts an older one and inherits its busy ownership. A failure
 * leaves the list, status and cards as they are (the next poll retries).
 */
function refreshFlowList(): void {
  if (_flowListXhr !== null && _flowListKind === "load") {
    return;
  }
  abortFlowListRequest({ replacement: true });
  _flowListKind = "refresh";
  const request = fetchMetricFlows();
  _flowListXhr = request;
  request
    .done((response) => {
      if (_flowListXhr !== request) {
        return;
      }
      // The mode follows the slot's busy ownership at settle, whoever issued
      // the refresh (DD-36): owned = takeover (like a `load` success).
      const takeover = _flowListOwnsBusy;
      resetFlowListSlot();
      const entries = response.flows;
      const listed = new Set(entries.map((entry) => entry.id));
      // A takeover's fan-out restart aborts dropped ids itself; a `dropId`
      // idle flip here would clear the busy the takeover still owns.
      purgeUnlistedFlows({ listed, dropFromQueue: !takeover });
      _flowList = entries;
      _flowListStatus = "loaded";
      _flowListErrorShown = false;
      if (takeover) {
        _flowLoadQueue.startFanOut({ ids: flowListIds() });
        renderFlowsPanel();
        return;
      }
      const newIds = entries
        .map((entry) => entry.id)
        .filter(
          (id) =>
            !_flowCache.has(id) &&
            !_flowStates.has(id) &&
            !_flowLoadQueue.isPending({ id }),
        );
      if (newIds.length > 0) {
        setFlowsPanelBusy({ busy: true });
        _flowLoadQueue.enqueue({ ids: newIds });
      }
      renderFlowsPanel();
    })
    .fail((xhr: JQuery.jqXHR) => {
      if (_flowListXhr !== request) {
        return;
      }
      const takeover = _flowListOwnsBusy;
      resetFlowListSlot();
      if (xhr.readyState === 0 && xhr.statusText !== "timeout") {
        if (takeover) {
          setFlowsPanelBusy({ busy: false });
        }
        return;
      }
      log("list refresh failed", xhr.status);
      if (takeover) {
        applyFlowListFailure({ showBanner: !is429Handled(xhr) });
      }
    });
}

// A `/flow` 404 for a custom id means another admin deleted it: drop the card
// quietly (no banner). While Flows is the active tab the list is re-fetched
// once; while hidden no request is sent and the list is marked stale instead.
function removeMissingCustomFlow({ id }: { id: string }): void {
  _flowCache.delete(id);
  _flowStates.delete(id);
  if (_flowList !== null) {
    _flowList = _flowList.filter((entry) => entry.id !== id);
  }
  if (_activeTab === TAB.FLOWS) {
    renderFlowsPanel();
    refreshFlowList();
    return;
  }
  abortFlowListRequest({ replacement: false });
  _flowListStatus = "idle";
  renderFlowsPanel();
}

// Listed ids with no cached response, stored state or pending request (e.g. a
// fan-out aborted off-tab) are re-requested when Flows is activated again.
function catchUpFlowLoads(): void {
  const missing = flowListIds().filter(
    (id) =>
      !_flowCache.has(id) &&
      !_flowStates.has(id) &&
      !_flowLoadQueue.isPending({ id }),
  );
  if (missing.length === 0) {
    return;
  }
  setFlowsPanelBusy({ busy: true });
  _flowLoadQueue.enqueue({ ids: missing });
}

function getCardFlowId({ element }: { element: HTMLElement }): string | null {
  return element.closest<HTMLElement>(".flow-card")?.dataset.flowId ?? null;
}

function focusCardControl({
  id,
  attribute,
}: {
  id: string;
  attribute: string;
}): void {
  const grid = getElementByIdOrNull<HTMLElement>(FLOWS_GRID_ID);
  const card = grid === null ? null : findFlowCard({ grid, id });
  const control = card?.querySelector<HTMLElement>(`[${attribute}]`) ?? null;
  const target =
    control ?? card ?? getElementByIdOrNull<HTMLElement>(FLOWS_HEADING_ID);
  target?.focus();
}

// Delete: open the in-place confirm (one at a time), focus Cancel. Ignored
// while any card is deleting (the button is `aria-disabled`, DD-16).
function openFlowConfirm({ button }: { button: HTMLElement }): void {
  const id = getCardFlowId({ element: button });
  if (id === null || button.getAttribute("aria-disabled") === "true") {
    return;
  }
  _flowCardMessages.delete(id);
  clearFlowNotice();
  _flowConfirm = { id, phase: "open", title: getFlowTitle({ id }) };
  renderFlowsPanel();
  focusCardControl({ id, attribute: "data-flow-confirm-cancel" });
}

// Cancel / Escape on an open confirm: close it and refocus that card's Delete.
function closeFlowConfirm({ id }: { id: string | null }): void {
  if (
    id === null ||
    _flowConfirm === null ||
    _flowConfirm.id !== id ||
    _flowConfirm.phase !== "open"
  ) {
    return;
  }
  _flowConfirm = null;
  renderFlowsPanel();
  focusCardControl({ id, attribute: "data-flow-delete" });
}

// Confirm: send the DELETE once; the outcome handlers own everything after.
function submitFlowDelete({ button }: { button: HTMLElement }): void {
  const id = getCardFlowId({ element: button });
  if (
    id === null ||
    button.getAttribute("aria-disabled") === "true" ||
    _flowConfirm === null ||
    _flowConfirm.id !== id ||
    _flowConfirm.phase !== "open"
  ) {
    return;
  }
  _flowConfirm = { id, phase: "deleting", title: getFlowTitle({ id }) };
  renderFlowsPanel();
  const request = deleteMetricFlow({ flowId: id });
  _flowDeleteXhr = request;
  request
    .done(() => handleFlowDeleted({ xhr: request, id, alreadyDeleted: false }))
    .fail((xhr: JQuery.jqXHR) => {
      if (xhr.status === 404) {
        handleFlowDeleted({ xhr: request, id, alreadyDeleted: true });
        return;
      }
      handleFlowDeleteFailure({ request, xhr, id });
    });
}

function handleFlowGridKeydown(event: JQuery.TriggeredEvent): void {
  const target = event.target;
  if (event.key !== "Escape" || !(target instanceof Element)) {
    return;
  }
  const group = target.closest<HTMLElement>("[data-flow-confirm]");
  if (group === null || _flowConfirm?.phase !== "open") {
    return;
  }
  event.stopPropagation();
  closeFlowConfirm({ id: getCardFlowId({ element: group }) });
}

// DELETE 200 or 404: remove the card locally and refetch the list. A list
// request already in flight is aborted first so it cannot resurrect the card;
// when it owned `aria-busy` the refetch becomes a takeover that keeps it.
function handleFlowDeleted({
  xhr,
  id,
  alreadyDeleted,
}: {
  xhr: JQuery.jqXHR;
  id: string;
  alreadyDeleted: boolean;
}): void {
  if (_flowDeleteXhr !== xhr) {
    return;
  }
  _flowDeleteXhr = null;
  const name = getFlowTitle({ id });
  const focusEligible = isFocusInCardOrBody({ id });
  const onFlows = _activeTab === TAB.FLOWS;
  const aborted = abortFlowListRequest({ replacement: onFlows });
  if (onFlows && aborted?.ownsBusy === true) {
    setFlowsPanelBusy({ busy: true });
  }
  _flowLoadQueue.dropId({ id });
  _flowCache.delete(id);
  _flowStates.delete(id);
  _flowCardMessages.delete(id);
  if (_flowList !== null) {
    _flowList = _flowList.filter((entry) => entry.id !== id);
  }
  if (_flowConfirm?.id === id) {
    _flowConfirm = null;
  }
  if (!onFlows) {
    _flowListStatus = "idle";
    renderFlowsPanel();
    return;
  }
  const text = fillTemplate({
    template: alreadyDeleted
      ? APP_CONFIG.strings.METRICS_FLOW_ALREADY_DELETED
      : APP_CONFIG.strings.METRICS_FLOW_DELETED,
    values: { name },
  });
  if (alreadyDeleted) {
    showFlowNotice({ text });
  }
  renderFlowsPanel();
  if (focusEligible) {
    getElementByIdOrNull<HTMLElement>(FLOWS_HEADING_ID)?.focus();
  }
  announceFlowAction({ text });
  refreshFlowList();
}

// DELETE failed (429, 400, 5xx, timeout): the card stays with an inline message.
function handleFlowDeleteFailure({
  request,
  xhr,
  id,
}: {
  request: JQuery.jqXHR;
  xhr: JQuery.jqXHR;
  id: string;
}): void {
  if (_flowDeleteXhr !== request) {
    return;
  }
  _flowDeleteXhr = null;
  const focusEligible = isFocusInCardOrBody({ id });
  if (_flowConfirm?.id === id) {
    _flowConfirm = null;
  }
  if (is429Handled(xhr)) {
    renderFlowsPanel();
    return;
  }
  const message =
    xhr.status === 429
      ? APP_CONFIG.strings.METRICS_FLOW_RATE_LIMITED
      : APP_CONFIG.strings.METRICS_FLOW_DELETE_FAILED;
  _flowCardMessages.set(id, message);
  renderFlowsPanel();
  if (_activeTab !== TAB.FLOWS) {
    return;
  }
  if (focusEligible) {
    focusCardControl({ id, attribute: "data-flow-delete" });
  }
  announceFlowAction({ text: message });
}

function handleFlowGridClick(event: JQuery.TriggeredEvent): void {
  const target = event.target;
  if (!(target instanceof Element)) {
    return;
  }
  const listRetry = target.closest<HTMLElement>("[data-flow-list-retry]");
  if (listRetry !== null) {
    if (listRetry.getAttribute("aria-disabled") === "true") {
      return;
    }
    loadFlowList({ retryButton: listRetry });
    return;
  }
  const deleteButton = target.closest<HTMLElement>("[data-flow-delete]");
  if (deleteButton !== null) {
    openFlowConfirm({ button: deleteButton });
    return;
  }
  const cancelButton = target.closest<HTMLElement>(
    "[data-flow-confirm-cancel]",
  );
  if (cancelButton !== null) {
    if (cancelButton.getAttribute("aria-disabled") !== "true") {
      closeFlowConfirm({ id: getCardFlowId({ element: cancelButton }) });
    }
    return;
  }
  const confirmButton = target.closest<HTMLElement>(
    "[data-flow-confirm-delete]",
  );
  if (confirmButton !== null) {
    submitFlowDelete({ button: confirmButton });
    return;
  }
  const retry = target.closest<HTMLElement>("[data-flow-retry]");
  if (retry === null) {
    return;
  }
  const card = retry.closest<HTMLElement>(".flow-card");
  const id = card?.dataset.flowId;
  const grid = getElementByIdOrNull<HTMLElement>(FLOWS_GRID_ID);
  if (id === undefined || grid === null) {
    return;
  }
  _flowStates.delete(id);
  if (!_flowLoadQueue.isPending({ id })) {
    setFlowsPanelBusy({ busy: true });
    _flowLoadQueue.enqueue({ ids: [id] });
  }
  renderFlowsPanel();
  findFlowCard({ grid, id })?.focus();
}

/**
 * Test-only: drop one flow id (aborts its request, clears cache and state).
 */
export function _dropFlowIdForTests({ id }: { id: string }): void {
  _flowLoadQueue.dropId({ id });
  _flowCache.delete(id);
  _flowStates.delete(id);
  renderFlowsPanel();
}

/**
 * Render the Gauges panel from `_gaugesCache`. Owns the no-data case (DD): when
 * the cache is `null` or carries an empty `gauges[]`, the grid is cleared and a
 * single panel-level `MetricsEmptyState` element is appended — `renderGaugeGrid`
 * itself never emits an empty state. Otherwise every gauge card is rendered (and
 * reconciled in place) from the full cached batched response.
 */
function renderGaugesPanel(): void {
  const grid = getElementByIdOrNull<HTMLElement>(GAUGES_GRID_ID);
  if (grid === null) {
    return;
  }
  if (_gaugesCache === null || _gaugesCache.gauges.length === 0) {
    while (grid.firstChild !== null) {
      grid.removeChild(grid.firstChild);
    }
    const emptyState = document.createElement("p");
    emptyState.className = "MetricsEmptyState";
    emptyState.tabIndex = 0;
    emptyState.textContent = APP_CONFIG.strings.METRICS_GAUGES_EMPTY;
    grid.appendChild(emptyState);
    return;
  }
  renderGaugeGrid({
    container: grid,
    response: _gaugesCache,
    selectedGaugeName: _selectedGaugeName,
  });
}

/**
 * Fire the single batched `gauges/timeseries` request (mirrors the single-XHR
 * `fetchPipelineHealth()` shape, NOT the per-flow fan-out). One request returns
 * every gauge's windowed series; the batched response is cached and the panel
 * re-rendered on success. `_currentWindow` is read here, so each window change
 * re-requests the batched series (DD-10).
 *
 * Deliberately separate from `fetchAll`'s global busy / `onSettleAny` path:
 * gauge settle-state lives only on `#MetricsPanelGauges` aria-busy (DD-7).
 */
function fetchGauges(): void {
  setGaugesPanelBusy({ busy: true });
  let succeeded = false;
  const gaugesRequest = fetchGaugesTimeseries({ window: _currentWindow });
  _inFlight.gaugesTimeseries = gaugesRequest;
  gaugesRequest
    .done((response) => {
      succeeded = true;
      setBannerVisible({ visible: false });
      _gaugesCache = response;
      renderGaugesPanel();
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
      _inFlight.gaugesTimeseries = null;
      _lastFetchPerf = performance.now();
      setGaugesPanelBusy({ busy: false });
      if (succeeded) {
        const announcement = getElementByIdOrNull<HTMLElement>(
          GAUGES_ANNOUNCEMENT_ID,
        );
        if (announcement !== null) {
          announcement.textContent = APP_CONFIG.strings.METRICS_GAUGES_LOADED;
        }
      }
    });
}

/**
 * Render the Latency percentile table from `_latencyCache`. The renderer owns the
 * empty / no-match states (HTML `<tr><td colspan>` rows) and the no-selection
 * prompt; when a row is selected the detail container is left for
 * `fetchLatencyTimeseries`'s `.done` to fill with the chart.
 */
function renderLatencyPanelFromCache(): void {
  const tableRoot = getElementByIdOrNull<HTMLTableElement>(LATENCY_TABLE_ID);
  const detailRoot = getElementByIdOrNull<HTMLElement>(
    LATENCY_CHART_CONTAINER_ID,
  );
  if (tableRoot === null || detailRoot === null || _latencyCache === null) {
    return;
  }
  renderLatencyPanel({
    tableRoot,
    detailRoot,
    response: _latencyCache,
    selectedEndpoint: _selectedLatencyEndpoint,
    selectedMethod: _selectedLatencyMethod,
    approximate: _latencyCache.approximate ?? false,
  });
}

/**
 * Fetch the selected endpoint's latency timeseries and render the multi-series
 * chart into the detail container. Reads `_selectedLatencyEndpoint` /
 * `_selectedLatencyMethod` at invocation time. No-op when no row is selected.
 * Excluded from the global busy path (its own `latencyTimeseries` slot).
 */
function fetchLatencyTimeseries(): void {
  if (_selectedLatencyEndpoint === null) {
    return;
  }
  if (_inFlight.latencyTimeseries !== null) {
    _inFlight.latencyTimeseries.abort();
    _inFlight.latencyTimeseries = null;
  }
  const detailRoot = getElementByIdOrNull<HTMLElement>(
    LATENCY_CHART_CONTAINER_ID,
  );
  const request = fetchLatencyTimeseriesClient({
    window: _currentWindow,
    endpoint: _selectedLatencyEndpoint,
    method: _selectedLatencyMethod,
    resolution: LONG_WINDOWS.has(_currentWindow) ? "day" : "hour",
  });
  _inFlight.latencyTimeseries = request;
  request
    .done((response) => {
      setBannerVisible({ visible: false });
      if (detailRoot !== null) {
        renderLatencyDetailChart({
          container: detailRoot,
          response,
          daily: LONG_WINDOWS.has(_currentWindow),
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
      _inFlight.latencyTimeseries = null;
      _lastFetchPerf = performance.now();
    });
}

/**
 * Drive the latency `aria-live` announcement off the approximate-state TRANSITION
 * (mirrors the flush-bucket announce guard). Writes the bridged approximate note
 * into `#MetricsPanelLatencyAnnouncement` on a false→true transition and clears it
 * on a true→false transition. Acts only on an actual change of state; the initial
 * `null` counts as a transition (null→true announces, null→false is a no-op clear).
 */
function announceLatencyApproximate({
  approximate,
}: {
  approximate: boolean;
}): void {
  if (approximate === _lastAnnouncedLatencyApproximate) {
    return;
  }
  _lastAnnouncedLatencyApproximate = approximate;
  const announcement = getElementByIdOrNull<HTMLElement>(
    LATENCY_ANNOUNCEMENT_ID,
  );
  if (announcement === null) {
    return;
  }
  announcement.textContent = approximate
    ? APP_CONFIG.strings.METRICS_LATENCY_APPROXIMATE_NOTE
    : "";
}

/**
 * Fire the single batched `/latency` percentile request (mirrors `fetchGauges`).
 * The batched response is cached and the table re-rendered on success. When a row
 * is currently selected, the detail chart is also refreshed via
 * `fetchLatencyTimeseries` so the trend stays current on each poll without a
 * re-click. `_currentWindow` is read here, so each window change re-requests.
 *
 * Deliberately separate from `fetchAll`'s global busy / `onSettleAny` path:
 * latency settle-state lives only on `#MetricsPanelLatency` aria-busy.
 */
function fetchLatency(): void {
  setLatencyPanelBusy({ busy: true });
  const request = fetchLatencyClient({ window: _currentWindow });
  _inFlight.latency = request;
  request
    .done((response) => {
      setBannerVisible({ visible: false });
      _latencyCache = response;
      announceLatencyApproximate({
        approximate: response.approximate ?? false,
      });
      renderLatencyPanelFromCache();
      if (_selectedLatencyEndpoint !== null) {
        fetchLatencyTimeseries();
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
      _inFlight.latency = null;
      _lastFetchPerf = performance.now();
      setLatencyPanelBusy({ busy: false });
    });
}

/**
 * Resolve the clicked `.latency-row`, persist its endpoint+method as the
 * selection, re-render the table (highlighting the row), then fetch + render the
 * detail chart. Clicks outside a `.latency-row` are ignored. Mirrors
 * `handleGaugeRowClick`.
 */
function handleLatencyRowClick(event: JQuery.TriggeredEvent): void {
  const row = (event.target as HTMLElement).closest<HTMLTableRowElement>(
    "tr.latency-row",
  );
  if (row === null) {
    return;
  }
  const endpoint = row.dataset.endpoint;
  if (endpoint === undefined || endpoint === "") {
    return;
  }
  _selectedLatencyEndpoint = endpoint;
  _selectedLatencyMethod =
    row.dataset.method !== undefined && row.dataset.method !== ""
      ? row.dataset.method
      : null;
  renderLatencyPanelFromCache();
  fetchLatencyTimeseries();

  const container = getElementByIdOrNull<HTMLElement>(
    LATENCY_CHART_CONTAINER_ID,
  );
  container?.scrollIntoView({ behavior: "smooth", block: "start" });
}

/**
 * Keyboard activation for latency rows. Enter and Space both fire the same action
 * as a mouse click (ARIA APG for a focusable non-button widget).
 */
function handleLatencyRowKeydown(event: JQuery.TriggeredEvent): void {
  const key = event.key;
  if (key !== "Enter" && key !== " ") {
    return;
  }
  event.preventDefault();
  handleLatencyRowClick(event);
}

function fetchAll(): void {
  abortInFlightRequests();
  _flowLoadQueue.abortAll();
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
    loadFlowList();
  } else {
    // The abort above ended any running flow loads, so cached cards are stale
    // for the new window: abort the list request, mark the list for a fresh
    // request on return (the retained list still renders), and clear the panel
    // busy flag silently (no completion announcement).
    abortFlowListRequest({ replacement: false });
    _flowListStatus = "idle";
    setFlowsPanelBusy({ busy: false });
  }

  // Gate the single batched gauges request on the active tab (same pattern as
  // the Flows gate). `fetchGauges()` reads `_currentWindow`, so each window
  // change re-requests the batched series — keeping the window selector live on
  // the Gauges tab for free (DD-10).
  if (_activeTab === TAB.GAUGES) {
    fetchGauges();
  }

  // Gate the batched latency request on the active tab (same pattern as the
  // Gauges gate). `fetchLatency()` reads `_currentWindow`, so each window change
  // re-requests — keeping the window selector live on the Latency tab.
  if (_activeTab === TAB.LATENCY) {
    fetchLatency();
  }
}

/**
 * Clear UI in-flight indicators when no requests remain pending. Both
 * `aria-busy` on the dashboard root and the Refresh button's `aria-disabled`
 * track the union of all in-flight requests.
 *
 * Flow loads are excluded — tracked via #MetricsPanelFlows aria-busy instead.
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
  const previousTab = _activeTab;
  _activeTab = tab;
  if (previousTab !== TAB.FLOWS && tab === TAB.FLOWS) {
    // Returning to Flows: a failure that landed while away must not surface
    // as a stale, unannounced message.
    _flowCardMessages.clear();
  }
  if (previousTab === TAB.FLOWS && tab !== TAB.FLOWS) {
    // Leaving Flows: a list that resolves later must not start a fan-out.
    abortFlowListRequest({ replacement: false });
    // An open confirm and the messages that exist now are dropped; a
    // `deleting` confirm is kept until its DELETE settles.
    if (_flowConfirm?.phase === "open") {
      _flowConfirm = null;
    }
    _flowCardMessages.clear();
    clearFlowNotice();
  }
  if (
    tab !== TAB.PIPELINE_HEALTH &&
    tab !== TAB.FLOWS &&
    tab !== TAB.GAUGES &&
    tab !== TAB.LATENCY
  ) {
    _currentCategory = tab;
  }

  // The global summary section reports window-wide EVENT totals, so it is
  // hidden on the Flows and Gauges tabs: Flows carries its own per-funnel
  // conversion summaries, and Gauges shows sampled scalar values that the event
  // totals say nothing about. It stays visible on the event-category tabs.
  const summarySection = getElementByIdOrNull<HTMLElement>(SUMMARY_SECTION_ID);
  if (summarySection !== null) {
    if (tab === TAB.FLOWS || tab === TAB.GAUGES || tab === TAB.LATENCY) {
      summarySection.setAttribute("hidden", "");
    } else {
      summarySection.removeAttribute("hidden");
    }
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
  if (
    tab !== TAB.PIPELINE_HEALTH &&
    tab !== TAB.FLOWS &&
    tab !== TAB.GAUGES &&
    tab !== TAB.LATENCY
  ) {
    renderCategoryPanelFromCache({ category: tab });
  }

  // First activation of the Flows tab fires the fan-out immediately rather
  // than waiting up to 60 s for the next `fetchAll` tick. Subsequent switches
  // re-render from the warm cache.
  if (tab === TAB.FLOWS) {
    if (_flowListStatus === "idle" && _flowListXhr === null) {
      loadFlowList();
    } else {
      if (_flowListStatus === "loaded") {
        catchUpFlowLoads();
      }
      renderFlowsPanel();
    }
  }

  // First activation of the Gauges tab fires the single batched request
  // immediately; subsequent switches re-render from the warm cache.
  if (tab === TAB.GAUGES) {
    if (_gaugesCache === null) {
      fetchGauges();
    } else {
      renderGaugesPanel();
    }
  }

  // First activation of the Latency tab fires the batched request immediately;
  // subsequent switches re-render the table from the warm cache (no round-trip).
  if (tab === TAB.LATENCY) {
    if (_latencyCache === null) {
      fetchLatency();
    } else {
      renderLatencyPanelFromCache();
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

  // Delegate gauge row click + keydown on the stable grid container. The table
  // (and its rows) is rebuilt by `renderGaugeGrid` on each render, but events
  // bubble from those rows to the server-rendered grid, so a single binding at
  // init covers every subsequent render — mirrors the top-table tbody binding.
  const gaugeGrid = getElementByIdOrNull<HTMLElement>(GAUGES_GRID_ID);
  if (gaugeGrid !== null) {
    $(gaugeGrid).offAndOnExact(
      "click.metricsDashboardGaugeRow",
      handleGaugeRowClick,
    );
    $(gaugeGrid).offAndOnExact(
      "keydown.metricsDashboardGaugeRow",
      handleGaugeRowKeydown,
    );
  }

  // Delegate latency-row click + keydown on the stable percentile table. The
  // table body is rebuilt on each render, but events bubble from the rows to the
  // server-rendered table, so one binding at init covers every subsequent
  // render — mirrors the gauge-grid binding.
  const latencyTable = getElementByIdOrNull<HTMLElement>(LATENCY_TABLE_ID);
  if (latencyTable !== null) {
    $(latencyTable).offAndOnExact(
      "click.metricsDashboardLatencyRow",
      handleLatencyRowClick,
    );
    $(latencyTable).offAndOnExact(
      "keydown.metricsDashboardLatencyRow",
      handleLatencyRowKeydown,
    );
  }

  // Delegate Retry clicks (per-card and list) on the stable flow grid: the
  // cards are rebuilt on each render, so one binding at init covers them all.
  const flowGrid = getElementByIdOrNull<HTMLElement>(FLOWS_GRID_ID);
  if (flowGrid !== null) {
    $(flowGrid).offAndOnExact(
      "click.metricsDashboardFlowGrid",
      handleFlowGridClick,
    );
    $(flowGrid).offAndOnExact(
      "keydown.metricsDashboardFlowGrid",
      handleFlowGridKeydown,
    );
  }

  document.addEventListener("visibilitychange", handleVisibilityChange);

  initPaneResizers();

  // `_activeTab` defaults to Gauges, so `fetchAll`'s active-tab gate fires the
  // batched gauges request on load — no separate call needed.
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
  _flowLoadQueue.abortAll();
  abortFlowListRequest({ replacement: false });
  _flowList = null;
  _flowListStatus = "idle";
  resetFlowListSlot();
  _flowListErrorShown = false;
  _flowListRetryButton = null;
  const staleDeleteXhr = _flowDeleteXhr;
  _flowDeleteXhr = null;
  staleDeleteXhr?.abort();
  _flowConfirm = null;
  _flowCardMessages.clear();
  if (_flowActionAnnounceTimer !== null) {
    clearTimeout(_flowActionAnnounceTimer);
    _flowActionAnnounceTimer = null;
  }
  _lastFetchPerf = 0;
  _currentWindow = "day";
  _currentCategory = TAB.API;
  _activeTab = TAB.GAUGES;
  _inFlight = {
    topApi: null,
    topUi: null,
    topDomain: null,
    tsApi: null,
    tsUi: null,
    tsDomain: null,
    summary: null,
    pipelineHealth: null,
    gaugesTimeseries: null,
    latency: null,
    latencyTimeseries: null,
  };
  _flowCache.clear();
  _flowStates.clear();
  _gaugesCache = null;
  _selectedGaugeName = null;
  _latencyCache = null;
  _selectedLatencyEndpoint = null;
  _selectedLatencyMethod = null;
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
  _lastAnnouncedLatencyApproximate = null;
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
