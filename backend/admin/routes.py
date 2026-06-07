from __future__ import annotations

from flask import Blueprint, render_template
from flask.wrappers import Response as FlaskResponse
from flask_login import login_required

from backend.api_common.auth_decorators import admin_required
from backend.utils.constants import provide_config_for_constants

admin = Blueprint("admin", __name__)


@admin.context_processor
def provide_constants() -> dict:
    return provide_config_for_constants()


@admin.route("/admin/metrics", methods=["GET"])
@login_required
@admin_required
def admin_metrics() -> FlaskResponse:
    """Server-rendered HTML shell for the admin metrics dashboard.

    Data fetching is entirely client-side via `/api/metrics/query/*`.
    Decorator order (source top-down): `@login_required` then
    `@admin_required`. Flask evaluates decorators bottom-up at request
    time, so `@login_required` (outer) runs first and 302-redirects
    anonymous users; `@admin_required` (inner) then returns JSON 404 for
    authenticated non-admin users.
    """
    return render_template(
        "pages/admin_metrics.html",
        is_admin_metrics=True,
    )
