from backend.metrics.suppression import MIN_CELL_COUNT
from backend.utils.strings import metric_flow_strs


class ADMIN_METRICS_STRINGS:
    METRICS_DASHBOARD_TITLE: str = "Anonymous Metrics — Admin Dashboard"
    METRICS_REFRESH_BUTTON_LABEL: str = "Refresh"
    METRICS_TAB_API: str = "Top Endpoints"
    METRICS_TAB_UI: str = "Top UI Events"
    METRICS_TAB_DOMAIN: str = "Top Domain Actions"
    METRICS_TAB_PIPELINE_HEALTH: str = "Pipeline Health"
    METRICS_TAB_FLOWS: str = "Flows"
    METRICS_TAB_GAUGES: str = "Gauges"
    METRICS_TIMESERIES_SELECT_ARIA: str = "Select event for timeseries chart"
    METRICS_LAST_FLUSH_UNKNOWN: str = "Last flush unknown"
    METRICS_LAST_FLUSH_JUST_NOW: str = "Last flush just now"
    METRICS_LAST_FLUSH_SECONDS: str = "Last flush {{ n }}s ago"
    METRICS_LAST_FLUSH_MINUTES: str = "Last flush {{ n }}m ago"
    METRICS_LAST_FLUSH_STALE_MINUTES: str = "Last flush {{ n }}m ago (stale)"
    METRICS_LAST_FLUSH_STALE_HOURS: str = "Last flush {{ n }}h ago (stale)"
    METRICS_LAST_EVENT_UNKNOWN: str = "Last event unknown"
    METRICS_LAST_EVENT_JUST_NOW: str = "Last event just now"
    METRICS_LAST_EVENT_SECONDS: str = "Last event {{ n }}s ago"
    METRICS_LAST_EVENT_MINUTES: str = "Last event {{ n }}m ago"
    METRICS_LAST_EVENT_HOURS: str = "Last event {{ n }}h ago"
    METRICS_EMPTY_STATE: str = "No events recorded in the selected window."
    METRICS_FETCH_FAILED_BANNER: str = (
        "Refresh failed — showing last successful data. Retrying in 60 seconds."
    )
    METRICS_SUMMARY_TOTAL_EVENTS: str = "Total Events"
    METRICS_SUMMARY_API_HITS: str = "API hits"
    METRICS_SUMMARY_UI_EVENTS: str = "UI events"
    METRICS_SUMMARY_DOMAIN_ACTIONS: str = "Domain actions"
    METRICS_SUMMARY_DELTA_SUFFIX: str = " vs prev"
    METRICS_SUMMARY_DELTA_UNAVAILABLE: str = "—"
    METRICS_TOP_TABLE_HEADER_RANK: str = "#"
    METRICS_TOP_TABLE_HEADER_ENDPOINT: str = "Endpoint"
    METRICS_TOP_TABLE_HEADER_EVENT: str = "Event"
    METRICS_TOP_TABLE_HEADER_ACTION: str = "Action"
    METRICS_TOP_TABLE_HEADER_HITS: str = "Hits"
    METRICS_TOP_TABLE_HEADER_DELTA: str = "Δ vs prev"
    METRICS_TOP_TABLE_ROW_ARIA: str = "Show timeseries for {{ name }}"
    METRICS_CHART_Y_AXIS_LABEL: str = "Count"
    METRICS_TOP_RESOURCE_ALL: str = "All resources"
    METRICS_TOP_RESOURCE_UTUB: str = "UTubs"
    METRICS_TOP_RESOURCE_URL: str = "URLs"
    METRICS_TOP_RESOURCE_TAG: str = "Tags"
    METRICS_TOP_RESOURCE_MEMBER: str = "Members"
    METRICS_TOP_RESOURCE_AUTH: str = "Auth"
    METRICS_TOP_RESOURCE_SEARCH: str = "Search"
    METRICS_TOP_RESOURCE_FORM: str = "Forms"
    METRICS_TOP_RESOURCE_DECK: str = "Deck"
    METRICS_TOP_RESOURCE_NAV: str = "Navigation"
    METRICS_TOP_RESOURCE_ERROR: str = "Errors"
    METRICS_TOP_RESOURCE_CONTACT: str = "Contact"
    METRICS_TOP_RESOURCE_ADMIN: str = "Admin"
    METRICS_TOP_RESOURCE_ONBOARDING: str = "Onboarding"
    METRICS_TOP_RESOURCE_OTHER: str = "Other"
    METRICS_TOP_DEVICE_ALL: str = "All devices"
    METRICS_TOP_DEVICE_MOBILE: str = "Mobile"
    METRICS_TOP_DEVICE_DESKTOP: str = "Desktop"
    METRICS_TOP_EMPTY_NO_MATCHES: str = "No events match the current filter."
    METRICS_PIPELINE_HEALTH_TITLE: str = "Pipeline Health"
    METRICS_PIPELINE_HEALTH_EMPTY_STATE: str = (
        "No ingest batches recorded in the selected window."
    )
    METRICS_PIPELINE_HEALTH_AXIS_LABEL: str = "Batches"
    METRICS_PIPELINE_HEALTH_AXIS_LABEL_X: str = "Events per batch"
    METRICS_PIPELINE_HEALTH_LEGEND_FETCH_DESKTOP: str = "fetch · desktop"
    METRICS_PIPELINE_HEALTH_LEGEND_FETCH_MOBILE: str = "fetch · mobile"
    METRICS_PIPELINE_HEALTH_LEGEND_BEACON_DESKTOP: str = "beacon · desktop"
    METRICS_PIPELINE_HEALTH_LEGEND_BEACON_MOBILE: str = "beacon · mobile"
    METRICS_PIPELINE_HEALTH_CHART_DESC: str = (
        "Stacked bar chart of accepted ingest batches grouped by batch size "
        "and split by transport and device type."
    )
    METRICS_PIPELINE_HEALTH_SUPPRESSED_COLUMN: str = f"suppressed (<{MIN_CELL_COUNT})"
    METRICS_PIPELINE_HEALTH_DESC_SUPPRESSED: str = f"{{{{ count }}}} batches in suppressed cells (fewer than {MIN_CELL_COUNT} each)."
    METRICS_FLOW_SUCCEEDED: str = "succeeded"
    METRICS_FLOW_CONVERSION: str = "conversion"
    METRICS_FLOW_DROPOFF: str = "drop-off"
    METRICS_FLOW_CATEGORY_UI: str = "UI"
    METRICS_FLOW_CATEGORY_API: str = "API"
    METRICS_FLOW_CATEGORY_DOMAIN: str = "Domain"
    METRICS_FLOW_EMPTY: str = "No funnel activity recorded in the selected window."
    METRICS_FLOWS_LOADED: str = "Flow funnels updated."
    METRICS_FLOWS_HEADING: str = "Flow funnels"
    METRICS_FLOWS_COUNT: str = "{builtin} built-in · {custom} custom (of {max})"
    METRICS_FLOWS_COUNT_BUILTIN_ONLY: str = "{builtin} built-in"
    METRICS_FLOWS_COUNT_LOADING: str = "Loading flows…"
    METRICS_FLOWS_ZERO_CUSTOM_HINT: str = (
        "No custom flows yet. Custom flows created by admins appear here."
    )
    METRICS_FLOW_BADGE_BUILTIN: str = "Built-in"
    METRICS_FLOW_BADGE_CUSTOM: str = "Custom"
    METRICS_FLOW_CUSTOM_SUFFIX: str = "(custom)"
    METRICS_FLOW_DELETE_LABEL: str = "Delete flow {name}"
    METRICS_FLOW_DELETE_PROMPT: str = "Delete “{name}”? This cannot be undone."
    METRICS_FLOW_DELETE_CONFIRM: str = "Delete"
    METRICS_FLOW_DELETE_CANCEL: str = "Cancel"
    METRICS_FLOW_DELETING: str = "Deleting…"
    METRICS_FLOW_DELETED: str = "Flow “{name}” deleted."
    METRICS_FLOW_ALREADY_DELETED: str = "“{name}” was already deleted by another admin."
    METRICS_FLOW_DELETE_FAILED: str = "Couldn't delete this flow. Try again."
    METRICS_FLOW_RATE_LIMITED: str = "Too many requests. Wait a moment and try again."
    METRICS_FLOW_NEEDS_ATTENTION: str = "Needs attention."
    METRICS_FLOW_NEEDS_ATTENTION_STEP: str = "Step {step}: {reason}"
    METRICS_FLOW_NEEDS_ATTENTION_HELP: str = (
        "This flow can't be counted. Edit the flow to fix it, or delete it."
    )
    METRICS_FLOW_LOADING_LABEL: str = "{title}: loading"
    METRICS_FLOW_LOAD_FAILED: str = "Couldn't load this flow."
    METRICS_FLOW_RETRY: str = "Retry"
    METRICS_FLOWS_LIST_FAILED: str = "Custom flows couldn't be loaded."
    METRICS_FLOWS_LIST_RETRYING: str = "Retrying…"
    METRICS_FLOW_DELETE_LOCKED: str = "Another flow is being deleted."
    METRICS_FLOW_BUILDER_TITLE_NEW: str = "New flow"
    METRICS_FLOW_BUILDER_TITLE_EDIT: str = "Edit flow"
    METRICS_FLOW_BUILDER_NEW_BUTTON: str = "+ New flow"
    METRICS_FLOW_BUILDER_EDIT_LABEL: str = "Edit flow {name}"
    METRICS_FLOW_BUILDER_FIELD_NAME: str = "Display name"
    METRICS_FLOW_BUILDER_STEP_HEADING: str = "Step {step}"
    METRICS_FLOW_BUILDER_STEP_LABEL: str = "Step {step} label"
    METRICS_FLOW_BUILDER_STEP_STREAM: str = "Step {step} stream"
    METRICS_FLOW_BUILDER_STEP_EVENT: str = "Step {step} event"
    METRICS_FLOW_BUILDER_STEP_ENDPOINT: str = "Step {step} endpoint"
    METRICS_FLOW_BUILDER_STEP_METHOD: str = "Step {step} method"
    METRICS_FLOW_BUILDER_MOVE_UP: str = "Move step {step} up"
    METRICS_FLOW_BUILDER_MOVE_DOWN: str = "Move step {step} down"
    METRICS_FLOW_BUILDER_REMOVE_STEP: str = "Remove step {step}"
    METRICS_FLOW_BUILDER_ADD_STEP: str = "+ Add step ({count} of {max})"
    METRICS_FLOW_BUILDER_SAVE: str = "Save flow"
    METRICS_FLOW_BUILDER_SAVING: str = "Saving…"
    METRICS_FLOW_BUILDER_CANCEL: str = "Cancel"
    METRICS_FLOW_BUILDER_DELETE: str = "Delete flow"
    METRICS_FLOW_BUILDER_STREAM_UI: str = "UI"
    METRICS_FLOW_BUILDER_STREAM_API: str = "API"
    METRICS_FLOW_BUILDER_STREAM_DOMAIN: str = "Domain"
    METRICS_FLOW_BUILDER_CHOOSE_EVENT: str = "Choose an event"
    METRICS_FLOW_BUILDER_CHOOSE_ENDPOINT: str = "Choose an endpoint"
    METRICS_FLOW_BUILDER_CHOOSE_METHOD: str = "Choose a method"
    METRICS_FLOW_BUILDER_HINT_FIRST_STEP: str = 'Conversion is measured against Step 1. A browser "open" event as Step 1 can undercount (dropped beacons), which overstates conversion.'
    METRICS_FLOW_BUILDER_HINT_CAP: str = (
        "Limit of {max} custom flows reached. Delete one to add another."
    )
    METRICS_FLOW_BUILDER_HINT_MIN_STEPS: str = "At least {min} steps are required."
    METRICS_FLOW_BUILDER_HINT_MAX_STEPS: str = "At most {max} steps are allowed."
    METRICS_FLOW_BUILDER_HINT_ALREADY_FIRST: str = "Already the first step."
    METRICS_FLOW_BUILDER_HINT_ALREADY_LAST: str = "Already the last step."
    METRICS_FLOW_BUILDER_HINT_REFRESH_PAUSED: str = (
        "Grid refreshes when you leave the builder"
    )
    METRICS_FLOW_BUILDER_NOTE_STALE_VALUE: str = "{value} (no longer exists)"
    METRICS_FLOW_BUILDER_NOTE_FILTERS_CLEARED: str = (
        "Filters and breakdown removed because the event changed."
    )
    METRICS_FLOW_BUILDER_NOTE_KEPT_FILTERS_BREAKDOWN: str = (
        "{count} filters and a breakdown kept. Not editable yet."
    )
    METRICS_FLOW_BUILDER_NOTE_KEPT_FILTERS_BREAKDOWN_ONE: str = (
        "1 filter and a breakdown kept. Not editable yet."
    )
    METRICS_FLOW_BUILDER_NOTE_KEPT_FILTERS: str = (
        "{count} filters kept. Not editable yet."
    )
    METRICS_FLOW_BUILDER_NOTE_KEPT_FILTERS_ONE: str = "1 filter kept. Not editable yet."
    METRICS_FLOW_BUILDER_NOTE_KEPT_BREAKDOWN: str = "Breakdown kept. Not editable yet."
    METRICS_FLOW_BUILDER_NOTE_FILTERS_UNEDITABLE: str = (
        "Filters can't be edited here yet: remove the step or delete the flow."
    )
    METRICS_FLOW_BUILDER_ERR_PROBLEMS: str = "{count} problems to fix"
    METRICS_FLOW_BUILDER_ERR_PROBLEM_ONE: str = "1 problem to fix"
    METRICS_FLOW_BUILDER_ERR_SAVE_FAILED: str = "Couldn't save this flow. Try again."
    METRICS_FLOW_BUILDER_ERR_CATALOG_FAILED: str = (
        "Could not load the event list. Nothing was lost."
    )
    METRICS_FLOW_BUILDER_CATALOG_RETRY: str = "Try again"
    METRICS_FLOW_BUILDER_ERR_FLOW_GONE: str = "This flow no longer exists."
    METRICS_FLOW_BUILDER_CATALOG_LOADING: str = "Loading the event list…"
    METRICS_FLOW_BUILDER_DISCARD_TITLE: str = "Discard changes to “{name}”?"
    METRICS_FLOW_BUILDER_DISCARD_BODY: str = "Your unsaved changes will be lost."
    METRICS_FLOW_BUILDER_DISCARD_CONFIRM: str = "Discard changes"
    METRICS_FLOW_BUILDER_DISCARD_KEEP: str = "Keep editing"
    METRICS_FLOW_BUILDER_DELETE_TITLE: str = "Delete “{name}”?"
    METRICS_FLOW_BUILDER_DELETE_BODY_CLEAN: str = "This cannot be undone."
    METRICS_FLOW_BUILDER_DELETE_BODY: str = (
        "This cannot be undone. Your unsaved changes will also be lost."
    )
    METRICS_FLOW_BUILDER_ANNOUNCE_MOVED: str = (
        "Step moved to position {position} of {total}."
    )
    METRICS_FLOW_BUILDER_ANNOUNCE_REMOVED: str = "Step removed."
    METRICS_FLOW_BUILDER_ANNOUNCE_ADDED: str = "Step added."
    METRICS_FLOW_BUILDER_ANNOUNCE_SAVED: str = "Flow “{name}” saved."
    METRICS_FLOW_BUILDER_ERR_EVENT_REQUIRED: str = metric_flow_strs.EVENT_REQUIRED_STR
    METRICS_FLOW_BUILDER_ERR_ENDPOINT_REQUIRED: str = (
        metric_flow_strs.ENDPOINT_REQUIRED_STR
    )
    METRICS_FLOW_BUILDER_ERR_METHOD_REQUIRED: str = metric_flow_strs.METHOD_REQUIRED_STR
    METRICS_FLOW_BUILDER_ERR_NAME_LENGTH: str = (
        "Enter a name of {min} to {max} characters."
    )
    METRICS_FLOW_BUILDER_ERR_LABEL_LENGTH: str = (
        "Enter a label of {min} to {max} characters."
    )
    METRICS_FLOW_BUILDER_ERR_STEP_LINE: str = "Step {step}: {message}"
    METRICS_GAUGE_KIND_VOLUME: str = "Volume"
    METRICS_GAUGE_KIND_DISTRIBUTION_MAX: str = "Distribution (max)"
    METRICS_GAUGE_KIND_DISTRIBUTION_AVG: str = "Distribution (avg)"
    METRICS_GAUGE_KIND_DISTRIBUTION_MEDIAN: str = "Distribution (median)"
    METRICS_GAUGE_KIND_DISTRIBUTION_P90: str = "Distribution (p90)"
    METRICS_GAUGE_SUPPRESSED_ARIA: str = "Value unavailable"
    METRICS_SUPPRESSED_LABEL: str = f"suppressed (fewer than {MIN_CELL_COUNT})"
    METRICS_PIPELINE_HEALTH_LEGEND_SUPPRESSED: str = METRICS_SUPPRESSED_LABEL
    METRICS_FLOW_COUNT_SUPPRESSED_ARIA: str = (
        f"Count suppressed (fewer than {MIN_CELL_COUNT})"
    )
    METRICS_GAUGES_LOADED: str = "Gauge values updated."
    METRICS_GAUGE_SELECT_PROMPT: str = "Select a gauge to view its timeseries."
    METRICS_GAUGE_COL_NAME: str = "Gauge"
    METRICS_GAUGE_COL_VALUE: str = "Value"
    METRICS_GAUGES_EMPTY: str = "No gauge samples recorded in the selected window."
    METRICS_TAB_LATENCY: str = "Backend Performance"
    METRICS_LATENCY_EMPTY: str = "No latency samples recorded in the selected window."
    METRICS_LATENCY_SELECT_PROMPT: str = "Select an endpoint to view its latency trend"
    METRICS_LATENCY_COL_ENDPOINT: str = "Endpoint"
    METRICS_LATENCY_COL_P50: str = "p50 (ms)"
    METRICS_LATENCY_COL_P95: str = "p95 (ms)"
    METRICS_LATENCY_COL_P99: str = "p99 (ms)"
    METRICS_LATENCY_COL_SAMPLES: str = "Samples"
    METRICS_LATENCY_Y_AXIS_LABEL: str = "Latency (ms)"
    METRICS_LATENCY_ROW_ARIA: str = (
        "{{endpoint}}: p50 {{p50}} ms, p95 {{p95}} ms, p99 {{p99}} ms"
    )
    METRICS_LATENCY_SERIES_ARIA_P50: str = "p50 latency series"
    METRICS_LATENCY_SERIES_ARIA_P95: str = "p95 latency series"
    METRICS_LATENCY_SERIES_ARIA_P99: str = "p99 latency series"
    METRICS_LATENCY_APPROXIMATE_NOTE: str = (
        "Summary percentiles for this window are approximate (daily rollup); "
        "the per-day trend below is exact."
    )
    METRICS_LATENCY_DAILY_RESOLUTION_NOTE: str = (
        "Showing daily trend for this long window; hourly detail is only "
        "available within the last 35 days."
    )
