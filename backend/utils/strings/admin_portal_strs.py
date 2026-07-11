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
    OPS_BACKUP_TRIGGER_LABEL: str = "Trigger Backup"
    OPS_BACKUP_TRIGGER_CONFIRM_TITLE: str = "Trigger Backup?"
    OPS_BACKUP_TRIGGER_CONFIRM_BODY: str = (
        "Request an on-demand run of the full backup pipeline. "
        "The workflow container polls for the request every minute "
        "and runs the same pipeline as the nightly 1 AM backup."
    )
    OPS_BACKUP_TRIGGER_SUBMIT: str = "Trigger"
    HEALTH_LABEL_BACKUP_LAST_SUCCESS: str = "Daily Backup (sidecar)"
    # Moderation section — user-detail and DB-row action buttons (Jinja-only; not bridged to JS)
    MOD_SECTION_TITLE: str = "Moderation"
    MOD_LOCKED_BADGE: str = "locked"
    MOD_UTUB_LOCK_LABEL: str = "Lock UTub"
    MOD_UTUB_LOCK_CONFIRM_TITLE: str = "Lock UTub?"
    MOD_UTUB_LOCK_CONFIRM_BODY: str = (
        "Prevent new URLs, tags, and members from being added to this UTub. "
        "Existing content is preserved. The action can be reversed with Unlock."
    )
    MOD_UTUB_LOCK_SUBMIT: str = "Lock"
    MOD_UTUB_UNLOCK_LABEL: str = "Unlock UTub"
    MOD_UTUB_UNLOCK_CONFIRM_TITLE: str = "Unlock UTub?"
    MOD_UTUB_UNLOCK_CONFIRM_BODY: str = (
        "Re-enable content writes for this UTub. "
        "Members will be able to add URLs, tags, and new members again."
    )
    MOD_UTUB_UNLOCK_SUBMIT: str = "Unlock"
    MOD_UTUB_DELETE_LABEL: str = "Delete UTub"
    MOD_UTUB_DELETE_CONFIRM_TITLE: str = "Delete UTub?"
    MOD_UTUB_DELETE_CONFIRM_BODY: str = (
        "Permanently delete this UTub and all its members, URLs, and tags. "
        "This action cannot be undone."
    )
    MOD_UTUB_DELETE_SUBMIT: str = "Delete"
    MOD_MEMBER_REMOVE_LABEL: str = "Remove Member"
    MOD_MEMBER_REMOVE_CONFIRM_TITLE: str = "Remove Member?"
    MOD_MEMBER_REMOVE_CONFIRM_BODY: str = (
        "Remove this user from the UTub. If the user is the creator and other "
        "members exist, ownership transfers to the next eligible member. "
        "If the user is the sole member, the UTub will be deleted."
    )
    MOD_MEMBER_REMOVE_SUBMIT: str = "Remove"
    MOD_URL_DELETE_LABEL: str = "Remove from UTub"
    MOD_URL_DELETE_CONFIRM_TITLE: str = "Remove URL from UTub?"
    MOD_URL_DELETE_CONFIRM_BODY: str = (
        "Remove this URL association from its UTub. "
        "The canonical URL record is preserved and the URL may still appear in other UTubs."
    )
    MOD_URL_DELETE_SUBMIT: str = "Remove"
    MOD_URL_PURGE_LABEL: str = "Purge from all UTubs"
    MOD_URL_PURGE_CONFIRM_TITLE: str = "Purge URL from all UTubs?"
    MOD_URL_PURGE_CONFIRM_BODY: str = (
        "Remove this URL from every UTub that contains it. "
        "The canonical URL record is preserved, but all UTub associations and their tags are deleted. "
        "This action cannot be undone."
    )
    MOD_URL_PURGE_SUBMIT: str = "Purge"
    # Account lifecycle section — user-detail action buttons (Jinja-only; not bridged to JS)
    ACCOUNT_SECTION_TITLE: str = "Account Actions"
    ACCOUNT_SELF_ACTIONS_NA: str = (
        "Account actions are not available for your own account."
    )
    ACCOUNT_SUSPEND_LABEL: str = "Suspend"
    ACCOUNT_SUSPEND_CONFIRM_TITLE: str = "Suspend Account?"
    ACCOUNT_SUSPEND_CONFIRM_BODY: str = (
        "Suspend this user account. This blocks the user from logging in and "
        "immediately kills all active sessions and revokes all API tokens. "
        "The account can be restored with Unsuspend."
    )
    ACCOUNT_SUSPEND_SUBMIT: str = "Suspend"
    ACCOUNT_UNSUSPEND_LABEL: str = "Unsuspend"
    ACCOUNT_UNSUSPEND_CONFIRM_TITLE: str = "Unsuspend Account?"
    ACCOUNT_UNSUSPEND_CONFIRM_BODY: str = (
        "Lift the suspension on this user account, restoring their ability to "
        "log in. Existing sessions remain killed — the user will need to log in again."
    )
    ACCOUNT_UNSUSPEND_SUBMIT: str = "Unsuspend"
    ACCOUNT_KILL_SESSIONS_LABEL: str = "Kill Sessions"
    ACCOUNT_KILL_SESSIONS_CONFIRM_TITLE: str = "Kill Sessions?"
    ACCOUNT_KILL_SESSIONS_CONFIRM_BODY: str = (
        "Immediately invalidate all active web sessions and revoke all API "
        "refresh tokens for this user. The user will be logged out everywhere "
        "they are currently signed in."
    )
    ACCOUNT_KILL_SESSIONS_SUBMIT: str = "Kill Sessions"
    ACCOUNT_FORCE_RESET_LABEL: str = "Force Password Reset"
    ACCOUNT_FORCE_RESET_CONFIRM_TITLE: str = "Force Password Reset?"
    ACCOUNT_FORCE_RESET_CONFIRM_BODY: str = (
        "Send a password-reset email to this user and immediately log them out "
        "everywhere. All active web sessions are killed and all API tokens are "
        "revoked. This bypasses rate limits."
    )
    ACCOUNT_FORCE_RESET_SUBMIT: str = "Force Reset"
    ACCOUNT_FORCE_RESET_NA: str = "OAuth-only account — no local password to reset."
    # Account data actions — erase, email-verify, email-resend (Jinja-only; not bridged to JS)
    ACCOUNT_ERASE_LABEL: str = "Erase Account"
    ACCOUNT_ERASE_CONFIRM_TITLE: str = "Erase Account?"
    ACCOUNT_ERASE_CONFIRM_BODY: str = (
        "PII is scrubbed immediately from the live database: username, email, and "
        "password are replaced with anonymized tombstone values. "
        "The action cannot be undone. "
        "Audit rows and backups retain the original data for up to 90 days until they age out."
    )
    ACCOUNT_ERASE_SUBMIT: str = "Erase"
    ACCOUNT_ERASED_NA: str = "Account already erased."
    ACCOUNT_EMAIL_VERIFY_LABEL: str = "Mark Email Verified"
    ACCOUNT_EMAIL_VERIFY_CONFIRM_TITLE: str = "Mark Email Verified?"
    ACCOUNT_EMAIL_VERIFY_CONFIRM_BODY: str = (
        "Mark this user's email address as verified and delete any pending "
        "email-validation row. Idempotent: already-verified users are unaffected."
    )
    ACCOUNT_EMAIL_VERIFY_SUBMIT: str = "Verify"
    ACCOUNT_EMAIL_VERIFIED_NA: str = "Email already verified."
    ACCOUNT_EMAIL_RESEND_LABEL: str = "Resend Verification Email"
    ACCOUNT_EMAIL_RESEND_CONFIRM_TITLE: str = "Resend Verification Email?"
    ACCOUNT_EMAIL_RESEND_CONFIRM_BODY: str = (
        "Resend the email-verification link for this user, bypassing rate limits. "
        "Creates or resets the pending validation row with a fresh token."
    )
    ACCOUNT_EMAIL_RESEND_SUBMIT: str = "Resend"
    # OAuth identities panel (Jinja-only; not bridged to JS)
    ACCOUNT_OAUTH_SECTION_TITLE: str = "OAuth Identities"
    ACCOUNT_OAUTH_NONE: str = "No OAuth identities linked."
    ACCOUNT_UNLINK_LABEL: str = "Unlink"
    ACCOUNT_UNLINK_CONFIRM_TITLE: str = "Unlink OAuth Identity?"
    ACCOUNT_UNLINK_CONFIRM_BODY: str = (
        "Remove this OAuth identity from the account. "
        "The user will no longer be able to sign in with this provider. "
        "Cannot unlink the last login method."
    )
    ACCOUNT_UNLINK_SUBMIT: str = "Unlink"
    ACCOUNT_UNLINK_NA: str = "Last login method — cannot unlink."


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
    OPS_BACKUP_TRIGGER_SUCCESS: str = (
        "Backup requested. The workflow container will start it within one minute."
    )
    OPS_BACKUP_TRIGGER_ALREADY_PENDING: str = (
        "A backup request is already pending. No new request was made."
    )
    OPS_BACKUP_TRIGGER_UNAVAILABLE: str = "Metrics Redis is not configured."
    OPS_BACKUP_TRIGGER_ERROR: str = "Backup trigger failed. Check the server logs."
    # Moderation action backend response messages (not bridged to JS)
    MOD_TARGET_NOT_FOUND: str = "Target not found."
    MOD_UTUB_LOCK_SUCCESS: str = "UTub locked successfully."
    MOD_UTUB_LOCK_NOOP: str = "UTub is already locked. No change made."
    MOD_UTUB_UNLOCK_SUCCESS: str = "UTub unlocked successfully."
    MOD_UTUB_UNLOCK_NOOP: str = "UTub is already unlocked. No change made."
    MOD_UTUB_DELETE_SUCCESS: str = "UTub deleted successfully."
    MOD_MEMBER_REMOVE_SUCCESS: str = "Member removed successfully."
    MOD_MEMBER_REMOVE_TRANSFERRED: str = (
        "Member removed. UTub ownership transferred to user {user_id}."
    )
    MOD_MEMBER_REMOVE_UTUB_DELETED: str = (
        "Member removed. UTub deleted (sole member was creator)."
    )
    MOD_URL_DELETE_SUCCESS: str = "URL removed from UTub successfully."
    MOD_URL_PURGE_SUCCESS: str = "URL purged from {count} UTub(s)."
    # Account lifecycle action backend response messages (not bridged to JS)
    LAST_ADMIN_FORBIDDEN: str = (
        "Cannot perform this action: no other active admin exists."
    )
    ACCOUNT_SUSPEND_SUCCESS: str = "User suspended successfully."
    ACCOUNT_SUSPEND_NOOP: str = "User is already suspended. No change made."
    ACCOUNT_UNSUSPEND_SUCCESS: str = "User unsuspended successfully."
    ACCOUNT_UNSUSPEND_NOOP: str = "User is not suspended. No change made."
    ACCOUNT_KILL_SESSIONS_SUCCESS: str = (
        "Sessions killed. {count} API token(s) revoked."
    )
    ACCOUNT_FORCE_RESET_SUCCESS: str = "Password reset email sent and sessions killed."
    ACCOUNT_FORCE_RESET_OAUTH_ONLY: str = (
        "This account uses OAuth only and has no password to reset."
    )
    ACCOUNT_FORCE_RESET_EMAIL_FAILURE: str = (
        "Password reset email failed to send. No changes were committed."
    )
    # Account data action backend response messages (not bridged to JS)
    ACCOUNT_ERASE_SUCCESS: str = (
        "User erased. PII scrubbed, sessions killed, memberships resolved."
    )
    ACCOUNT_ERASE_NOOP: str = "User is already erased. No change made."
    ACCOUNT_UNLINK_SUCCESS: str = "OAuth identity ({provider}) unlinked."
    ACCOUNT_UNLINK_LAST_CREDENTIAL: str = (
        "Cannot unlink: this is the account's only login method."
    )
    ACCOUNT_EMAIL_VERIFY_SUCCESS: str = "Email marked as verified."
    ACCOUNT_EMAIL_VERIFY_NOOP: str = "Email is already verified. No change made."
    ACCOUNT_EMAIL_RESEND_SUCCESS: str = "Verification email sent."
    ACCOUNT_EMAIL_RESEND_ALREADY_VERIFIED: str = (
        "Email is already verified. No email sent."
    )
    ACCOUNT_EMAIL_RESEND_FAILURE: str = (
        "Verification email failed to send. No changes were committed."
    )
    ACCOUNT_TARGET_ERASED: str = (
        "This account has been erased. Email actions are not available."
    )


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
    OPS_BACKUP_TRIGGER: str = "admin.ops.backup_trigger"
    # Content moderation actions
    UTUB_LOCK: str = "admin.utub.lock"
    UTUB_UNLOCK: str = "admin.utub.unlock"
    UTUB_DELETE: str = "admin.utub.delete"
    MEMBER_REMOVE: str = "admin.member.remove"
    URL_DELETE: str = "admin.url.delete"
    URL_PURGE: str = "admin.url.purge"
    # Account lifecycle actions
    USER_SUSPEND: str = "admin.user.suspend"
    USER_UNSUSPEND: str = "admin.user.unsuspend"
    USER_FORCE_RESET: str = "admin.user.force_reset"
    USER_KILL_SESSIONS: str = "admin.user.kill_sessions"
    # Account data actions
    USER_ERASE: str = "admin.user.erase"
    OAUTH_UNLINK: str = "admin.user.oauth_unlink"
    EMAIL_VERIFY: str = "admin.user.email_verify"
    EMAIL_RESEND: str = "admin.user.email_resend"
