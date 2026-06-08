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

import { APP_CONFIG } from "../lib/config.js";
import { $ } from "../lib/globals.js";
import { is429Handled } from "../lib/ajax.js";

import {
  fetchSummary,
  fetchTimeseries,
  fetchTopEvents,
} from "./metrics-query-client.js";
import { renderSummary } from "./render-summary.js";
import { renderTimeseriesChart } from "./render-timeseries-chart.js";
import { renderTopTable } from "./render-top-table.js";

type MetricsWindow = "day" | "week" | "month" | "year";
type MetricsCategory = "api" | "ui" | "domain";
type TopEventsResponseSchema = Schema<"TopEventsResponseSchema">;
type LastFlushBucket = "just_now" | "seconds" | "minutes" | "stale";

interface InFlightRequests {
  topApi: JQuery.jqXHR | null;
  topUi: JQuery.jqXHR | null;
  topDomain: JQuery.jqXHR | null;
  tsApi: JQuery.jqXHR | null;
  tsUi: JQuery.jqXHR | null;
  tsDomain: JQuery.jqXHR | null;
  summary: JQuery.jqXHR | null;
}

interface CategoryPanelIds {
  tbody: string;
  chart: string;
  select: string;
  tab: string;
  panel: string;
}

const POLL_INTERVAL_MS = 60_000;
const VISIBILITY_REFETCH_THRESHOLD_MS = 5_000;
const BADGE_TICK_INTERVAL_MS = 1_000;
const BADGE_BUCKET_SECONDS_MS = 5_000;
const BADGE_BUCKET_MINUTES_MS = 60_000;
const BADGE_BUCKET_STALE_MS = 3_600_000;
const BADGE_STALE_CLASS = "MetricsBadgeStale";

const DASHBOARD_ROOT_ID = "MetricsDashboard";
const REFRESH_BUTTON_ID = "MetricsRefreshNowBtn";
const ERROR_BANNER_ID = "MetricsErrorBanner";
const LAST_FLUSH_BADGE_ID = "MetricsLastFlush";
const LAST_FLUSH_TEXT_ID = "MetricsLastFlushText";
const LAST_FLUSH_ANNOUNCEMENT_ID = "MetricsLastFlushAnnouncement";
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
  },
  ui: {
    tbody: "MetricsTopTableUi",
    chart: "MetricsChartUi",
    select: "MetricsTimeseriesEventUi",
    tab: "MetricsTabUi",
    panel: "MetricsPanelUi",
  },
  domain: {
    tbody: "MetricsTopTableDomain",
    chart: "MetricsChartDomain",
    select: "MetricsTimeseriesEventDomain",
    tab: "MetricsTabDomain",
    panel: "MetricsPanelDomain",
  },
};

// All three categories are kept warm by polling so tab switching is instant.
// Each `.done(...)` writes to `_topCache` and re-renders the panel.
// Tablist navigation order also matches DOM order: API → UI → Domain.
const CATEGORIES: readonly MetricsCategory[] = ["api", "ui", "domain"];

let _pollIntervalId: ReturnType<typeof setInterval> | null = null;
let _lastFetchPerf: number = 0;
let _currentWindow: MetricsWindow = "day";
let _currentCategory: MetricsCategory = "api";
let _inFlight: InFlightRequests = {
  topApi: null,
  topUi: null,
  topDomain: null,
  tsApi: null,
  tsUi: null,
  tsDomain: null,
  summary: null,
};

const TOP_SLOT_BY_CATEGORY: Record<
  MetricsCategory,
  "topApi" | "topUi" | "topDomain"
> = {
  api: "topApi",
  ui: "topUi",
  domain: "topDomain",
};
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
// Records the window each category's chart was last fetched against. When the
// user changes window (Day → Week, etc.), `_currentWindow` advances but each
// panel's chart still shows old-window data until the timeseries re-fetches —
// so `ensureDefaultSelection` re-triggers the change handler whenever this
// map's value diverges from `_currentWindow`, even when the user's event
// selection is still valid.
const _chartFetchedWindowByCategory: Map<MetricsCategory, MetricsWindow> =
  new Map();

