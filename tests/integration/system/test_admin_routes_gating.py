from __future__ import annotations

import json
import re
from typing import Tuple

import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient

from backend.models.users import Users
from backend.utils.all_routes import ADMIN_ROUTES, SEARCH_ROUTES

pytestmark = pytest.mark.cli

_APP_CONFIG_PATTERN = re.compile(
    rb'<script id="app-config" type="application/json">\s*(\{.*?\})\s*</script>',
    re.DOTALL,
)


def _routes_from_response(response_data: bytes) -> dict[str, str]:
    """Extract APP_CONFIG.routes from the rendered `app-config` script tag."""
    match = _APP_CONFIG_PATTERN.search(response_data)
    assert match is not None, "Page did not render an app-config script tag"
    payload = json.loads(match.group(1).decode("utf-8"))
    routes = payload.get("routes")
    assert isinstance(routes, dict), "APP_CONFIG.routes missing or wrong shape"
    return routes


def test_admin_user_sees_admin_metrics_route_in_app_config(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """Admin users get `adminMetricsPage` in their APP_CONFIG.routes payload."""
    client, _, _, _ = login_admin_user_with_register

    with client.application.test_request_context():
        expected_admin_metrics_url = url_for(ADMIN_ROUTES.METRICS_PAGE)

    response = client.get(expected_admin_metrics_url)

    assert response.status_code == 200
    routes = _routes_from_response(response.data)
    assert routes.get("adminMetricsPage") == expected_admin_metrics_url


def test_non_admin_user_does_not_see_admin_metrics_route_in_app_config(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """Authenticated non-admin users do NOT see `adminMetricsPage` in
    APP_CONFIG.routes — the admin URL is gated server-side.
    """
    client, _, _, _ = login_first_user_with_register

    response = client.get("/home")

    assert response.status_code == 200
    routes = _routes_from_response(response.data)
    assert "adminMetricsPage" not in routes


def test_anonymous_user_does_not_see_admin_metrics_route_in_app_config(
    client: FlaskClient,
) -> None:
    """Anonymous users do NOT see `adminMetricsPage` in APP_CONFIG.routes."""
    response = client.get("/")

    assert response.status_code == 200
    routes = _routes_from_response(response.data)
    assert "adminMetricsPage" not in routes


def test_authenticated_user_sees_cross_utub_search_route_in_app_config(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """Authenticated users get `crossUtubSearch` in their APP_CONFIG.routes
    payload, pointing at the cross-UTub search endpoint.
    """
    client, _, _, _ = login_first_user_with_register

    with client.application.test_request_context():
        expected_cross_utub_search_url = url_for(SEARCH_ROUTES.SEARCH)

    response = client.get("/home")

    assert response.status_code == 200
    routes = _routes_from_response(response.data)
    assert routes.get("crossUtubSearch") == expected_cross_utub_search_url
