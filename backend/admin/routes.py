from __future__ import annotations

from flask import Blueprint, abort, render_template, request
from flask.wrappers import Response as FlaskResponse
from flask_login import current_user

from backend import db
from backend.admin import db_browser_service
from backend.admin.audit_service import (
    AuditLogFilters,
    DEFAULT_AUDIT_PAGE_LIMIT,
    query_audit_log,
)
from backend.admin.health_service import collect_health_snapshot
from backend.admin.account_data_service import is_tombstoned
from backend.admin.user_service import (
    DEFAULT_SEARCH_LIMIT,
    get_user_detail,
    search_users,
)
from backend.api_common.auth_decorators import admin_login_required
from backend.extensions import audit
from backend.utils.constants import provide_config_for_constants
from backend.utils.strings.admin_portal_strs import (
    ADMIN_AUDIT_ACTIONS,
    ADMIN_PORTAL_STRINGS,
)

admin = Blueprint("admin", __name__)


@admin.context_processor
def provide_constants() -> dict:
    return provide_config_for_constants()


@admin.context_processor
def provide_admin_portal_strings() -> dict:
    return {"ADMIN_PORTAL_STRINGS": ADMIN_PORTAL_STRINGS}


@admin.route("/admin", methods=["GET"])
@admin_login_required
def admin_portal() -> FlaskResponse:
    """Server-rendered HTML landing page for the admin portal.

    Nav shell linking every admin sub-surface (health, DB browser, users,
    audit log, metrics). Unauthenticated requests are redirected (302) to
    the login page; authenticated non-admin requests receive a 403 —
    matching the established `/admin/metrics` gating semantics.
    """
    audit.record(actor_id=current_user.id, action=ADMIN_AUDIT_ACTIONS.PORTAL_VIEW)
    db.session.commit()
    return render_template(
        "admin_portal/index.html",
        is_admin_portal=True,
    )


@admin.route("/admin/health", methods=["GET"])
@admin_login_required
def admin_health() -> FlaskResponse:
    """Server-rendered shell for the system-health dashboard.

    The dashboard content itself is loaded (and every 30s reloaded) from
    ``/admin/health/snapshot`` by the client-side health-monitor controller;
    this route only renders the shell and audits the page view.
    """
    audit.record(actor_id=current_user.id, action=ADMIN_AUDIT_ACTIONS.HEALTH_VIEW)
    db.session.commit()
    return render_template(
        "admin_portal/health.html",
        is_admin_portal=True,
    )


@admin.route("/admin/health/snapshot", methods=["GET"])
@admin_login_required
def admin_health_snapshot() -> FlaskResponse:
    """HTML fragment with the current health snapshot.

    Deliberately NOT audited: the fragment is polled every 30 seconds and
    per-poll audit rows would flood the audit log; the page view itself is
    audited by ``admin_health``.
    """
    health_snapshot = collect_health_snapshot()
    return render_template(
        "admin_portal/_health_snapshot.html",
        snapshot=health_snapshot,
    )


@admin.route("/admin/users", methods=["GET"])
@admin_login_required
def admin_users() -> FlaskResponse:
    """Server-rendered shell for the admin user-search page.

    The results table is loaded (on init, and 500ms-debounced on typing)
    from ``/admin/users/search`` by the client-side user-search controller.
    Not audited itself — the initial fragment request records the blank search.
    """
    return render_template(
        "admin_portal/users/index.html",
        is_admin_portal=True,
    )


@admin.route("/admin/users/search", methods=["GET"])
@admin_login_required
def admin_users_search() -> FlaskResponse:
    """HTML fragment of user-search result rows.

    Every execution is audited with the query and result count — search
    strings land in AuditLogs.metadata and age out with the 90-day
    retention purge.
    """
    search_query: str = request.args.get("q", "")
    result_offset = _parse_offset_arg()
    search_page = search_users(
        query=search_query,
        limit=DEFAULT_SEARCH_LIMIT,
        offset=result_offset,
    )
    audit.record(
        actor_id=current_user.id,
        action=ADMIN_AUDIT_ACTIONS.USER_SEARCH,
        metadata={
            "query": search_page.query,
            "result_count": search_page.total_count,
        },
    )
    db.session.commit()
    return render_template(
        "admin_portal/users/_results.html",
        search_page=search_page,
    )


@admin.route("/admin/users/<int:user_id>", methods=["GET"])
@admin_login_required
def admin_user_detail(user_id: int) -> FlaskResponse:
    """Detail page for one user: metadata, role, email-validated status,
    OAuth identities, and UTub memberships, plus the account-action and
    moderation controls (each mutation POSTs to its own audited endpoint —
    rendering this page itself mutates nothing)."""
    detail_user = get_user_detail(user_id=user_id)
    if detail_user is None:
        abort(404)
    audit.record(
        actor_id=current_user.id,
        action=ADMIN_AUDIT_ACTIONS.USER_VIEW,
        target_type="User",
        target_id=str(user_id),
    )
    db.session.commit()
    return render_template(
        "admin_portal/users/detail.html",
        is_admin_portal=True,
        detail_user=detail_user,
        is_erased=is_tombstoned(user=detail_user),
    )


