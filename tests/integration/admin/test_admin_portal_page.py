from __future__ import annotations

from typing import Tuple
from urllib.parse import quote, urlsplit

import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient

from backend.models.audit_log import AuditLog
from backend.models.users import Users
from backend.utils.all_routes import ADMIN_ROUTES
from backend.utils.strings.admin_portal_strs import (
    ADMIN_AUDIT_ACTIONS,
    ADMIN_PORTAL_STRINGS,
)

pytestmark = pytest.mark.admin

_ADMIN_PORTAL_URL = "/admin"
_PORTAL_TITLE_BYTES = ADMIN_PORTAL_STRINGS.PORTAL_TITLE.encode()
_NAV_ID_BYTES = b'id="AdminNav"'


def test_admin_portal_page_renders_for_admin(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in admin user
    WHEN the admin sends GET /admin
    THEN the response is 200 HTML containing the portal title text and the
         AdminNav element id.
    """
    client, _, _, app = login_admin_user_with_register

    with app.test_request_context():
        admin_portal_url = url_for(ADMIN_ROUTES.PORTAL)

    response = client.get(admin_portal_url)

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert _PORTAL_TITLE_BYTES in response.data
    assert _NAV_ID_BYTES in response.data


def test_admin_portal_page_creates_audit_log_row(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an empty AuditLogs table and a logged-in admin user
    WHEN the admin sends GET /admin
    THEN exactly one AuditLog row is created with action == PORTAL_VIEW
         and actor_id == the admin's user id, with target_type left null.
    """
    client, _, admin_user, app = login_admin_user_with_register

    with app.app_context():
        rows_before: int = AuditLog.query.count()
    assert rows_before == 0

    client.get(_ADMIN_PORTAL_URL)

    with app.app_context():
        rows_after: int = AuditLog.query.count()
        assert rows_after == 1
        audit_row: AuditLog | None = AuditLog.query.first()
        assert audit_row is not None
        assert audit_row.action == ADMIN_AUDIT_ACTIONS.PORTAL_VIEW
        assert audit_row.actor_id == admin_user.id
        assert audit_row.target_type is None


def test_admin_portal_page_returns_403_for_non_admin(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an empty AuditLogs table and a logged-in non-admin user
    WHEN the user sends GET /admin
    THEN the response is 403 Forbidden and no AuditLog row is created.
    """
    client, _, _, app = login_first_user_with_register

    with app.app_context():
        rows_before: int = AuditLog.query.count()
    assert rows_before == 0

    response = client.get(_ADMIN_PORTAL_URL)

    assert response.status_code == 403

    with app.app_context():
        rows_after: int = AuditLog.query.count()
    assert rows_after == 0


def test_admin_portal_page_redirects_anonymous_to_splash(client: FlaskClient) -> None:
    """
    GIVEN an anonymous (unauthenticated) browser session
    WHEN the client sends GET /admin
    THEN the response is 302 and redirects away from /admin
         (to the login page) with the original path in the `next` parameter.
    """
    response = client.get(_ADMIN_PORTAL_URL)

    assert response.status_code == 302
    assert response.location is not None

    redirect_path = urlsplit(response.location).path
    assert not redirect_path.startswith("/admin")

    encoded_next = quote(_ADMIN_PORTAL_URL, safe="")
    raw_next = _ADMIN_PORTAL_URL
    assert (
        f"next={encoded_next}" in response.location
        or f"next={raw_next}" in response.location
    )
