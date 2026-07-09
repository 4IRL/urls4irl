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
    NAV_USERS: str = "Users"
    NAV_AUDIT_LOG: str = "Audit Log"
    NAV_METRICS: str = "Metrics"
    HEALTH_TITLE: str = "System Health"
    HEALTH_LABEL_DATABASE: str = "Database"
    HEALTH_LABEL_DB_CONNECTIONS: str = "DB Connections"
    HEALTH_LABEL_SESSION_REDIS: str = "Session Redis"
    HEALTH_LABEL_METRICS_REDIS: str = "Metrics Redis"
    HEALTH_LABEL_DISK_USED: str = "Disk Used"
    HEALTH_LABEL_FLUSH_LAST_SUCCESS: str = "Metrics Flush (sidecar)"
    HEALTH_LABEL_GAUGE_LAST_SAMPLE: str = "Gauge Sample (sidecar)"
    HEALTH_VALUE_UNKNOWN: str = "unknown"
    HEALTH_NEVER_RAN: str = "never"


class ADMIN_AUDIT_ACTIONS:
    """Closed set of ``AuditLogs.action`` values emitted by the admin portal."""

    PORTAL_VIEW: str = "admin.portal.view"
    HEALTH_VIEW: str = "admin.health.view"
