from __future__ import annotations

from unittest.mock import MagicMock, patch

from flask import Flask, jsonify
import pytest

from backend.api_common.auth_decorators import ADMIN_AUTH_DECORATORS
from backend.extensions.metrics.admin_auth import metrics_admin_required
from backend.models.users import User_Role
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON

pytestmark = pytest.mark.unit


AUTH_DECORATOR_ATTR = "_auth_decorator"
EXPECTED_DECORATOR_NAME = "metrics_admin_required"


def _stub_view():
    """Minimal handler the decorator wraps."""
    return jsonify({"ok": True}), 200


def _build_app_with_decorated_view() -> Flask:
    """Build a minimal Flask app that exposes a single admin-gated route."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    decorated = metrics_admin_required(_stub_view)
    app.add_url_rule("/admin-stub", view_func=decorated, methods=["GET"])
    return app


class TestMetricsAdminRequiredAttribute:
    """The decorator must stash its name on the wrapper for OpenAPI introspection."""

    def test_decorated_view_has_auth_decorator_attribute(self):
        decorated = metrics_admin_required(_stub_view)
        assert hasattr(decorated, AUTH_DECORATOR_ATTR)
        assert getattr(decorated, AUTH_DECORATOR_ATTR) == EXPECTED_DECORATOR_NAME


class TestMetricsAdminRequiredRegistry:
    """The decorator name must live in ADMIN_AUTH_DECORATORS (not SESSION)."""

    def test_decorator_name_in_admin_registry(self):
        assert EXPECTED_DECORATOR_NAME in ADMIN_AUTH_DECORATORS

    def test_admin_registry_does_not_contain_session_only_names(self):
        # Sanity check: ADMIN_AUTH_DECORATORS is its own set, not overlapping.
        from backend.api_common.auth_decorators import SESSION_AUTH_DECORATORS

        assert EXPECTED_DECORATOR_NAME not in SESSION_AUTH_DECORATORS


class TestMetricsAdminRequiredAnonymous:
    """Anonymous requests must receive a 401 JSON envelope (NOT a 302 redirect)."""

    def test_anonymous_returns_401_json_envelope(self):
        app = _build_app_with_decorated_view()

        anonymous_user = MagicMock()
        anonymous_user.is_authenticated = False

        with patch(
            "backend.extensions.metrics.admin_auth.current_user", anonymous_user
        ):
            client = app.test_client()
            response = client.get("/admin-stub")

        assert response.status_code == 401
        assert response.is_json
        body = response.get_json()
        assert body[STD_JSON.STATUS] == STD_JSON.FAILURE


class TestMetricsAdminRequiredNonAdmin:
    """Authenticated non-admin requests must receive a 404 JSON envelope."""

    def test_authenticated_non_admin_returns_404_json_envelope(self):
        app = _build_app_with_decorated_view()

        non_admin_user = MagicMock()
        non_admin_user.is_authenticated = True
        non_admin_user.role = User_Role.USER

        with patch(
            "backend.extensions.metrics.admin_auth.current_user", non_admin_user
        ):
            client = app.test_client()
            response = client.get("/admin-stub")

        assert response.status_code == 404
        assert response.is_json
        body = response.get_json()
        assert body[STD_JSON.STATUS] == STD_JSON.FAILURE


class TestMetricsAdminRequiredAdminPassThrough:
    """Authenticated admin requests must reach the wrapped handler."""

    def test_authenticated_admin_passes_through_to_handler(self):
        app = _build_app_with_decorated_view()

        admin_user = MagicMock()
        admin_user.is_authenticated = True
        admin_user.role = User_Role.ADMIN

        with patch("backend.extensions.metrics.admin_auth.current_user", admin_user):
            client = app.test_client()
            response = client.get("/admin-stub")

        assert response.status_code == 200
        assert response.is_json
        body = response.get_json()
        assert body == {"ok": True}
