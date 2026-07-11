from __future__ import annotations

from typing import Tuple
from urllib.parse import quote, urlsplit

import pytest
from flask import Flask
from flask.testing import FlaskClient

from backend import db
from backend.models.audit_log import AuditLog
from backend.models.urls import Urls
from backend.models.users import Users
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.utils.strings.admin_portal_strs import (
    ADMIN_AUDIT_ACTIONS,
    ADMIN_PORTAL_STRINGS,
)

pytestmark = pytest.mark.admin

_ADMIN_UTUBS_URL: str = "/admin/utubs"
_UTUB_ACTIONS_TITLE_BYTES: bytes = ADMIN_PORTAL_STRINGS.UTUB_ACTIONS_TITLE.encode()
_SEARCH_INPUT_ID_BYTES: bytes = b'id="AdminUtubTableSearch"'
_TABLE_GRID_ID_BYTES: bytes = b'id="AdminUtubTableGrid"'
_DETAIL_TITLE_ID_BYTES: bytes = b'id="AdminUtubDetailTitle"'
_DETAIL_MEMBERS_TABLE_ID_BYTES: bytes = b'id="AdminUtubDetailMembersTable"'
_DETAIL_URLS_TABLE_ID_BYTES: bytes = b'id="AdminUtubDetailUrlsTable"'

_ALPHA_UTUB_NAME: str = "AlphaSeededUtub"
_BETA_UTUB_NAME: str = "BetaSeededUtub"
_DETAIL_UTUB_NAME: str = "DetailSeededUtub"
_DETAIL_URL_STRING: str = "https://detail-seeded-example.test/page"
_DETAIL_URL_TITLE: str = "Detail Seeded URL Title"
_MISSING_UTUB_ID: int = 999999


def _seed_utub(*, name: str, creator_id: int) -> int:
    """Insert one UTub owned by ``creator_id`` and return its id."""
    new_utub = Utubs(name=name, utub_creator=creator_id, utub_description="")
    db.session.add(new_utub)
    db.session.commit()
    return new_utub.id


def _seed_utub_with_content(*, name: str, creator_id: int) -> int:
    """Insert one UTub owned by ``creator_id`` with the creator as a member and
    a single URL association, returning the UTub id.

    Provides the aggregated detail page with at least one member row and one
    URL row so the members/URLs tables render (rather than empty states).
    """
    new_utub = Utubs(name=name, utub_creator=creator_id, utub_description="")
    db.session.add(new_utub)
    db.session.flush()
    db.session.add(
        Utub_Members(
            utub_id=new_utub.id,
            user_id=creator_id,
            member_role=Member_Role.CREATOR,
        )
    )
    new_url = Urls(normalized_url=_DETAIL_URL_STRING, current_user_id=creator_id)
    db.session.add(new_url)
    db.session.flush()
    db.session.add(
        Utub_Urls(
            utub_id=new_utub.id,
            url_id=new_url.id,
            user_id=creator_id,
            url_title=_DETAIL_URL_TITLE,
        )
    )
    db.session.commit()
    return new_utub.id


# ---------------------------------------------------------------------------
# UTub Actions list page
# ---------------------------------------------------------------------------


