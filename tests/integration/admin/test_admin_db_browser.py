from __future__ import annotations

from typing import Tuple
from urllib.parse import quote, urlsplit

import pytest
from flask import Flask
from flask.testing import FlaskClient

from backend import db
from backend.models.audit_log import AuditLog
from backend.models.users import Users
from backend.utils.strings.admin_portal_strs import ADMIN_AUDIT_ACTIONS

pytestmark = pytest.mark.admin

_ADMIN_DB_BROWSER_URL: str = "/admin/db/"
_ADMIN_DB_BROWSER_USERS_URL: str = "/admin/db/users/"
_ADMIN_DB_BROWSER_USERS_NEW_URL: str = "/admin/db/users/new/"
_ADMIN_DB_BROWSER_USERS_DELETE_URL: str = "/admin/db/users/delete/"
_ADMIN_DB_BROWSER_USERS_EXPORT_URL: str = "/admin/db/users/export/csv/"
_PASSWORD_HASH_PREFIX: bytes = b"scrypt:"
_USERS_MODEL_NAME: str = "Users"
_USERS_AUDIT_ENDPOINT: str = f"admin_db_{_USERS_MODEL_NAME.lower()}.index_view"


def test_admin_db_browser_index_returns_200_for_admin(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in admin user
    WHEN the admin sends GET /admin/db/
    THEN the response is 200 OK.
    """
    client, _, _, _ = login_admin_user_with_register

    response = client.get(_ADMIN_DB_BROWSER_URL)

    assert response.status_code == 200


def test_admin_db_browser_users_list_returns_200_for_admin(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in admin user
    WHEN the admin sends GET /admin/db/users/
    THEN the response is 200 OK.
    """
    client, _, _, _ = login_admin_user_with_register

    response = client.get(_ADMIN_DB_BROWSER_USERS_URL)

    assert response.status_code == 200


def test_admin_db_browser_users_list_creates_audit_log_row(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an empty AuditLogs table and a logged-in admin user
    WHEN the admin sends GET /admin/db/users/
    THEN exactly one AuditLog row is created with action == DB_BROWSER_VIEW,
         target_type == "Users", and actor_id == the admin's user id.
    """
    client, _, admin_user, app = login_admin_user_with_register

    with app.app_context():
        rows_before: int = AuditLog.query.count()
    assert rows_before == 0

    client.get(_ADMIN_DB_BROWSER_USERS_URL)

    with app.app_context():
        rows_after: int = AuditLog.query.count()
        assert rows_after == 1
        audit_row: AuditLog | None = AuditLog.query.first()
        assert audit_row is not None
        assert audit_row.action == ADMIN_AUDIT_ACTIONS.DB_BROWSER_VIEW
        assert audit_row.target_type == _USERS_MODEL_NAME
        assert audit_row.actor_id == admin_user.id


def test_admin_db_browser_users_list_excludes_password_hash(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in admin user whose scrypt-hashed password is stored in the DB
    WHEN the admin sends GET /admin/db/users/
    THEN the response body does NOT contain any scrypt hash prefix (column excluded),
         AND the admin's username IS present in the response (proving rows rendered).
    """
    client, _, admin_user, _ = login_admin_user_with_register
    admin_username_bytes: bytes = admin_user.username.encode()

    response = client.get(_ADMIN_DB_BROWSER_USERS_URL)

    assert response.status_code == 200
    assert admin_username_bytes in response.data
    assert _PASSWORD_HASH_PREFIX not in response.data


def test_admin_db_browser_create_endpoint_not_accessible_for_admin(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in admin user and a read-only model view with can_create=False
    WHEN the admin sends GET /admin/db/users/new/
    THEN the response status is NOT 200 (Flask-Admin redirects or 404s when
         record creation is disabled).
    """
    client, _, _, _ = login_admin_user_with_register

    response = client.get(_ADMIN_DB_BROWSER_USERS_NEW_URL)

    assert response.status_code != 200


def test_admin_db_browser_delete_does_not_remove_row(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in admin user and a read-only model view with can_delete=False
    WHEN the admin sends POST /admin/db/users/delete/ with an existing user id
    THEN the Users table row count is UNCHANGED regardless of the response status
         (Flask-Admin rejects the deletion when can_delete is False).
    """
    client, _, admin_user, app = login_admin_user_with_register

    with app.app_context():
        count_before: int = Users.query.count()
    assert count_before > 0

    client.post(
        _ADMIN_DB_BROWSER_USERS_DELETE_URL,
        data={"id": admin_user.id},
    )

    with app.app_context():
        count_after: int = Users.query.count()
    assert count_after == count_before


def test_admin_db_browser_export_endpoint_not_accessible_for_admin(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in admin user and a read-only model view with can_export=False
    WHEN the admin sends GET /admin/db/users/export/csv/
    THEN the response status is NOT 200 (Flask-Admin rejects the export when
         can_export is False).
    """
    client, _, _, _ = login_admin_user_with_register

    response = client.get(_ADMIN_DB_BROWSER_USERS_EXPORT_URL)

    assert response.status_code != 200


def test_admin_db_browser_all_model_views_are_registered(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a running application with the DB browser mounted
    WHEN the Flask url_map / view_functions are inspected
    THEN every SQLAlchemy-mapped model class has a corresponding endpoint
         `admin_db_<classname_lower>.index_view` registered in view_functions.
         (Behavior is asserted per model, not as a hardcoded count.)
    """
    _, _, _, app = login_admin_user_with_register

    with app.app_context():
        model_classes = [
            mapper.class_
            for mapper in db.Model.registry.mappers  # type: ignore[attr-defined]
        ]

    for model_class in model_classes:
        expected_endpoint = f"admin_db_{model_class.__name__.lower()}.index_view"
        assert expected_endpoint in app.view_functions, (
            f"Flask-Admin endpoint '{expected_endpoint}' not found in "
            f"view_functions for model {model_class.__name__!r}"
        )


def test_admin_db_browser_index_returns_403_for_non_admin(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an empty AuditLogs table and a logged-in non-admin user
    WHEN the user sends GET /admin/db/
    THEN the response is 403 Forbidden and no AuditLog rows are created.
    """
    client, _, _, app = login_first_user_with_register

    with app.app_context():
        rows_before: int = AuditLog.query.count()
    assert rows_before == 0

    response = client.get(_ADMIN_DB_BROWSER_URL)

    assert response.status_code == 403

    with app.app_context():
        rows_after: int = AuditLog.query.count()
    assert rows_after == 0


def test_admin_db_browser_users_list_returns_403_for_non_admin(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an empty AuditLogs table and a logged-in non-admin user
    WHEN the user sends GET /admin/db/users/
    THEN the response is 403 Forbidden and no AuditLog rows are created
         (the audit record in index_view is never reached).
    """
    client, _, _, app = login_first_user_with_register

    with app.app_context():
        rows_before: int = AuditLog.query.count()
    assert rows_before == 0

    response = client.get(_ADMIN_DB_BROWSER_USERS_URL)

    assert response.status_code == 403

    with app.app_context():
        rows_after: int = AuditLog.query.count()
    assert rows_after == 0


def test_admin_db_browser_index_redirects_anonymous_to_splash(
    client: FlaskClient,
) -> None:
    """
    GIVEN an anonymous (unauthenticated) browser session
    WHEN the client sends GET /admin/db/
    THEN the response is 302 and redirects away from /admin/db
         (to the login page) with the original path in the `next` parameter.
    """
    response = client.get(_ADMIN_DB_BROWSER_URL)

    assert response.status_code == 302
    assert response.location is not None

    redirect_path = urlsplit(response.location).path
    assert not redirect_path.startswith("/admin")

    encoded_next = quote(_ADMIN_DB_BROWSER_URL, safe="")
    raw_next = _ADMIN_DB_BROWSER_URL
    assert (
        f"next={encoded_next}" in response.location
        or f"next={raw_next}" in response.location
    )
