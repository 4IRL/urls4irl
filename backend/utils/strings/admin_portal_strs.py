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


class ADMIN_AUDIT_ACTIONS:
    """Closed set of ``AuditLogs.action`` values emitted by the admin portal."""

    PORTAL_VIEW: str = "admin.portal.view"
