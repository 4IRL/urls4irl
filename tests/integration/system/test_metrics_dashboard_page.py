from __future__ import annotations

from typing import Tuple
from urllib.parse import quote, urlsplit

import pytest
from flask import Flask
from flask.testing import FlaskClient

from backend.models.users import Users

pytestmark = pytest.mark.cli

_ADMIN_METRICS_URL = "/admin/metrics"


def test_dashboard_page_renders_for_admin(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """Admin GET /admin/metrics returns 200 HTML with the dashboard main shell."""
    client, _, _, _ = login_admin_user_with_register

    response = client.get(_ADMIN_METRICS_URL)

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert b'<main id="MetricsDashboard"' in response.data


def test_dashboard_page_returns_404_for_non_admin(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """Authenticated non-admin user receives a JSON 404 envelope (not HTML)."""
    client, _, _, _ = login_first_user_with_register

    response = client.get(_ADMIN_METRICS_URL)

    assert response.status_code == 404
    assert response.is_json


def test_dashboard_page_redirects_anonymous_to_splash(client: FlaskClient) -> None:
    """Anonymous GET /admin/metrics 302 redirects to splash (`/`) with the
    original path preserved in the `next` query parameter — never to a
    literal `/admin` route.
    """
    response = client.get(_ADMIN_METRICS_URL)

    assert response.status_code == 302
    assert response.location is not None

    redirect_path = urlsplit(response.location).path
    assert not redirect_path.startswith("/admin")

    encoded_next = quote(_ADMIN_METRICS_URL, safe="")
    raw_next = _ADMIN_METRICS_URL
    assert (
        f"next={encoded_next}" in response.location
        or f"next={raw_next}" in response.location
    )


def test_dashboard_page_exposes_app_config_csrf_meta(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """Admin dashboard page renders the standard CSRF meta tag and the
    `app-config` JSON script the JS bundle depends on."""
    client, _, _, _ = login_admin_user_with_register

    response = client.get(_ADMIN_METRICS_URL)

    assert response.status_code == 200
    assert b'<meta name="csrf-token"' in response.data
    assert b'id="app-config"' in response.data
