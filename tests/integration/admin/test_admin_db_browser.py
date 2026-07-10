from __future__ import annotations

from typing import Tuple
from urllib.parse import urlsplit

import pytest
from flask import Flask
from flask.testing import FlaskClient

from backend import db
from backend.models.audit_log import AuditLog
from backend.models.users import Users
from backend.utils.strings.admin_portal_strs import (
    ADMIN_AUDIT_ACTIONS,
    ADMIN_PORTAL_STRINGS,
)
from tests.integration.admin.seed_helpers import (
    seed_event_registry_row,
    seed_utub_member,
)

pytestmark = pytest.mark.admin

_ADMIN_DB_OVERVIEW_URL: str = "/admin/db"
_ADMIN_DB_USERS_URL: str = "/admin/db/Users"
_ADMIN_DB_USERS_ROW_URL: str = "/admin/db/Users/1"
_ADMIN_DB_UNKNOWN_TABLE_URL: str = "/admin/db/NotATable"
_ADMIN_DB_UNKNOWN_ROW_URL: str = "/admin/db/Users/999999"
_ADMIN_DB_GATED_URLS: list[str] = [
    _ADMIN_DB_OVERVIEW_URL,
    _ADMIN_DB_USERS_URL,
    _ADMIN_DB_USERS_ROW_URL,
]

_PASSWORD_HASH_PREFIX: bytes = b"scrypt:"
_USERS_MODEL_NAME: str = "Users"
_OVERVIEW_TABLES_ID: bytes = b'id="AdminDbTables"'
_ROW_DETAIL_ID: bytes = b'id="AdminDbRowDetail"'

_SECOND_USERNAME: str = "seconddbuser"
_THIRD_USERNAME: str = "thirddbuser"
_SEEDED_EMAIL_DOMAIN: str = "@browser.example.com"
_SEEDED_PASSWORD: str = "SuperSecret123!"
_EVENT_REGISTRY_NAME: str = "admin_db_route_test_event"


def _seed_extra_user(username: str) -> Users:
    """Insert one extra validated (non-logged-in) user.

    The username only ever appears in a grid cell — never in the shared layout
    topbar/modals that render the *logged-in* user — so it is a reliable proof
    that a grid row rendered.
    """
    extra_user = Users(
        username=username,
        email=f"{username}{_SEEDED_EMAIL_DOMAIN}",
        plaintext_password=_SEEDED_PASSWORD,
    )
    extra_user.email_validated = True
    db.session.add(extra_user)
    db.session.commit()
    return extra_user


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------


