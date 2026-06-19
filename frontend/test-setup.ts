import jquery from "jquery";

// Provide jQuery on window before any module imports (mirrors global script tag)
window.jQuery = jquery;
window.$ = jquery;

// Approved exception to top-level-imports rule: window.jQuery must be assigned
// before jquery-plugins evaluates, requiring deferred loading that cannot be
// moved to module scope.
const { registerJQueryPlugins } = await import("./lib/jquery-plugins.js");
registerJQueryPlugins();

// Factory for Bootstrap component mocks — each component shares the same
// constructor/show/hide/dispose/getInstance/getOrCreateInstance shape.
function makeBootstrapClass(
  componentName: string,
  extra?: Record<string, () => void>,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- test mock; full bootstrap typing not needed
): any {
  const ComponentClass = class {
    constructor() {}
    show() {}
    hide() {}
    dispose() {}
    static getInstance() {
      return null;
    }
    static getOrCreateInstance() {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any -- dynamic bootstrap mock access
      return new (window.bootstrap as any)[componentName]();
    }
  };
  if (extra) {
    Object.assign(ComponentClass.prototype, extra);
  }
  Object.defineProperty(ComponentClass, "name", { value: componentName });
  return ComponentClass;
}

// Mock Bootstrap (mirrors global script tag)
window.bootstrap = {
  Modal: makeBootstrapClass("Modal"),
  Tooltip: makeBootstrapClass("Tooltip"),
  Toast: makeBootstrapClass("Toast"),
  Collapse: makeBootstrapClass("Collapse", { toggle() {} }),
  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- test mock; full bootstrap typing not needed
} as any;

