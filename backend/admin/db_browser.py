from __future__ import annotations

from typing import Any

from flask import Flask, abort, g, redirect, request, url_for
from flask_admin import Admin, AdminIndexView, expose
from flask_admin.contrib.sqla import ModelView
from flask_admin.theme import Bootstrap4Theme
from flask_login import current_user
from werkzeug.wrappers.response import Response as WerkzeugResponse

from backend import db

# Imported for its side effect: backend/models/__init__.py imports every
# model module, so the mapper registry iterated below is fully populated
# even in testing mode (where create_app skips the migration-time import).
import backend.models  # noqa: F401
from backend.extensions import audit
from backend.models.users import User_Role
from backend.utils.all_routes import ROUTES
from backend.utils.strings.admin_portal_strs import ADMIN_AUDIT_ACTIONS

DB_BROWSER_URL: str = "/admin/db"
DB_BROWSER_NAME: str = "U4I DB Browser"
_DB_BROWSER_ENDPOINT: str = "admin_db"
_MODEL_VIEW_PAGE_SIZE: int = 50

# Per-model column exclusions for sensitive data. The browser is read-only,
# but password hashes still must never render in a browser page.
_SENSITIVE_COLUMN_EXCLUSIONS: dict[str, list[str]] = {
    "Users": ["password"],
}


class _AdminAccessMixin:
    """Gate every Flask-Admin view on an authenticated ADMIN session.

    Mirrors `admin_login_required` semantics: anonymous requests are
    redirected (302) to the login page, authenticated non-admin requests
    receive a 403.
    """

    def is_accessible(self) -> bool:
        return bool(
            current_user.is_authenticated and current_user.role == User_Role.ADMIN
        )

    def inaccessible_callback(self, name: str, **kwargs: Any) -> WerkzeugResponse:
        if not current_user.is_authenticated:
            return redirect(url_for(ROUTES.SPLASH.SPLASH_PAGE, next=request.full_path))
        abort(403)


class ProtectedAdminIndexView(_AdminAccessMixin, AdminIndexView):
    """Admin-gated landing page of the DB browser (model list menu)."""


class ReadOnlyModelView(_AdminAccessMixin, ModelView):
    """Strictly read-only Flask-Admin model view.

    No create/edit/delete, and `can_export = False` on every view — a
    one-click CSV dump of the Users table is a bulk personal-data
    exfiltration vector that browsing row-by-row is not. If a targeted
    export need ever arises, enable it per-model with an explicit
    `audit.record(...)` call and a written justification, never
    blanket-on-by-default.
    """

    can_create = False
    can_edit = False
    can_delete = False
    can_export = False
    can_view_details = True
    page_size = _MODEL_VIEW_PAGE_SIZE

    @property
    def session(self):
        """Always resolve the live ``db.session``.

        The test harness swaps ``db.session`` for a transaction-bound
        session per test; a reference captured at construction time would
        query a different (empty) session. Live resolution is equally
        correct in production, where ``db.session`` is the stable scoped
        proxy.
        """
        return db.session

    @session.setter
    def session(self, _session_assigned_by_init) -> None:
        """``ModelView.__init__`` assigns ``self.session``; discard it —
        resolution is always live via the property getter."""

    @expose("/")
    def index_view(self):
        audit.record(
            actor_id=current_user.id,
            action=ADMIN_AUDIT_ACTIONS.DB_BROWSER_VIEW,
            target_type=self.model.__name__,
        )
        return super().index_view()


def _iter_all_model_classes() -> list[type]:
    """Every mapped SQLAlchemy model class, sorted by class name.

    Iterating the registry (rather than a hand-maintained import list)
    guarantees any future model automatically appears in the browser.
    """
    model_classes = [
        mapper.class_
        for mapper in db.Model.registry.mappers  # type: ignore[attr-defined]
    ]
    return sorted(model_classes, key=lambda model_class: model_class.__name__)


def build_read_only_model_view(model_class: type) -> ReadOnlyModelView:
    model_name = model_class.__name__
    view_class: type[ReadOnlyModelView] = ReadOnlyModelView
    sensitive_columns = _SENSITIVE_COLUMN_EXCLUSIONS.get(model_name)
    if sensitive_columns:
        # Column exclusions must be CLASS attributes set before construction —
        # Flask-Admin scaffolds its column lists inside __init__, so mutating
        # the instance afterwards has no effect.
        view_class = type(
            f"ReadOnly{model_name}View",
            (ReadOnlyModelView,),
            {
                "column_exclude_list": sensitive_columns,
                "column_details_exclude_list": sensitive_columns,
            },
        )
    return view_class(
        model_class,
        db.session,
        name=model_name,
        endpoint=f"{_DB_BROWSER_ENDPOINT}_{model_name.lower()}",
        url=model_name.lower(),
    )


def init_db_browser(app: Flask) -> Admin:
    """Mount the read-only Flask-Admin DB browser at ``/admin/db``.

    The portal shell owns ``/admin``; the browser gets its own sub-path and
    endpoint namespace (``admin_db*``) so its generated blueprints never
    collide with the app's ``admin``/``users``/``urls`` blueprints. The
    ``csp_nonce_generator`` feeds the app's per-session nonce into
    Flask-Admin's inline scripts so they run under the strict CSP.
    """
    db_browser = Admin(
        app,
        name=DB_BROWSER_NAME,
        url=DB_BROWSER_URL,
        endpoint=_DB_BROWSER_ENDPOINT,
        index_view=ProtectedAdminIndexView(
            name="Overview",
            endpoint=_DB_BROWSER_ENDPOINT,
            url=DB_BROWSER_URL,
        ),
        theme=Bootstrap4Theme(),
        csp_nonce_generator=lambda: g.nonce,
    )
    for model_class in _iter_all_model_classes():
        db_browser.add_view(build_read_only_model_view(model_class))
    return db_browser
