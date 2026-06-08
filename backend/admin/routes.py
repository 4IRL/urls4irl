from __future__ import annotations

from flask import Blueprint, render_template
from flask.wrappers import Response as FlaskResponse

from backend.api_common.auth_decorators import admin_login_required
from backend.utils.constants import provide_config_for_constants

admin = Blueprint("admin", __name__)


@admin.context_processor
def provide_constants() -> dict:
    return provide_config_for_constants()


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