// Inject app-config script element for lib/config.js
const appConfig = {
  routes: {
    home: "/",
    createUTub: "/utubs",
    getUTubs: "/utubs",
    login: "/login",
    register: "/register",
    confirmEmailAfterRegister: "/confirm-email",
    sendValidationEmail: "/send-validation-email",
    forgotPassword: "/forgot-password",
    errorPage: "/error",
    logout: "/logout",
    getUTub: "/utubs/-1",
    deleteUTub: "/utubs/-1",
    updateUTubName: "/utubs/-1/name",
    updateUTubDescription: "/utubs/-1/description",
    getURL: "/utubs/-1/urls/-2",
    createURL: "/utubs/-1/urls",
    deleteURL: "/utubs/-1/urls/-2",
    updateURL: "/utubs/-1/urls/-2",
    updateURLTitle: "/utubs/-1/urls/-2/title",
    createURLTag: "/utubs/-1/urls/-2/tags",
    deleteURLTag: "/utubs/-1/urls/-2/tags/-3",
    createUTubTag: "/utubs/-1/tags",
    deleteUTubTag: "/utubs/-1/tags/-2",
    createMember: "/utubs/-1/members",
    removeMember: "/utubs/-1/members/-4",
    contactUs: "/contact",
    crossUtubSearch: "/search",
  },
  constants: {
    UTUBS_MIN_NAME_LENGTH: 1,
    URLS_MIN_LENGTH: 1,
    URLS_TITLE_MIN_LENGTH: 1,
    URLS_TITLE_MAX_LENGTH: 100,
    MEMBER_ROLES: {
      CREATOR: "CREATOR",
      CO_CREATOR: "CO_CREATOR",
    },
    // Source of truth: backend/metrics/dimension_models.py (DIMENSION_MODELS registry).
    // — keep this array in sync when DIMENSION_MODELS changes.
    DIMENSION_KEYS: [
      "active_tag_count",
      "deck",
      "device_type",
      "form",
      "result",
      "scope",
      "search_active",
      "target",
      "trigger",
    ],
    // Source of truth: backend/metrics/events.py (DeviceType IntEnum).
    DEVICE_TYPE: {
      MOBILE: 1,
      DESKTOP: 2,
    },
    // Source of truth: backend/metrics/events.py (DEVICE_TYPE_DIM_KEY).
    DEVICE_TYPE_DIM_KEY: "device_type",
  },
  strings: {
    COOKIE_BANNER_SEEN: "cookie_banner_seen=true",
    EDIT_URL_TITLE_TOOLTIP: "Edit URL title",
    INVALID_URL: "This is not a valid URL.",
    TAG_FILTER_NO_RESULTS: "No URLs match selected tags",
    URL_SEARCH_NO_RESULTS: "No URLs found",
    UTUB_NO_URLS: "No URLs yet",
    ADD_URL_BUTTON: "Add URL",
    CROSS_SEARCH_NO_RESULTS: "No results found across your UTubs",
    CROSS_SEARCH_SHORT_QUERY:
      "Type a search and press Enter or the search button",
    CROSS_SEARCH_PLACEHOLDER: "Search all your UTubs",
    CROSS_SEARCH_COUNT_TEMPLATE: "{{ count }} results across {{ utubs }} UTubs",
    CROSS_SEARCH_FIELD_URL: "URL",
    CROSS_SEARCH_FIELD_TITLE: "Title",
    CROSS_SEARCH_FIELD_TAG: "Tag",
    CROSS_SEARCH_HISTORY_HEADING: "Recent searches",
    CROSS_SEARCH_HISTORY_CLEAR: "Clear",
    CROSS_SEARCH_TRIGGER_OPEN_LABEL: "Search across your UTubs",
    CROSS_SEARCH_TRIGGER_CLOSE_LABEL: "Close search",
    CROSS_SEARCH_SUBMIT_LABEL: "Search across your UTubs",
    CROSS_SEARCH_REFRESH_LABEL: "Refresh these search results",
    VALIDATE_MY_EMAIL: "Validate My Email",
    UTUB_SEARCH_NO_RESULTS: "No UTubs found",
    UTUB_SEARCH_PLACEHOLDER: "Search UTub Names",
    UTUB_SEARCH_COUNT_TEMPLATE: "{{ visible }} of {{ total }} UTubs shown",
    UTUB_CREATE_MSG: "Create a UTub",
    // Admin Metrics Dashboard strings — source of truth: backend/utils/strings/admin_metrics_strs.py.
    // Only keys read by production TS are mirrored here. Jinja-only labels are inline in templates;
    // Python-test-only keys live in ui_testing_strs.py. Vitest runs in Node with no Flask app context,
    // so APP_CONFIG must be hand-mocked.
    METRICS_TIMESERIES_SELECT_ARIA: "Select event for timeseries chart",
    METRICS_LAST_FLUSH_UNKNOWN: "Last flush unknown",
    METRICS_LAST_FLUSH_JUST_NOW: "Last flush just now",
    METRICS_LAST_FLUSH_SECONDS: "Last flush {{ n }}s ago",
    METRICS_LAST_FLUSH_MINUTES: "Last flush {{ n }}m ago",
    METRICS_LAST_FLUSH_STALE_MINUTES: "Last flush {{ n }}m ago (stale)",
    METRICS_LAST_FLUSH_STALE_HOURS: "Last flush {{ n }}h ago (stale)",
    METRICS_LAST_EVENT_UNKNOWN: "Last event unknown",
    METRICS_LAST_EVENT_JUST_NOW: "Last event just now",
    METRICS_LAST_EVENT_SECONDS: "Last event {{ n }}s ago",
    METRICS_LAST_EVENT_MINUTES: "Last event {{ n }}m ago",
    METRICS_LAST_EVENT_HOURS: "Last event {{ n }}h ago",
    METRICS_EMPTY_STATE: "No events recorded in the selected window.",
    METRICS_FETCH_FAILED_BANNER:
      "Refresh failed — showing last successful data. Retrying in 60 seconds.",
    METRICS_SUMMARY_TOTAL_EVENTS: "Total Events",
    METRICS_SUMMARY_API_HITS: "API hits",
    METRICS_SUMMARY_UI_EVENTS: "UI events",
    METRICS_SUMMARY_DOMAIN_ACTIONS: "Domain actions",
    METRICS_SUMMARY_DELTA_SUFFIX: " vs prev",
    METRICS_SUMMARY_DELTA_UNAVAILABLE: "—",
    METRICS_TOP_TABLE_HEADER_RANK: "#",
    METRICS_TOP_TABLE_HEADER_ENDPOINT: "Endpoint",
    METRICS_TOP_TABLE_HEADER_EVENT: "Event",
    METRICS_TOP_TABLE_HEADER_ACTION: "Action",
    METRICS_TOP_TABLE_HEADER_HITS: "Hits",
    METRICS_TOP_TABLE_HEADER_DELTA: "Δ vs prev",
    METRICS_TOP_TABLE_ROW_ARIA: "Show timeseries for {{ name }}",
    METRICS_CHART_Y_AXIS_LABEL: "Count",
    METRICS_TOP_RESOURCE_ALL: "All resources",
    METRICS_TOP_RESOURCE_UTUB: "UTubs",
    METRICS_TOP_RESOURCE_URL: "URLs",
    METRICS_TOP_RESOURCE_TAG: "Tags",
    METRICS_TOP_RESOURCE_MEMBER: "Members",
    METRICS_TOP_RESOURCE_AUTH: "Auth",
    METRICS_TOP_RESOURCE_SEARCH: "Search",
    METRICS_TOP_RESOURCE_FORM: "Forms",
    METRICS_TOP_RESOURCE_DECK: "Deck",
    METRICS_TOP_RESOURCE_NAV: "Navigation",
    METRICS_TOP_RESOURCE_ERROR: "Errors",
    METRICS_TOP_RESOURCE_CONTACT: "Contact",
    METRICS_TOP_RESOURCE_ADMIN: "Admin",
    METRICS_TOP_RESOURCE_OTHER: "Other",
    METRICS_TOP_DEVICE_ALL: "All devices",
    METRICS_TOP_DEVICE_MOBILE: "Mobile",
    METRICS_TOP_DEVICE_DESKTOP: "Desktop",
    METRICS_TOP_EMPTY_NO_MATCHES: "No events match the current filter.",
    METRICS_PIPELINE_HEALTH_TITLE: "Pipeline Health",
    METRICS_PIPELINE_HEALTH_EMPTY_STATE:
      "No ingest batches recorded in the selected window.",
    METRICS_PIPELINE_HEALTH_AXIS_LABEL: "Batches",
    METRICS_PIPELINE_HEALTH_AXIS_LABEL_X: "Events per batch",
    METRICS_PIPELINE_HEALTH_LEGEND_FETCH_DESKTOP: "fetch · desktop",
    METRICS_PIPELINE_HEALTH_LEGEND_FETCH_MOBILE: "fetch · mobile",
    METRICS_PIPELINE_HEALTH_LEGEND_BEACON_DESKTOP: "beacon · desktop",
    METRICS_PIPELINE_HEALTH_LEGEND_BEACON_MOBILE: "beacon · mobile",
    METRICS_PIPELINE_HEALTH_CHART_DESC:
      "Stacked bar chart of accepted ingest batches grouped by batch size and split by transport and device type.",
    METRICS_FLOW_SUCCEEDED: "succeeded",
    METRICS_FLOW_CONVERSION: "conversion",
    METRICS_FLOW_DROPOFF: "drop-off",
    METRICS_FLOW_CATEGORY_UI: "UI",
    METRICS_FLOW_CATEGORY_API: "API",
    METRICS_FLOW_CATEGORY_DOMAIN: "Domain",
    METRICS_FLOW_EMPTY: "No funnel activity recorded in the selected window.",
    METRICS_FLOWS_LOADED: "Flow funnels updated.",
    METRICS_GAUGE_KIND_VOLUME: "Volume",
    METRICS_GAUGE_KIND_DISTRIBUTION_MAX: "Distribution (max)",
    METRICS_GAUGE_KIND_DISTRIBUTION_AVG: "Distribution (avg)",
    METRICS_GAUGE_SUPPRESSED_ARIA: "Value unavailable",
    METRICS_GAUGES_LOADED: "Gauge values updated.",
    METRICS_GAUGE_SELECT_PROMPT: "Select a gauge to view its timeseries.",
    METRICS_GAUGE_COL_NAME: "Gauge",
    METRICS_GAUGE_COL_VALUE: "Value",
    METRICS_GAUGES_EMPTY: "No gauge samples recorded in the selected window.",
  },
};

const configScript = document.createElement("script");
configScript.id = "app-config";
configScript.type = "application/json";
configScript.textContent = JSON.stringify(appConfig);
document.head.appendChild(configScript);
