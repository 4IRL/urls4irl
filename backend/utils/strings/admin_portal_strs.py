class ADMIN_PORTAL_STRINGS:
    """Strings rendered by the admin-portal Jinja templates.

    Deliberately NOT bridged into ``generate_strings_js()`` /
    ``APP_CONFIG.strings`` — no TypeScript reads them. They are exposed to
    templates via the admin blueprint's context processor and referenced by
    ``ui_testing_strs.py`` so Python UI tests never duplicate the literals.
    """

    PORTAL_TITLE: str = "Admin Portal"
    PORTAL_SUBTITLE: str = "Operations console for URLS4IRL"
    NAV_DASHBOARD: str = "Dashboard"
    NAV_HEALTH: str = "System Health"
    NAV_DB_BROWSER: str = "DB Browser"
    DB_BROWSER_TITLE: str = "Database Browser"
    DB_BROWSER_SUBTITLE: str = (
        "Read-only view of every table. Select a table to browse its rows."
    )
    DB_EMPTY_TABLE: str = "This table has no rows."
    DB_NO_SEARCH_RESULTS: str = "No rows match this search."
    DB_SEARCH_PLACEHOLDER: str = "Search this table…"
    DB_ROW_COUNT_SINGULAR: str = "row"
    DB_ROW_COUNT_PLURAL: str = "rows"
    NAV_USERS: str = "Users"
    NAV_AUDIT_LOG: str = "Audit Log"
    NAV_METRICS: str = "Metrics"
    HEALTH_TITLE: str = "System Health"
    HEALTH_LABEL_DATABASE: str = "Database"
    HEALTH_LABEL_DB_CONNECTIONS: str = "DB Connections"
    HEALTH_LABEL_SESSION_REDIS: str = "Session Redis"
    HEALTH_LABEL_METRICS_REDIS: str = "Metrics Redis"
    HEALTH_LABEL_FLUSH_LAST_SUCCESS: str = "Metrics Flush (sidecar)"
    HEALTH_LABEL_GAUGE_LAST_SAMPLE: str = "Gauge Sample (sidecar)"
    HEALTH_VALUE_UNKNOWN: str = "unknown"
    HEALTH_VALUE_UNAVAILABLE: str = "unavailable"
    HEALTH_NEVER_RAN: str = "never"
    USERS_TITLE: str = "Users"
    USERS_SEARCH_PLACEHOLDER: str = "Search by username or email…"
    USERS_SEARCH_ARIA: str = "Search users by username or email"
    USERS_NO_RESULTS: str = "No users match this search."
    USER_DETAIL_TITLE: str = "User Detail"
    USER_DETAIL_MEMBERSHIPS_HEADING: str = "UTub Memberships"
    USER_DETAIL_NO_MEMBERSHIPS: str = "Not a member of any UTubs."
    AUDIT_LOG_TITLE: str = "Audit Log"
    AUDIT_LOG_NO_RESULTS: str = "No audit entries match these filters."
    AUDIT_LOG_FILTER_ACTOR: str = "Actor (username or email)"
    AUDIT_LOG_FILTER_ACTION: str = "Action contains"
    AUDIT_LOG_FILTER_TARGET_TYPE: str = "Target type"
    AUDIT_LOG_FILTER_SINCE: str = "Since"
    AUDIT_LOG_FILTER_UNTIL: str = "Until"
    AUDIT_LOG_METADATA_SUMMARY: str = "metadata"
    # Ops section — health page operational action buttons (Jinja-only; not bridged to JS)
    OPS_SECTION_TITLE: str = "Operations"
    OPS_METRICS_FLUSH_LABEL: str = "Flush Metrics"
    OPS_METRICS_FLUSH_CONFIRM_TITLE: str = "Flush Metrics?"
    OPS_METRICS_FLUSH_CONFIRM_BODY: str = (
        "Trigger an immediate Redis-to-Postgres metrics flush. "
        "This runs the same flush the cron worker runs every minute. "
        "Returns 0 rows when the flush lock is held by the cron worker."
    )
    OPS_METRICS_FLUSH_SUBMIT: str = "Flush"
    OPS_GAUGE_SAMPLE_LABEL: str = "Sample Gauges"
    OPS_GAUGE_SAMPLE_CONFIRM_TITLE: str = "Sample Gauges?"
    OPS_GAUGE_SAMPLE_CONFIRM_BODY: str = (
        "Trigger an immediate gauge sample run. "
        "This samples all registered gauges and writes the current values to the database."
    )
    OPS_GAUGE_SAMPLE_SUBMIT: str = "Sample"
    OPS_AUDIT_PURGE_LABEL: str = "Purge Audit Log"
    OPS_AUDIT_PURGE_CONFIRM_TITLE: str = "Purge Audit Log?"
    OPS_AUDIT_PURGE_CONFIRM_BODY: str = (
        "Delete audit log entries older than 90 days (window-only purge). "
        "This runs the same retention purge as the daily cron job. "
        "The purge trigger is always recorded in the audit log first."
    )
    OPS_AUDIT_PURGE_SUBMIT: str = "Purge"
    OPS_VERIFY_TABLES_LABEL: str = "Verify Tables"
    OPS_VERIFY_TABLES_CONFIRM_TITLE: str = "Verify Tables?"
    OPS_VERIFY_TABLES_CONFIRM_BODY: str = (
        "Check for missing database tables (read-only). "
        "No schema changes or repairs will be made."
    )
    OPS_VERIFY_TABLES_SUBMIT: str = "Verify"
    OPS_SHORT_URLS_SYNC_LABEL: str = "Sync Short URLs"
    OPS_SHORT_URLS_SYNC_CONFIRM_TITLE: str = "Sync Short URL Domains?"
    OPS_SHORT_URLS_SYNC_CONFIRM_BODY: str = (
        "Regenerate the short-URL domain Redis set from the canonical GitHub list. "
        "This re-fetches and re-adds all short-URL domains."
    )
    OPS_SHORT_URLS_SYNC_SUBMIT: str = "Sync"


