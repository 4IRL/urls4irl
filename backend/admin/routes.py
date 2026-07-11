from __future__ import annotations

from dataclasses import dataclass

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
from backend.models.users import Users
from backend.models.utub_members import Utub_Members
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.utils.constants import provide_config_for_constants
from backend.utils.strings.admin_portal_strs import (
    ADMIN_AUDIT_ACTIONS,
    ADMIN_PORTAL_STRINGS,
)

_DETAIL_TABLE_PAGE_SIZE: int = 50

admin = Blueprint("admin", __name__)


@dataclass(frozen=True)
class _DetailTablePage:
    """One page of a UTub-detail relationship table (members or URLs).

    Holds the sliced page rows plus the offset/limit/total needed to render
    the "showing X-Y of N" span and Previous/Next links, mirroring the
    ``TablePage`` pagination math used by the UTub list page.
    """

    rows: list[Utub_Members] | list[Utub_Urls]
    total_count: int
    offset: int
    limit: int

    @property
    def has_previous(self) -> bool:
        return self.offset > 0

    @property
    def has_next(self) -> bool:
        return self.offset + self.limit < self.total_count

    @property
    def previous_offset(self) -> int:
        return max(self.offset - self.limit, 0)

    @property
    def next_offset(self) -> int:
        return self.offset + self.limit

    @property
    def showing_start(self) -> int:
        return self.offset + 1 if self.total_count else 0

    @property
    def showing_end(self) -> int:
        return min(self.offset + self.limit, self.total_count)


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


@admin.route("/admin/system-operations", methods=["GET"])
@admin_login_required
def admin_system_operations() -> FlaskResponse:
    """Server-rendered page hosting the six global operations cards.

    Each card POSTs to its own audited ops endpoint (metrics flush, gauge
    sample, audit purge, verify tables, backup trigger, short-urls sync);
    rendering this page mutates nothing and only records the page view.
    """
    audit.record(actor_id=current_user.id, action=ADMIN_AUDIT_ACTIONS.SYSTEM_OPS_VIEW)
    db.session.commit()
    return render_template(
        "admin_portal/system_operations/index.html",
        is_admin_portal=True,
    )


@admin.route("/admin/utubs", methods=["GET"])
@admin_login_required
def admin_utubs() -> FlaskResponse:
    """Searchable, sortable, paginated list of UTubs for the UTub Actions tab.

    Reuses the DB browser's generic table service (``get_table_page`` over the
    ``Utubs`` table) rather than a bespoke search endpoint, so the grid mirrors
    the DB browser's raw-column rendering. Query params ``q``/``sort``/``dir``/
    ``offset`` shape the search, ordering, and pagination exactly as
    ``admin_db_table``. Each row links to the per-UTub detail page. The page
    view is audited with the query and result count.
    """
    search_query: str = request.args.get("q", "")
    table_page = db_browser_service.get_table_page(
        table_name="Utubs",
        offset=_parse_offset_arg(),
        sort_key=request.args.get("sort"),
        direction=request.args.get("dir", "asc"),
        query=search_query,
    )
    audit.record(
        actor_id=current_user.id,
        action=ADMIN_AUDIT_ACTIONS.UTUB_LIST,
        metadata={
            "query": table_page.query,
            "result_count": table_page.total_count,
        },
    )
    db.session.commit()
    return render_template(
        "admin_portal/utubs/index.html",
        is_admin_portal=True,
        table_page=table_page,
    )


@admin.route("/admin/utubs/<int:utub_id>", methods=["GET"])
@admin_login_required
def admin_utub_detail(utub_id: int) -> FlaskResponse:
    """Aggregated detail page for one UTub: info panel, members, and URLs.

    Renders the UTub's own relationships (``members`` and ``utub_urls``) so the
    lock/unlock, delete, remove-member, remove-URL, and purge-URL moderation
    controls source their ids directly from the loaded UTub. The creator's
    username is resolved from ``utub_creator``. Missing UTubs 404. The page view
    is audited; each mutation POSTs to its own audited endpoint — rendering this
    page mutates nothing.
    """
    detail_utub = Utubs.query.get(utub_id)
    if detail_utub is None:
        abort(404)
    creator_username: str | None = None
    creator = Users.query.get(detail_utub.utub_creator)
    if creator is not None:
        creator_username = creator.username

    members_offset = _parse_offset_arg("members_offset")
    urls_offset = _parse_offset_arg("urls_offset")
    members_total = Utub_Members.query.filter_by(utub_id=detail_utub.id).count()
    members_rows = (
        Utub_Members.query.filter_by(utub_id=detail_utub.id)
        .order_by(Utub_Members.user_id)
        .limit(_DETAIL_TABLE_PAGE_SIZE)
        .offset(members_offset)
        .all()
    )
    urls_total = Utub_Urls.query.filter_by(utub_id=detail_utub.id).count()
    urls_rows = (
        Utub_Urls.query.filter_by(utub_id=detail_utub.id)
        .order_by(Utub_Urls.id)
        .limit(_DETAIL_TABLE_PAGE_SIZE)
        .offset(urls_offset)
        .all()
    )
    members_page = _DetailTablePage(
        rows=members_rows,
        total_count=members_total,
        offset=members_offset,
        limit=_DETAIL_TABLE_PAGE_SIZE,
    )
    urls_page = _DetailTablePage(
        rows=urls_rows,
        total_count=urls_total,
        offset=urls_offset,
        limit=_DETAIL_TABLE_PAGE_SIZE,
    )

    audit.record(
        actor_id=current_user.id,
        action=ADMIN_AUDIT_ACTIONS.UTUB_VIEW,
        target_type="Utub",
        target_id=str(utub_id),
    )
    db.session.commit()
    return render_template(
        "admin_portal/utubs/detail.html",
        is_admin_portal=True,
        detail_utub=detail_utub,
        creator_username=creator_username,
        members_page=members_page,
        urls_page=urls_page,
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


def _parse_offset_arg(arg_name: str = "offset") -> int:
    try:
        return max(int(request.args.get(arg_name, "0")), 0)
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
