from __future__ import annotations

from typing import Tuple
from unittest.mock import patch
from urllib.parse import quote, urlsplit

import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient

from backend.admin.health_service import (
    STATUS_DOWN,
    STATUS_UP,
    collect_health_snapshot,
)
from backend.models.audit_log import AuditLog
from backend.models.users import Users
from backend.utils.all_routes import ADMIN_ROUTES
from backend.utils.strings.admin_portal_strs import (
    ADMIN_AUDIT_ACTIONS,
    ADMIN_PORTAL_STRINGS,
)

pytestmark = pytest.mark.admin

_ADMIN_HEALTH_URL: str = "/admin/health"
_ADMIN_HEALTH_SNAPSHOT_URL: str = "/admin/health/snapshot"
_HEALTH_TITLE_BYTES: bytes = ADMIN_PORTAL_STRINGS.HEALTH_TITLE.encode()
_SNAPSHOT_REGION_ID_BYTES: bytes = b'id="AdminHealthSnapshot"'
_HEALTH_GRID_ID_BYTES: bytes = b'id="AdminHealthGrid"'
_STATUS_UP_BYTES: bytes = STATUS_UP.encode()


def test_admin_health_page_renders_for_admin(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in admin user
    WHEN the admin sends GET /admin/health
    THEN the response is 200 HTML containing the health title text and the
         AdminHealthSnapshot element id.
    """
    client, _, _, app = login_admin_user_with_register

    with app.test_request_context():
        admin_health_url = url_for(ADMIN_ROUTES.HEALTH_PAGE)

    response = client.get(admin_health_url)

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert _HEALTH_TITLE_BYTES in response.data
    assert _SNAPSHOT_REGION_ID_BYTES in response.data


def test_admin_health_page_creates_audit_log_row(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an empty AuditLogs table and a logged-in admin user
    WHEN the admin sends GET /admin/health
    THEN exactly one AuditLog row is created with action == HEALTH_VIEW
         and actor_id == the admin's user id.
    """
    client, _, admin_user, app = login_admin_user_with_register

    with app.app_context():
        rows_before: int = AuditLog.query.count()
    assert rows_before == 0

    client.get(_ADMIN_HEALTH_URL)

    with app.app_context():
        rows_after: int = AuditLog.query.count()
        assert rows_after == 1
        audit_row: AuditLog | None = AuditLog.query.first()
        assert audit_row is not None
        assert audit_row.action == ADMIN_AUDIT_ACTIONS.HEALTH_VIEW
        assert audit_row.actor_id == admin_user.id


def test_admin_health_snapshot_renders_for_admin(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in admin user
    WHEN the admin sends GET /admin/health/snapshot
    THEN the response is 200 HTML containing the AdminHealthGrid id and the
         "up" status string for the database card.
    """
    client, _, _, app = login_admin_user_with_register

    with app.test_request_context():
        snapshot_url = url_for(ADMIN_ROUTES.HEALTH_SNAPSHOT)

    response = client.get(snapshot_url)

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert _HEALTH_GRID_ID_BYTES in response.data
    assert _STATUS_UP_BYTES in response.data


def test_admin_health_snapshot_creates_no_audit_log_row(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an empty AuditLogs table and a logged-in admin user
    WHEN the admin sends GET /admin/health/snapshot
    THEN no AuditLog rows are created (the snapshot endpoint is deliberately
         not audited to avoid flooding the audit log on each 30s poll).
    """
    client, _, _, app = login_admin_user_with_register

    with app.app_context():
        rows_before: int = AuditLog.query.count()
    assert rows_before == 0

    client.get(_ADMIN_HEALTH_SNAPSHOT_URL)

    with app.app_context():
        rows_after: int = AuditLog.query.count()
    assert rows_after == 0


def test_collect_health_snapshot_returns_database_up(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a running test app with a reachable Postgres database
    WHEN collect_health_snapshot() is called directly inside the app context
    THEN database_status == STATUS_UP, database_connection_count is an int
         >= 1, and captured_at is a timezone-aware datetime.
    """
    _, _, _, app = login_admin_user_with_register

    with app.app_context():
        snapshot = collect_health_snapshot()

    assert snapshot.database_status == STATUS_UP
    assert isinstance(snapshot.database_connection_count, int)
    assert snapshot.database_connection_count >= 1
    assert snapshot.captured_at.tzinfo is not None


def test_collect_health_snapshot_degrades_on_database_error(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a running test app where the database probe raises an exception
    WHEN collect_health_snapshot() is called directly inside the app context
    THEN database_status == STATUS_DOWN, database_connection_count is None,
         and the function does NOT raise.
    """
    _, _, _, app = login_admin_user_with_register

    with app.app_context():
        with patch(
            "backend.admin.health_service.db.session.execute",
            side_effect=Exception("simulated database error"),
        ):
            snapshot = collect_health_snapshot()

    assert snapshot.database_status == STATUS_DOWN
    assert snapshot.database_connection_count is None


def test_admin_health_page_returns_403_for_non_admin(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in non-admin user
    WHEN the user sends GET /admin/health
    THEN the response is 403 Forbidden and no AuditLog row is created.
    """
    client, _, _, app = login_first_user_with_register

    with app.app_context():
        rows_before: int = AuditLog.query.count()
    assert rows_before == 0

    response = client.get(_ADMIN_HEALTH_URL)

    assert response.status_code == 403

    with app.app_context():
        rows_after: int = AuditLog.query.count()
    assert rows_after == 0


def test_admin_health_snapshot_returns_403_for_non_admin(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in non-admin user
    WHEN the user sends GET /admin/health/snapshot
    THEN the response is 403 Forbidden.
    """
    client, _, _, _ = login_first_user_with_register

    response = client.get(_ADMIN_HEALTH_SNAPSHOT_URL)

    assert response.status_code == 403


def test_admin_health_page_redirects_anonymous_to_splash(
    client: FlaskClient,
) -> None:
    """
    GIVEN an anonymous (unauthenticated) browser session
    WHEN the client sends GET /admin/health
    THEN the response is 302 and redirects away from /admin/health
         (to the login page) with the original path in the `next` parameter.
    """
    response = client.get(_ADMIN_HEALTH_URL)

    assert response.status_code == 302
    assert response.location is not None

    redirect_path = urlsplit(response.location).path
    assert not redirect_path.startswith("/admin")

    encoded_next = quote(_ADMIN_HEALTH_URL, safe="")
    raw_next = _ADMIN_HEALTH_URL
    assert (
        f"next={encoded_next}" in response.location
        or f"next={raw_next}" in response.location
    )


def test_admin_health_snapshot_redirects_anonymous_to_splash(
    client: FlaskClient,
) -> None:
    """
    GIVEN an anonymous (unauthenticated) browser session
    WHEN the client sends GET /admin/health/snapshot
    THEN the response is 302 and redirects away from /admin.
    """
    response = client.get(_ADMIN_HEALTH_SNAPSHOT_URL)

    assert response.status_code == 302
    assert response.location is not None

    redirect_path = urlsplit(response.location).path
    assert not redirect_path.startswith("/admin")
