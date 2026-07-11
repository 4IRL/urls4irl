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


class ADMIN_ACTION_STRINGS:
    """Strings for the admin mutation-action surface.

    ``REASON_LABEL``, ``REASON_REQUIRED``, ``GENERIC_ERROR``,
    ``SUBMIT_DEFAULT``, and ``DISMISS`` ARE bridged into
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
    SELF_ACTION_FORBIDDEN: str = (
        "Admins cannot perform this action on their own account."
    )


class ADMIN_AUDIT_ACTIONS:
    """Closed set of ``AuditLogs.action`` values emitted by the admin portal."""

    PORTAL_VIEW: str = "admin.portal.view"
    HEALTH_VIEW: str = "admin.health.view"
    DB_BROWSER_VIEW: str = "admin.db_browser.view"
    USER_SEARCH: str = "admin.user.search"
    USER_VIEW: str = "admin.user.view"
    AUDIT_LOG_VIEW: str = "admin.audit_log.view"