@admin.route("/admin/db", methods=["GET"])
@admin_login_required
def admin_db() -> FlaskResponse:
    """Read-only DB-browser overview: every table and its live row count.

    Native replacement for the removed Flask-Admin model list. Each table
    links to its paginated grid. The page view is audited.
    """
    audit.record(actor_id=current_user.id, action=ADMIN_AUDIT_ACTIONS.DB_BROWSER_VIEW)
    db.session.commit()
    return render_template(
        "admin_portal/db/index.html",
        is_admin_portal=True,
        tables=db_browser_service.list_tables(),
    )


@admin.route("/admin/db/<table_name>", methods=["GET"])
@admin_login_required
def admin_db_table(table_name: str) -> FlaskResponse:
    """One paginated grid page of ``table_name`` (50 rows/page).

    Optional query params ``sort`` (column key), ``dir`` ("asc"/"desc"), and
    ``q`` (substring search) shape the ordering and filtering. Unknown tables
    404 (and are not audited). Sensitive columns are excluded by the service;
    every cell is HTML-escaped by Jinja autoescape.
    """
    table_page = db_browser_service.get_table_page(
        table_name=table_name,
        offset=_parse_offset_arg(),
        sort_key=request.args.get("sort"),
        direction=request.args.get("dir", "asc"),
        query=request.args.get("q", ""),
    )
    if table_page is None:
        abort(404)
    audit.record(
        actor_id=current_user.id,
        action=ADMIN_AUDIT_ACTIONS.DB_BROWSER_VIEW,
        target_type=table_name,
    )
    db.session.commit()
    return render_template(
        "admin_portal/db/table.html",
        is_admin_portal=True,
        table_page=table_page,
    )


@admin.route("/admin/db/<table_name>/<path:row_pk>", methods=["GET"])
@admin_login_required
def admin_db_row(table_name: str, row_pk: str) -> FlaskResponse:
    """Row-detail view: the full, untruncated field list for one row.

    Unknown tables, unparseable PKs, and missing rows 404 (and are not
    audited). Sensitive columns are excluded by the service.
    """
    row_detail = db_browser_service.get_row_detail(table_name=table_name, raw_pk=row_pk)
    if row_detail is None:
        abort(404)
    audit.record(
        actor_id=current_user.id,
        action=ADMIN_AUDIT_ACTIONS.DB_BROWSER_VIEW,
        target_type=table_name,
        target_id=row_pk,
    )
    db.session.commit()
    return render_template(
        "admin_portal/db/row.html",
        is_admin_portal=True,
        row_detail=row_detail,
    )


def _parse_offset_arg() -> int:
    try:
        return max(int(request.args.get("offset", "0")), 0)
    except ValueError:
        return 0


def _audit_filters_from_request() -> AuditLogFilters:
    return AuditLogFilters(
        actor=request.args.get("actor", ""),
        action=request.args.get("action", ""),
        target_type=request.args.get("target_type", ""),
        since=request.args.get("since", ""),
        until=request.args.get("until", ""),
    )


@admin.route("/admin/audit-log", methods=["GET"])
@admin_login_required
def admin_audit_log() -> FlaskResponse:
    """Server-rendered shell for the audit-log viewer.

    The rows table loads (and reloads on filter changes) from
    ``/admin/audit-log/rows`` by the client-side audit-log controller.
    The page view itself is audited — yes, viewing the audit log is itself
    an audited action.
    """
    audit.record(actor_id=current_user.id, action=ADMIN_AUDIT_ACTIONS.AUDIT_LOG_VIEW)
    db.session.commit()
    return render_template(
        "admin_portal/audit_log/index.html",
        is_admin_portal=True,
    )


@admin.route("/admin/audit-log/rows", methods=["GET"])
@admin_login_required
def admin_audit_log_rows() -> FlaskResponse:
    """HTML fragment of filtered audit-log rows.

    Not audited per-reload: the audited resource here IS the audit log,
    and the page view already records ``admin.audit_log.view`` — per-filter
    rows would only add self-referential noise.
    """
    audit_page = query_audit_log(
        filters=_audit_filters_from_request(),
        limit=DEFAULT_AUDIT_PAGE_LIMIT,
        offset=_parse_offset_arg(),
    )
    return render_template(
        "admin_portal/audit_log/_rows.html",
        audit_page=audit_page,
    )


@admin.route("/admin/metrics", methods=["GET"])
@admin_login_required
def admin_metrics() -> FlaskResponse:
    """Server-rendered HTML shell for the admin metrics dashboard.

    Server-rendered HTML page; not consumed as a JSON API. Although the
    `admin_login_required` decorator is in `ADMIN_AUTH_DECORATORS` (so the
    generated OpenAPI spec lists this route under admin security), the
    response is HTML — data fetching is entirely client-side via
    `/api/metrics/query/*`.

    Unauthenticated requests are redirected (302) to the login page;
    authenticated non-admin requests receive a 403.
    """
    return render_template(
        "pages/admin_metrics.html",
        is_admin_metrics=True,
    )