def test_admin_db_overview_returns_200_and_audits(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an empty AuditLogs table and a logged-in admin user
    WHEN the admin sends GET /admin/db
    THEN the response is 200 with the DB-browser title and table grid, and
         exactly one DB_BROWSER_VIEW audit row is recorded with no target_type.
    """
    client, _, admin_user, app = login_admin_user_with_register

    with app.app_context():
        assert AuditLog.query.count() == 0

    response = client.get(_ADMIN_DB_OVERVIEW_URL)

    assert response.status_code == 200
    assert ADMIN_PORTAL_STRINGS.DB_BROWSER_TITLE.encode() in response.data
    assert _OVERVIEW_TABLES_ID in response.data

    with app.app_context():
        assert AuditLog.query.count() == 1
        audit_row: AuditLog | None = AuditLog.query.first()
        assert audit_row is not None
        assert audit_row.action == ADMIN_AUDIT_ACTIONS.DB_BROWSER_VIEW
        assert audit_row.target_type is None
        assert audit_row.actor_id == admin_user.id


# ---------------------------------------------------------------------------
# Table grid
# ---------------------------------------------------------------------------


def test_admin_db_table_grid_renders_rows_and_masks_password(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in admin user and a seeded non-logged-in user whose
          scrypt-hashed passwords are stored
    WHEN the admin sends GET /admin/db/Users
    THEN the body contains the seeded username (proving a grid row rendered)
         but NOT the password hash, and exactly one DB_BROWSER_VIEW audit row
         targets "Users".
    """
    client, _, _, app = login_admin_user_with_register

    with app.app_context():
        assert AuditLog.query.count() == 0
        _seed_extra_user(_SECOND_USERNAME)

    response = client.get(_ADMIN_DB_USERS_URL)

    assert response.status_code == 200
    assert _SECOND_USERNAME.encode() in response.data
    assert _PASSWORD_HASH_PREFIX not in response.data

    with app.app_context():
        assert AuditLog.query.count() == 1
        audit_row: AuditLog | None = AuditLog.query.first()
        assert audit_row is not None
        assert audit_row.action == ADMIN_AUDIT_ACTIONS.DB_BROWSER_VIEW
        assert audit_row.target_type == _USERS_MODEL_NAME


def test_admin_db_table_unknown_table_returns_404_without_audit(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    client, _, _, app = login_admin_user_with_register

    response = client.get(_ADMIN_DB_UNKNOWN_TABLE_URL)

    assert response.status_code == 404
    with app.app_context():
        assert AuditLog.query.count() == 0


def test_admin_db_table_invalid_offset_falls_back_to_zero(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    client, _, _, _ = login_admin_user_with_register

    response = client.get(f"{_ADMIN_DB_USERS_URL}?offset=notanumber")

    assert response.status_code == 200


def test_admin_db_table_offset_pagination_is_disjoint(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN the admin (id 1) plus two seeded users (ids 2 and 3)
    WHEN the admin browses the Users grid at offset 0 vs offset 2
    THEN offset 0 shows both seeded usernames while offset 2 skips the first
         seeded user (id 2) and still shows the second (id 3) — proving the
         offset is applied and the pages are disjoint. Both seeded usernames
         only ever appear in grid cells, never in the logged-in-user layout.
    """
    client, _, _, app = login_admin_user_with_register

    with app.app_context():
        _seed_extra_user(_SECOND_USERNAME)
        _seed_extra_user(_THIRD_USERNAME)

    first_page = client.get(_ADMIN_DB_USERS_URL)
    third_offset_page = client.get(f"{_ADMIN_DB_USERS_URL}?offset=2")

    assert first_page.status_code == 200
    assert third_offset_page.status_code == 200
    assert _SECOND_USERNAME.encode() in first_page.data
    assert _THIRD_USERNAME.encode() in first_page.data
    assert _SECOND_USERNAME.encode() not in third_offset_page.data
    assert _THIRD_USERNAME.encode() in third_offset_page.data


def test_every_mapped_model_is_browsable(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a running application with the native DB browser mounted
    WHEN the admin GETs /admin/db/<table_name> for every mapped model
    THEN each grid page returns 200 (empty tables render an empty-state panel).
         Behavior is asserted per model, not as a hardcoded count.
    """
    client, _, _, app = login_admin_user_with_register

    with app.app_context():
        table_names = [
            mapper.class_.__tablename__
            for mapper in db.Model.registry.mappers  # type: ignore[attr-defined]
        ]

    for table_name in table_names:
        response = client.get(f"/admin/db/{table_name}")
        assert (
            response.status_code == 200
        ), f"DB-browser grid for table {table_name!r} did not return 200"


# ---------------------------------------------------------------------------
# Row detail
# ---------------------------------------------------------------------------


def test_admin_db_row_detail_renders_and_audits(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in admin user
    WHEN the admin sends GET /admin/db/Users/1
    THEN the row-detail table renders but the password hash does NOT, and
         exactly one DB_BROWSER_VIEW audit row targets "Users" with
         target_id == "1".
    """
    client, _, _, app = login_admin_user_with_register

    with app.app_context():
        assert AuditLog.query.count() == 0

    response = client.get(_ADMIN_DB_USERS_ROW_URL)

    assert response.status_code == 200
    assert _ROW_DETAIL_ID in response.data
    assert _PASSWORD_HASH_PREFIX not in response.data

    with app.app_context():
        assert AuditLog.query.count() == 1
        audit_row: AuditLog | None = AuditLog.query.first()
        assert audit_row is not None
        assert audit_row.action == ADMIN_AUDIT_ACTIONS.DB_BROWSER_VIEW
        assert audit_row.target_type == _USERS_MODEL_NAME
        assert audit_row.target_id == "1"


def test_admin_db_row_unknown_pk_returns_404(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    client, _, _, _ = login_admin_user_with_register

    response = client.get(_ADMIN_DB_UNKNOWN_ROW_URL)

    assert response.status_code == 404


def test_admin_db_row_composite_pk_resolves(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    client, _, _, app = login_admin_user_with_register

    with app.app_context():
        utub_member = seed_utub_member(user_id=1)
        pk_segment = f"{utub_member.utub_id},{utub_member.user_id}"

    response = client.get(f"/admin/db/UtubMembers/{pk_segment}")

    assert response.status_code == 200


def test_admin_db_row_string_pk_resolves(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    client, _, _, app = login_admin_user_with_register

    with app.app_context():
        seed_event_registry_row(name=_EVENT_REGISTRY_NAME)

    response = client.get(f"/admin/db/EventRegistry/{_EVENT_REGISTRY_NAME}")

    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Read-only guarantee (GET-only routes; no mutation surface exists)
# ---------------------------------------------------------------------------


def test_admin_db_table_rejects_post(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    client, _, _, _ = login_admin_user_with_register

    response = client.post(_ADMIN_DB_USERS_URL)

    assert response.status_code == 405


def test_admin_db_row_rejects_post(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    client, _, _, _ = login_admin_user_with_register

    response = client.post(_ADMIN_DB_USERS_ROW_URL)

    assert response.status_code == 405


# ---------------------------------------------------------------------------
# Gating: non-admin 403, anonymous 302
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("url", _ADMIN_DB_GATED_URLS)
def test_admin_db_returns_403_for_non_admin_without_audit(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    url: str,
) -> None:
    client, _, _, app = login_first_user_with_register

    with app.app_context():
        assert AuditLog.query.count() == 0

    response = client.get(url)

    assert response.status_code == 403
    with app.app_context():
        assert AuditLog.query.count() == 0


@pytest.mark.parametrize("url", _ADMIN_DB_GATED_URLS)
def test_admin_db_redirects_anonymous_to_splash(
    client: FlaskClient,
    url: str,
) -> None:
    response = client.get(url)

    assert response.status_code == 302
    assert response.location is not None

    redirect_path = urlsplit(response.location).path
    assert not redirect_path.startswith("/admin")
    assert "next=" in response.location
