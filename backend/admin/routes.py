from __future__ import annotations

from flask import Blueprint, render_template
from flask.wrappers import Response as FlaskResponse
from flask_login import current_user

from backend.api_common.auth_decorators import admin_login_required
from backend.admin.health_service import collect_health_snapshot
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
        "admin/index.html",
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
        "admin/health.html",
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
        "admin/_health_snapshot.html",
        snapshot=health_snapshot,
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