// Badge state. `_lastFlushAtMs` is a wall-clock epoch parsed from the server's
// `summary.last_flush_at`, so the elapsed delta MUST be computed with
// `Date.now()` — `performance.now()` is page-load-relative and would yield a
// nonsense delta when subtracted from a wall-clock value.
let _badgeIntervalId: ReturnType<typeof setInterval> | null = null;
let _lastFlushAtMs: number | null = null;
let _lastAnnouncedBucket: LastFlushBucket | null = null;

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
  for (const key of [
    "topApi",
    "topUi",
    "topDomain",
    "tsApi",
    "tsUi",
    "tsDomain",
    "summary",
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
}: {
  category: MetricsCategory;
  response: TopEventsResponseSchema;
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

  for (const event of response.events) {
    const optionElement = document.createElement("option");
    optionElement.value = event.event_name;
    optionElement.textContent = event.event_name;
    // For the API tab, `event_name` is the "<METHOD> <url_pattern>" string
    // built by query_service for display — the real DB event_name is always
    // "api_hit", and the (endpoint, method) pair lives in flat columns. We
    // stash all three on the option so the timeseries handler can issue a
    // properly-filtered query without re-parsing the displayed label.
    if (category === "api") {
      const [methodPart] = event.event_name.split(" ", 1);
      optionElement.dataset.eventName = "api_hit";
      optionElement.dataset.endpoint = event.description;
      optionElement.dataset.method = methodPart;
    } else {
      optionElement.dataset.eventName = event.event_name;
    }
    selectElement.appendChild(optionElement);
  }

  // Restore the previously-selected event when possible so polling refreshes
  // do not silently change the active timeseries series.
  if (previousValue !== "") {
    const matchingEvent = response.events.find(
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

  const tableElement = getElementByIdOrNull<HTMLTableElement>(
    CATEGORY_PANEL_IDS[category].tbody,
  );
  const tbody = tableElement?.querySelector("tbody") ?? null;
  if (tbody !== null) {
    renderTopTable({
      tbody: tbody as HTMLTableSectionElement,
      events: cachedResponse.events,
      selectedEventName: _selectedEventByCategory.get(category) ?? null,
    });
  }

  renderTimeseriesSelect({ category, response: cachedResponse });
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
  const timeseriesRequest = fetchTimeseries({
    eventName,
    window: fetchedWindow,
    resolution: "hour",
    endpoint: apiEndpoint,
    method: apiMethod,
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
 * Fire summary + per-category top-events for the current window. Each
 * `.done` callback writes to the per-category cache and re-renders the
 * active panel; `.fail` shows the error banner (unless the 429 prefilter
 * already replaced the page); every settled response refreshes
 * `_lastFetchPerf` for the visibility-refetch heuristic.
 *
 * Timeseries is fetched lazily — only when the user picks an event from a
 * panel's `<select>`. There is no stable default event to query on poll.
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
      const summaryRoot =
        getElementByIdOrNull<HTMLElement>("MetricsSummaryGrid");
      if (summaryRoot !== null) {
        renderSummary({ root: summaryRoot, response });
      }
      _lastFlushAtMs =
        response.last_flush_at !== null
          ? Date.parse(response.last_flush_at)
          : null;
      renderLastFlushBadge();
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

  for (const category of CATEGORIES) {
    const topRequest = fetchTopEvents({
      window: _currentWindow,
      category,
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
}

/**
 * Clear UI in-flight indicators when no requests remain pending. Both
 * `aria-busy` on the dashboard root and the Refresh button's `aria-disabled`
 * track the union of all three in-flight requests.
 */
function onSettleAny(): void {
  const anyInFlight =
    _inFlight.topApi !== null ||
    _inFlight.topUi !== null ||
    _inFlight.topDomain !== null ||
    _inFlight.tsApi !== null ||
    _inFlight.tsUi !== null ||
    _inFlight.tsDomain !== null ||
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

/**
 * Update `#MetricsLastFlush` with the elapsed time since the server's last
 * Redis-to-Postgres flush. Called every `BADGE_TICK_INTERVAL_MS` while the tab
 * is visible.
 *
 * `Date.now()` (NOT `performance.now()`) is correct here: `_lastFlushAtMs` is
 * `Date.parse(response.last_flush_at)`, a wall-clock epoch supplied by the
 * server. Subtracting a page-load-relative `performance.now()` from a
 * wall-clock epoch would produce a meaningless delta.
 *
 * The visible badge text refreshes every tick. The visually-hidden aria-live
 * sink (`#MetricsLastFlushAnnouncement`) is written only when the bucket
 * transitions, so screen-reader users hear at most four announcements per
 * flush cycle ("just now" → "N seconds" → "N minutes" → "N hours") rather
 * than every-second chatter.
 */
function renderLastFlushBadge(): void {
  const badge = getElementByIdOrNull<HTMLElement>(LAST_FLUSH_BADGE_ID);
  const textNode = getElementByIdOrNull<HTMLElement>(LAST_FLUSH_TEXT_ID);
  if (badge === null || textNode === null) {
    return;
  }

  if (_lastFlushAtMs === null) {
    textNode.textContent = "";
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
  } else if (elapsedMs < BADGE_BUCKET_STALE_MS) {
    text = APP_CONFIG.strings.METRICS_LAST_FLUSH_MINUTES.replace(
      "{{ n }}",
      String(Math.floor(elapsedMs / 60_000)),
    );
    bucket = "minutes";
  } else {
    text = APP_CONFIG.strings.METRICS_LAST_FLUSH_STALE_HOURS.replace(
      "{{ n }}",
      String(Math.floor(elapsedMs / 3_600_000)),
    );
    bucket = "stale";
  }

  textNode.textContent = text;
  if (bucket === "stale") {
    badge.classList.add(BADGE_STALE_CLASS);
  } else {
    badge.classList.remove(BADGE_STALE_CLASS);
  }

  if (bucket !== _lastAnnouncedBucket) {
    const announcement = getElementByIdOrNull<HTMLElement>(
      LAST_FLUSH_ANNOUNCEMENT_ID,
    );
    if (announcement !== null) {
      announcement.textContent = text;
    }
    _lastAnnouncedBucket = bucket;
  }
}

function startBadgeTicker(): void {
  if (_badgeIntervalId !== null) {
    clearInterval(_badgeIntervalId);
  }
  _badgeIntervalId = setInterval(renderLastFlushBadge, BADGE_TICK_INTERVAL_MS);
  renderLastFlushBadge();
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
  tabId: _tabId,
  category,
}: {
  tabId: string;
  category: MetricsCategory;
}): void {
  _currentCategory = category;

  for (const candidateCategory of CATEGORIES) {
    const isActive = candidateCategory === category;
    const tabElement = getElementByIdOrNull<HTMLButtonElement>(
      CATEGORY_PANEL_IDS[candidateCategory].tab,
    );
    if (tabElement !== null) {
      tabElement.setAttribute("aria-selected", isActive ? "true" : "false");
      tabElement.setAttribute("tabindex", isActive ? "0" : "-1");
    }

    const panelElement = getElementByIdOrNull<HTMLElement>(
      CATEGORY_PANEL_IDS[candidateCategory].panel,
    );
    if (panelElement !== null) {
      if (isActive) {
        panelElement.removeAttribute("hidden");
      } else {
        panelElement.setAttribute("hidden", "");
      }
    }
  }

  // Re-render the active panel from cache so the latest top-events list and
  // select options are visible immediately after the switch.
  renderCategoryPanelFromCache({ category });

  const activePanel = getElementByIdOrNull<HTMLElement>(
    CATEGORY_PANEL_IDS[category].panel,
  );
  activePanel?.focus();
}

function handleTabButtonClick(event: JQuery.TriggeredEvent): void {
  const tabElement = event.currentTarget as HTMLButtonElement;
  const category = tabElement.dataset.category as MetricsCategory | undefined;
  if (category === undefined) {
    return;
  }
  handleTabClick({ tabId: tabElement.id, category });
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
  const currentCategory = tabElement.dataset.category as
    | MetricsCategory
    | undefined;
  if (currentCategory === undefined) {
    return;
  }
  const currentIndex = CATEGORIES.indexOf(currentCategory);
  if (currentIndex === -1) {
    return;
  }

  let nextIndex: number;
  if (key === "ArrowLeft") {
    nextIndex = (currentIndex - 1 + CATEGORIES.length) % CATEGORIES.length;
  } else if (key === "ArrowRight") {
    nextIndex = (currentIndex + 1) % CATEGORIES.length;
  } else if (key === "Home") {
    nextIndex = 0;
  } else {
    nextIndex = CATEGORIES.length - 1;
  }

  event.preventDefault();

  const nextCategory = CATEGORIES[nextIndex];
  const nextTabElement = getElementByIdOrNull<HTMLButtonElement>(
    CATEGORY_PANEL_IDS[nextCategory].tab,
  );
  handleTabClick({
    tabId: CATEGORY_PANEL_IDS[nextCategory].tab,
    category: nextCategory,
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
  }

  document.addEventListener("visibilitychange", handleVisibilityChange);

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
  _currentCategory = "api";
  _inFlight = {
    topApi: null,
    topUi: null,
    topDomain: null,
    tsApi: null,
    tsUi: null,
    tsDomain: null,
    summary: null,
  };
  _topCache.clear();
  _selectedEventByCategory.clear();
  _chartFetchedWindowByCategory.clear();
  _lastFlushAtMs = null;
  _lastAnnouncedBucket = null;
  document.removeEventListener("visibilitychange", handleVisibilityChange);
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