def test_admin_utubs_page_renders_grid_for_admin(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in admin user and two seeded UTubs
    WHEN the admin sends GET /admin/utubs
    THEN the response is 200 HTML containing the UTub Actions title, the search
         input id, the table grid id, and a seeded UTub name; and exactly one
         AuditLog row is created with action UTUB_LIST, actor_id == the admin's
         user id, and metadata {"query": "", "result_count": <all UTub count>}.
    """
    client, _, admin_user, app = login_admin_user_with_register

    with app.app_context():
        _seed_utub(name=_ALPHA_UTUB_NAME, creator_id=admin_user.id)
        _seed_utub(name=_BETA_UTUB_NAME, creator_id=admin_user.id)
        total_utub_count: int = Utubs.query.count()
        rows_before: int = AuditLog.query.count()
    assert rows_before == 0
    assert total_utub_count == 2

    response = client.get(_ADMIN_UTUBS_URL)

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert _UTUB_ACTIONS_TITLE_BYTES in response.data
    assert _SEARCH_INPUT_ID_BYTES in response.data
    assert _TABLE_GRID_ID_BYTES in response.data
    assert _ALPHA_UTUB_NAME.encode() in response.data

    with app.app_context():
        rows_after: int = AuditLog.query.count()
        assert rows_after == 1
        audit_row: AuditLog | None = AuditLog.query.first()
        assert audit_row is not None
        assert audit_row.action == ADMIN_AUDIT_ACTIONS.UTUB_LIST
        assert audit_row.actor_id == admin_user.id
        assert audit_row.target_type is None
        assert audit_row.log_metadata == {
            "query": "",
            "result_count": total_utub_count,
        }


def test_admin_utubs_page_filters_by_query(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in admin user and two seeded UTubs with distinct names
    WHEN the admin sends GET /admin/utubs?q=<alpha name>
    THEN the grid contains the alpha UTub name but not the beta one, and
         exactly one AuditLog row is created with metadata.query == the alpha
         name and metadata.result_count == 1.
    """
    client, _, admin_user, app = login_admin_user_with_register

    with app.app_context():
        _seed_utub(name=_ALPHA_UTUB_NAME, creator_id=admin_user.id)
        _seed_utub(name=_BETA_UTUB_NAME, creator_id=admin_user.id)
        rows_before: int = AuditLog.query.count()
    assert rows_before == 0

    response = client.get(f"{_ADMIN_UTUBS_URL}?q={_ALPHA_UTUB_NAME}")

    assert response.status_code == 200
    assert _ALPHA_UTUB_NAME.encode() in response.data
    assert _BETA_UTUB_NAME.encode() not in response.data

    with app.app_context():
        rows_after: int = AuditLog.query.count()
        assert rows_after == 1
        audit_row: AuditLog | None = AuditLog.query.first()
        assert audit_row is not None
        assert audit_row.action == ADMIN_AUDIT_ACTIONS.UTUB_LIST
        assert audit_row.actor_id == admin_user.id
        assert audit_row.log_metadata == {
            "query": _ALPHA_UTUB_NAME,
            "result_count": 1,
        }


# ---------------------------------------------------------------------------
# Access-control: non-admin (403) and anonymous (302)
# ---------------------------------------------------------------------------


def test_admin_utubs_page_returns_403_for_non_admin(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an empty AuditLogs table and a logged-in non-admin user
    WHEN the user sends GET /admin/utubs
    THEN the response is 403 Forbidden and no AuditLog row is created.
    """
    client, _, _, app = login_first_user_with_register

    with app.app_context():
        rows_before: int = AuditLog.query.count()
    assert rows_before == 0

    response = client.get(_ADMIN_UTUBS_URL)

    assert response.status_code == 403

    with app.app_context():
        rows_after: int = AuditLog.query.count()
    assert rows_after == 0


def test_admin_utubs_page_redirects_anonymous_to_splash(
    client: FlaskClient,
) -> None:
    """
    GIVEN an anonymous (unauthenticated) browser session
    WHEN the client sends GET /admin/utubs
    THEN the response is 302 and redirects away from /admin (to the login
         page) with the original path in the ``next`` parameter.
    """
    response = client.get(_ADMIN_UTUBS_URL)

    assert response.status_code == 302
    assert response.location is not None

    redirect_path = urlsplit(response.location).path
    assert not redirect_path.startswith("/admin")

    encoded_next = quote(_ADMIN_UTUBS_URL, safe="")
    raw_next = _ADMIN_UTUBS_URL
    assert (
        f"next={encoded_next}" in response.location
        or f"next={raw_next}" in response.location
    )


# ---------------------------------------------------------------------------
# UTub detail page
# ---------------------------------------------------------------------------


def test_admin_utub_detail_renders_for_admin(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in admin user and a seeded UTub with one member and one URL
    WHEN the admin sends GET /admin/utubs/<id>
    THEN the response is 200 HTML containing the UTub name, the detail title id,
         the members-table id with the member's username, and the URLs-table id
         with the seeded URL string; and exactly one AuditLog row is created with
         action UTUB_VIEW, target_type "Utub", target_id str(<id>), and
         actor_id == the admin's user id.
    """
    client, _, admin_user, app = login_admin_user_with_register

    with app.app_context():
        admin_username: str = admin_user.username
        utub_id: int = _seed_utub_with_content(
            name=_DETAIL_UTUB_NAME, creator_id=admin_user.id
        )
        rows_before: int = AuditLog.query.count()
    assert rows_before == 0

    response = client.get(f"{_ADMIN_UTUBS_URL}/{utub_id}")

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert _DETAIL_TITLE_ID_BYTES in response.data
    assert _DETAIL_UTUB_NAME.encode() in response.data
    assert _DETAIL_MEMBERS_TABLE_ID_BYTES in response.data
    assert admin_username.encode() in response.data
    assert _DETAIL_URLS_TABLE_ID_BYTES in response.data
    assert _DETAIL_URL_STRING.encode() in response.data

    with app.app_context():
        rows_after: int = AuditLog.query.count()
        assert rows_after == 1
        audit_row: AuditLog | None = AuditLog.query.first()
        assert audit_row is not None
        assert audit_row.action == ADMIN_AUDIT_ACTIONS.UTUB_VIEW
        assert audit_row.actor_id == admin_user.id
        assert audit_row.target_type == "Utub"
        assert audit_row.target_id == str(utub_id)


def test_admin_utub_detail_returns_404_for_missing_id(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in admin user and no UTub with the requested id
    WHEN the admin sends GET /admin/utubs/<missing id>
    THEN the response is 404 and no AuditLog row is created.
    """
    client, _, _, app = login_admin_user_with_register

    with app.app_context():
        assert Utubs.query.get(_MISSING_UTUB_ID) is None
        rows_before: int = AuditLog.query.count()
    assert rows_before == 0

    response = client.get(f"{_ADMIN_UTUBS_URL}/{_MISSING_UTUB_ID}")

    assert response.status_code == 404

    with app.app_context():
        rows_after: int = AuditLog.query.count()
    assert rows_after == 0


def test_admin_utub_detail_returns_403_for_non_admin(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in non-admin user and one seeded UTub
    WHEN the user sends GET /admin/utubs/<id>
    THEN the response is 403 Forbidden and no AuditLog row is created.
    """
    client, _, user, app = login_first_user_with_register

    with app.app_context():
        utub_id: int = _seed_utub(name=_DETAIL_UTUB_NAME, creator_id=user.id)
        rows_before: int = AuditLog.query.count()
    assert rows_before == 0

    response = client.get(f"{_ADMIN_UTUBS_URL}/{utub_id}")

    assert response.status_code == 403

    with app.app_context():
        rows_after: int = AuditLog.query.count()
    assert rows_after == 0


def test_admin_utub_detail_redirects_anonymous_to_splash(
    client: FlaskClient,
) -> None:
    """
    GIVEN an anonymous (unauthenticated) browser session
    WHEN the client sends GET /admin/utubs/<id>
    THEN the response is 302 and redirects away from /admin (to the login
         page) with the original path in the ``next`` parameter.
    """
    detail_path = f"{_ADMIN_UTUBS_URL}/1"

    response = client.get(detail_path)

    assert response.status_code == 302
    assert response.location is not None

    redirect_path = urlsplit(response.location).path
    assert not redirect_path.startswith("/admin")

    encoded_next = quote(detail_path, safe="")
    assert (
        f"next={encoded_next}" in response.location
        or f"next={detail_path}" in response.location
    )
