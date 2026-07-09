from __future__ import annotations

from flask import Blueprint, abort, render_template, request
from flask.wrappers import Response as FlaskResponse
from flask_login import current_user

from backend.admin.health_service import collect_health_snapshot
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
    return render_template(
        "admin_portal/index.html",
        is_admin_portal=True,
    )


@admin.route("/admin/health", methods=["GET"])
@admin_login_required
def admin_health() -> FlaskResponse:
    """Server-rendered shell for the system-health dashboard.

    The dashboard content itself is loaded (and every 30s reloaded) from
    ``/admin/health/snapshot`` via htmx; this route only renders the shell
    and audits the page view.
    """
    audit.record(actor_id=current_user.id, action=ADMIN_AUDIT_ACTIONS.HEALTH_VIEW)
    return render_template(
        "admin_portal/health.html",
        is_admin_portal=True,
    )


@admin.route("/admin/health/snapshot", methods=["GET"])
@admin_login_required
def admin_health_snapshot() -> FlaskResponse:
    """HTML fragment with the current health snapshot, swapped in by htmx.

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

    The results table is loaded (on load, and 500ms-debounced on typing)
    from ``/admin/users/search`` via htmx. Not audited itself — the
    load-triggered fragment request records the initial (blank) search.
    """
    return render_template(
        "admin_portal/users/index.html",
        is_admin_portal=True,
    )


@admin.route("/admin/users/search", methods=["GET"])
@admin_login_required
def admin_users_search() -> FlaskResponse:
    """HTML fragment of user-search result rows, swapped in by htmx.

    Every execution is audited with the query and result count — search
    strings land in AuditLogs.metadata and age out with the 90-day
    retention purge.
    """
    search_query: str = request.args.get("q", "")
    try:
        result_offset = max(int(request.args.get("offset", "0")), 0)
    except ValueError:
        result_offset = 0
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
    return render_template(
        "admin_portal/users/_results.html",
        search_page=search_page,
    )


@admin.route("/admin/users/<int:user_id>", methods=["GET"])
@admin_login_required
def admin_user_detail(user_id: int) -> FlaskResponse:
    """Read-only detail page for one user: metadata, role, email-validated
    status, and UTub memberships. No mutating actions exist on this page."""
    detail_user = get_user_detail(user_id=user_id)
    if detail_user is None:
        abort(404)
    audit.record(
        actor_id=current_user.id,
        action=ADMIN_AUDIT_ACTIONS.USER_VIEW,
        target_type="User",
        target_id=str(user_id),
    )
    return render_template(
        "admin_portal/users/detail.html",
        is_admin_portal=True,
        detail_user=detail_user,
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
