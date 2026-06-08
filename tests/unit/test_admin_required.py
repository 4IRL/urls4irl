from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from flask import Flask, jsonify

from backend.api_common.auth_decorators import (
    ADMIN_AUTH_DECORATORS,
    SESSION_AUTH_DECORATORS,
    admin_login_required,
    admin_required,
)
from backend.models.users import User_Role
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON

pytestmark = pytest.mark.unit


AUTH_DECORATOR_ATTR = "_auth_decorator"
EXPECTED_ADMIN_REQUIRED_NAME = "admin_required"
EXPECTED_ADMIN_LOGIN_REQUIRED_NAME = "admin_login_required"


def _stub_view():
    """Minimal handler the decorator wraps."""
    return jsonify({"ok": True}), 200


def _build_app_with_admin_required() -> Flask:
    """Build a minimal Flask app that exposes a single admin-gated route (JSON API)."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    decorated = admin_required(_stub_view)
    app.add_url_rule("/admin-stub", view_func=decorated, methods=["GET"])
    return app


def _build_app_with_admin_login_required() -> Flask:
    """Build a minimal Flask app with an admin-gated HTML route."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["LOGIN_DISABLED"] = False
    app.secret_key = "test-secret"
    decorated = admin_login_required(_stub_view)
    app.add_url_rule("/admin-html-stub", view_func=decorated, methods=["GET"])
    return app


class TestAdminRequiredAttribute:
    """The decorator must stash its name on the wrapper for OpenAPI introspection."""

    def test_decorated_view_has_auth_decorator_attribute(self):
        decorated = admin_required(_stub_view)
        assert hasattr(decorated, AUTH_DECORATOR_ATTR)
        assert getattr(decorated, AUTH_DECORATOR_ATTR) == EXPECTED_ADMIN_REQUIRED_NAME


class TestAdminLoginRequiredAttribute:
    """admin_login_required must stash its name for OpenAPI introspection."""

    def test_decorated_view_has_auth_decorator_attribute(self):
        decorated = admin_login_required(_stub_view)
        assert hasattr(decorated, AUTH_DECORATOR_ATTR)
        assert (
            getattr(decorated, AUTH_DECORATOR_ATTR)
            == EXPECTED_ADMIN_LOGIN_REQUIRED_NAME
        )


class TestAdminRequiredRegistry:
    """Both admin decorator names must live in ADMIN_AUTH_DECORATORS (not SESSION)."""

    def test_admin_required_name_in_admin_registry(self):
        assert EXPECTED_ADMIN_REQUIRED_NAME in ADMIN_AUTH_DECORATORS

    def test_admin_login_required_name_in_admin_registry(self):
        assert EXPECTED_ADMIN_LOGIN_REQUIRED_NAME in ADMIN_AUTH_DECORATORS

    def test_admin_registry_does_not_contain_session_only_names(self):
        # Sanity check: ADMIN_AUTH_DECORATORS is its own set, not overlapping.
        assert EXPECTED_ADMIN_REQUIRED_NAME not in SESSION_AUTH_DECORATORS
        assert EXPECTED_ADMIN_LOGIN_REQUIRED_NAME not in SESSION_AUTH_DECORATORS


class TestAdminRequiredAnonymous:
    """Anonymous requests must receive a 401 JSON envelope (NOT a 302 redirect)."""

    def test_anonymous_returns_401_json_envelope(self):
        app = _build_app_with_admin_required()

        anonymous_user = MagicMock()
        anonymous_user.is_authenticated = False

        with patch("backend.api_common.auth_decorators.current_user", anonymous_user):
            client = app.test_client()
            response = client.get("/admin-stub")

        assert response.status_code == 401
        assert response.is_json
        body = response.get_json()
        assert body[STD_JSON.STATUS] == STD_JSON.FAILURE


class TestAdminRequiredNonAdmin:
    """Authenticated non-admin requests must receive a 404 JSON envelope."""

    def test_authenticated_non_admin_returns_404_json_envelope(self):
        app = _build_app_with_admin_required()

        non_admin_user = MagicMock()
        non_admin_user.is_authenticated = True
        non_admin_user.role = User_Role.USER

        with patch("backend.api_common.auth_decorators.current_user", non_admin_user):
            client = app.test_client()
            response = client.get("/admin-stub")

        assert response.status_code == 404
        assert response.is_json
        body = response.get_json()
        assert body[STD_JSON.STATUS] == STD_JSON.FAILURE


class TestAdminRequiredAdminPassThrough:
    """Authenticated admin requests must reach the wrapped handler."""

    def test_authenticated_admin_passes_through_to_handler(self):
        app = _build_app_with_admin_required()

        admin_user = MagicMock()
        admin_user.is_authenticated = True
        admin_user.role = User_Role.ADMIN

        with patch("backend.api_common.auth_decorators.current_user", admin_user):
            client = app.test_client()
            response = client.get("/admin-stub")

        assert response.status_code == 200
        assert response.is_json
        body = response.get_json()
        assert body == {"ok": True}


class TestAdminLoginRequiredAnonymous:
    """Anonymous requests to admin_login_required routes must receive a 302 redirect."""

    def test_anonymous_returns_302_redirect(self):
        app = _build_app_with_admin_login_required()

        anonymous_user = MagicMock()
        anonymous_user.is_authenticated = False

        with patch("flask_login.utils._get_user", return_value=anonymous_user):
            client = app.test_client()
            response = client.get("/admin-html-stub")

        assert response.status_code == 302


class TestAdminLoginRequiredNonAdmin:
    """Authenticated non-admin requests must receive a 403."""

    def test_authenticated_non_admin_returns_403(self):
        app = _build_app_with_admin_login_required()

        non_admin_user = MagicMock()
        non_admin_user.is_authenticated = True
        non_admin_user.role = User_Role.USER

        with patch("flask_login.utils._get_user", return_value=non_admin_user):
            with patch(
                "backend.api_common.auth_decorators.current_user", non_admin_user
            ):
                client = app.test_client()
                response = client.get("/admin-html-stub")

        assert response.status_code == 403


class TestAdminLoginRequiredAdminPassThrough:
    """Authenticated admin requests must reach the wrapped handler."""

    def test_authenticated_admin_passes_through_to_handler(self):
        app = _build_app_with_admin_login_required()

        admin_user = MagicMock()
        admin_user.is_authenticated = True
        admin_user.role = User_Role.ADMIN

        with patch("flask_login.utils._get_user", return_value=admin_user):
            with patch("backend.api_common.auth_decorators.current_user", admin_user):
                client = app.test_client()
                response = client.get("/admin-html-stub")

        assert response.status_code == 200
        assert response.is_json
        body = response.get_json()
        assert body == {"ok": True}