class ADMIN_ACTION_STRINGS:
    """Strings for the admin mutation-action surface.

    ``REASON_LABEL``, ``REASON_REQUIRED``, ``GENERIC_ERROR``,
    ``SUBMIT_DEFAULT``, ``DISMISS``, and ``SUCCESS_DEFAULT`` ARE bridged into
    ``generate_strings_js()`` / ``APP_CONFIG.strings`` — the shared
    admin-actions TypeScript controller renders them into the confirm modal.
    The remaining members are backend-only JSON response messages, surfaced
    verbatim from the response envelope.
    """

    REASON_LABEL: str = "Reason"
    REASON_REQUIRED: str = "A reason is required for this action."
    GENERIC_ERROR: str = "Action failed. Check the server logs."
    SUBMIT_DEFAULT: str = "Confirm"
    DISMISS: str = "Cancel"
    SUCCESS_DEFAULT: str = "Action completed."
    SELF_ACTION_FORBIDDEN: str = (
        "Admins cannot perform this action on their own account."
    )
    # Ops-action backend response messages (not bridged to JS)
    OPS_FLUSH_SUCCESS: str = "Metrics flush complete: {count} row(s) flushed."
    OPS_FLUSH_UNAVAILABLE: str = "Metrics Redis is not configured."
    OPS_FLUSH_ERROR: str = "Metrics flush failed. Check the server logs."
    OPS_GAUGE_SUCCESS: str = "Gauge sample complete: {count} gauge(s) sampled."
    OPS_GAUGE_UNAVAILABLE: str = "Metrics Redis is not configured."
    OPS_GAUGE_ERROR: str = "Gauge sample failed. Check the server logs."
    OPS_PURGE_SUCCESS: str = "Audit log purged: {count} row(s) deleted."
    OPS_PURGE_ERROR: str = "Audit log purge failed. Check the server logs."
    OPS_VERIFY_OK: str = "All tables present."
    OPS_VERIFY_MISSING: str = "Missing tables: {tables}"
    OPS_VERIFY_ERROR: str = "Table verification failed. Check the server logs."
    OPS_SHORT_URLS_SYNC_SUCCESS: str = (
        "Short URL sync complete: {count} new domain(s) added."
    )
    OPS_SHORT_URLS_SYNC_UNAVAILABLE: str = "Redis is not configured."
    OPS_SHORT_URLS_SYNC_ERROR: str = "Short URL sync failed. Check the server logs."


class ADMIN_AUDIT_ACTIONS:
    """Closed set of ``AuditLogs.action`` values emitted by the admin portal."""

    PORTAL_VIEW: str = "admin.portal.view"
    HEALTH_VIEW: str = "admin.health.view"
    DB_BROWSER_VIEW: str = "admin.db_browser.view"
    USER_SEARCH: str = "admin.user.search"
    USER_VIEW: str = "admin.user.view"
    AUDIT_LOG_VIEW: str = "admin.audit_log.view"
    # Ops actions
    OPS_METRICS_FLUSH: str = "admin.ops.metrics_flush"
    OPS_GAUGE_SAMPLE: str = "admin.ops.gauge_sample"
    OPS_AUDIT_PURGE: str = "admin.ops.audit_purge"
    OPS_VERIFY_TABLES: str = "admin.ops.verify_tables"
    OPS_SHORT_URLS_SYNC: str = "admin.ops.short_urls_sync"
