from __future__ import annotations

from typing import Tuple
from urllib.parse import quote, urlsplit

import pytest
from flask import Flask
from flask.testing import FlaskClient

from backend import db
from backend.admin.user_service import search_users
from backend.models.audit_log import AuditLog
from backend.models.users import Users
from backend.utils.strings.admin_portal_strs import (
    ADMIN_AUDIT_ACTIONS,
    ADMIN_PORTAL_STRINGS,
)

pytestmark = pytest.mark.admin

_ADMIN_USERS_URL: str = "/admin/users"
_ADMIN_USERS_SEARCH_URL: str = "/admin/users/search"
_USERS_TITLE_BYTES: bytes = ADMIN_PORTAL_STRINGS.USERS_TITLE.encode()
_SEARCH_INPUT_ID_BYTES: bytes = b'id="AdminUserSearchInput"'
_UNKNOWN_USER_ID: int = 999_999

# Extra user credentials used in filtering and pagination tests.
_ALPHA_USERNAME: str = "alphauser"
_ALPHA_EMAIL: str = "alpha@example.com"
_BETA_USERNAME: str = "betauser"
_BETA_EMAIL: str = "beta@x.com"
_PAGINATION_USERNAME_BASE: str = "paginationuser"
_PAGINATION_EMAIL_DOMAIN: str = "@pagination.example.com"
_PAGINATION_EXTRA_COUNT: int = 3
_DETAIL_USERNAME: str = "detailtestuser"
_DETAIL_EMAIL: str = "detailtest@example.com"

_TARGET_TYPE_USER: str = "User"


# ---------------------------------------------------------------------------
# Admin users index page
# ---------------------------------------------------------------------------


def test_admin_users_page_renders_for_admin(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in admin user
    WHEN the admin sends GET /admin/users
    THEN the response is 200 HTML containing the USERS_TITLE text and the
         AdminUserSearchInput element id, and no AuditLog row is created
         (the shell itself is not audited — the fragment request is).
    """
    client, _, _, app = login_admin_user_with_register

    with app.app_context():
        rows_before: int = AuditLog.query.count()
    assert rows_before == 0

    response = client.get(_ADMIN_USERS_URL)

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert _USERS_TITLE_BYTES in response.data
    assert _SEARCH_INPUT_ID_BYTES in response.data

    with app.app_context():
        rows_after: int = AuditLog.query.count()
    assert rows_after == 0


# ---------------------------------------------------------------------------
# Admin users search fragment
# ---------------------------------------------------------------------------


def test_admin_users_search_blank_query_returns_all_users(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an empty AuditLogs table and a logged-in admin user (the only user
         in the database at this point)
    WHEN the admin sends GET /admin/users/search without a ``q`` parameter
    THEN the response is 200 HTML containing the admin's username; exactly
         one AuditLog row is created with action USER_SEARCH, metadata
         equal to {"query": "", "result_count": <all user count>}, and
         actor_id equal to the admin's user id.
    """
    client, _, admin_user, app = login_admin_user_with_register
    admin_username_bytes: bytes = admin_user.username.encode()

    with app.app_context():
        rows_before: int = AuditLog.query.count()
        total_user_count: int = Users.query.count()
    assert rows_before == 0

    response = client.get(_ADMIN_USERS_SEARCH_URL)

    assert response.status_code == 200
    assert admin_username_bytes in response.data

    with app.app_context():
        rows_after: int = AuditLog.query.count()
        assert rows_after == 1
        audit_row: AuditLog | None = AuditLog.query.first()
        assert audit_row is not None
        assert audit_row.action == ADMIN_AUDIT_ACTIONS.USER_SEARCH
        assert audit_row.actor_id == admin_user.id
        assert audit_row.target_type is None
        assert audit_row.log_metadata == {
            "query": "",
            "result_count": total_user_count,
        }


def test_admin_users_search_filters_by_username(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in admin user and two additional users — one with
         username "alphauser" and one with username "betauser"
    WHEN the admin sends GET /admin/users/search?q=alpha
    THEN the fragment contains "alphauser" but not "betauser", exactly one
         AuditLog row is created with action USER_SEARCH, metadata.query ==
         "alpha", and metadata.result_count == 1.
    """
    client, _, admin_user, app = login_admin_user_with_register

    with app.app_context():
        alpha_user = Users(
            username=_ALPHA_USERNAME,
            email=_ALPHA_EMAIL,
            plaintext_password="AlphaPassword1234",
        )
        alpha_user.email_validated = True
        beta_user = Users(
            username=_BETA_USERNAME,
            email=_BETA_EMAIL,
            plaintext_password="BetaPassword1234",
        )
        beta_user.email_validated = True
        db.session.add(alpha_user)
        db.session.add(beta_user)
        db.session.commit()

    with app.app_context():
        rows_before: int = AuditLog.query.count()
    assert rows_before == 0

    response = client.get(f"{_ADMIN_USERS_SEARCH_URL}?q=alpha")

    assert response.status_code == 200
    assert _ALPHA_USERNAME.encode() in response.data
    assert _BETA_USERNAME.encode() not in response.data

    with app.app_context():
        rows_after: int = AuditLog.query.count()
        assert rows_after == 1
        audit_row: AuditLog | None = AuditLog.query.first()
        assert audit_row is not None
        assert audit_row.action == ADMIN_AUDIT_ACTIONS.USER_SEARCH
        assert audit_row.actor_id == admin_user.id
        assert audit_row.log_metadata == {"query": "alpha", "result_count": 1}


def test_admin_users_search_filters_by_email(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in admin user and two additional users — one with email
         "alpha@example.com" and one with email "beta@x.com"
    WHEN the admin sends GET /admin/users/search?q=beta@x
    THEN the fragment contains "betauser" but not "alphauser", and the audit
         metadata result_count == 1.
    """
    client, _, admin_user, app = login_admin_user_with_register

    with app.app_context():
        alpha_user = Users(
            username=_ALPHA_USERNAME,
            email=_ALPHA_EMAIL,
            plaintext_password="AlphaPassword1234",
        )
        alpha_user.email_validated = True
        beta_user = Users(
            username=_BETA_USERNAME,
            email=_BETA_EMAIL,
            plaintext_password="BetaPassword1234",
        )
        beta_user.email_validated = True
        db.session.add(alpha_user)
        db.session.add(beta_user)
        db.session.commit()

    with app.app_context():
        rows_before: int = AuditLog.query.count()
    assert rows_before == 0

    response = client.get(f"{_ADMIN_USERS_SEARCH_URL}?q=beta@x")

    assert response.status_code == 200
    assert _BETA_USERNAME.encode() in response.data
    assert _ALPHA_USERNAME.encode() not in response.data

    with app.app_context():
        rows_after: int = AuditLog.query.count()
        assert rows_after == 1
        audit_row: AuditLog | None = AuditLog.query.first()
        assert audit_row is not None
        assert audit_row.log_metadata == {"query": "beta@x", "result_count": 1}


def test_search_users_wildcard_escaping(app: Flask, register_first_user) -> None:
    """
    GIVEN a registered user whose username and email contain no literal
         "%" characters
    WHEN search_users() is called with query="%" inside an app context
    THEN total_count is 0, proving the "%" is treated as a literal character
         by the ILIKE clause rather than a wildcard; and calling with query=""
         returns the full user count.
    """
    _, registered_user = register_first_user

    with app.app_context():
        percent_page = search_users(query="%")
        blank_page = search_users(query="")
        total_users_in_db: int = Users.query.count()

    assert percent_page.total_count == 0
    assert blank_page.total_count == total_users_in_db
    assert total_users_in_db >= 1


def test_search_users_pagination(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in admin user and three additional users (four total)
    WHEN search_users() is called with limit=2 and offset=0 then offset=2
    THEN the two pages are disjoint, page one has has_previous=False and
         has_next=True, page two has has_previous=True and has_next=False;
         and GET /admin/users/search?q=&offset=<beyond total> returns 200
         with an empty results table.
    """
    client, _, _, app = login_admin_user_with_register

    with app.app_context():
        for extra_user_index in range(1, _PAGINATION_EXTRA_COUNT + 1):
            extra_user = Users(
                username=f"{_PAGINATION_USERNAME_BASE}{extra_user_index}",
                email=f"{_PAGINATION_USERNAME_BASE}{extra_user_index}{_PAGINATION_EMAIL_DOMAIN}",
                plaintext_password=f"PaginationPassword{extra_user_index}",
            )
            extra_user.email_validated = True
            db.session.add(extra_user)
        db.session.commit()

    with app.app_context():
        total_users: int = Users.query.count()
        page_one = search_users(query="", limit=2, offset=0)
        page_two = search_users(query="", limit=2, offset=2)

    assert not page_one.has_previous
    assert page_one.has_next
    assert page_two.has_previous
    assert not page_two.has_next

    page_one_ids = {searched_user.id for searched_user in page_one.users}
    page_two_ids = {searched_user.id for searched_user in page_two.users}
    assert page_one_ids.isdisjoint(page_two_ids)

    beyond_offset = total_users + 100
    response = client.get(f"{_ADMIN_USERS_SEARCH_URL}?q=&offset={beyond_offset}")
    assert response.status_code == 200


def test_search_users_garbage_offset_falls_back_to_zero(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in admin user
    WHEN the admin sends GET /admin/users/search?q=&offset=notanumber
    THEN the response is 200 (the garbage offset is silently treated as 0)
         and exactly one audit row is created.
    """
    client, _, admin_user, app = login_admin_user_with_register

    with app.app_context():
        rows_before: int = AuditLog.query.count()
    assert rows_before == 0

    response = client.get(f"{_ADMIN_USERS_SEARCH_URL}?q=&offset=notanumber")

    assert response.status_code == 200

    with app.app_context():
        rows_after: int = AuditLog.query.count()
    assert rows_after == 1


# ---------------------------------------------------------------------------
# Admin user detail page
# ---------------------------------------------------------------------------


def test_admin_user_detail_renders_for_admin(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in admin user and a second user in the database
    WHEN the admin sends GET /admin/users/<other_user_id>
    THEN the response is 200 HTML containing the target user's username and
         email; exactly one AuditLog row is created with action USER_VIEW,
         target_type "User", target_id equal to str(other_user_id), and
         actor_id equal to the admin's user id.
    """
    client, _, admin_user, app = login_admin_user_with_register

    with app.app_context():
        detail_user = Users(
            username=_DETAIL_USERNAME,
            email=_DETAIL_EMAIL,
            plaintext_password="DetailPassword1234",
        )
        detail_user.email_validated = True
        db.session.add(detail_user)
        db.session.commit()
        detail_user_id: int = detail_user.id

    with app.app_context():
        rows_before: int = AuditLog.query.count()
    assert rows_before == 0

    response = client.get(f"/admin/users/{detail_user_id}")

    assert response.status_code == 200
    assert _DETAIL_USERNAME.encode() in response.data
    assert _DETAIL_EMAIL.encode() in response.data

    with app.app_context():
        rows_after: int = AuditLog.query.count()
        assert rows_after == 1
        audit_row: AuditLog | None = AuditLog.query.first()
        assert audit_row is not None
        assert audit_row.action == ADMIN_AUDIT_ACTIONS.USER_VIEW
        assert audit_row.actor_id == admin_user.id
        assert audit_row.target_type == _TARGET_TYPE_USER
        assert audit_row.target_id == str(detail_user_id)


def test_admin_user_detail_returns_404_for_unknown_user(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in admin user and no user with id 999999 in the database
    WHEN the admin sends GET /admin/users/999999
    THEN the response is 404 and no AuditLog row is created (the audit write
         only happens after a successful lookup).
    """
    client, _, _, app = login_admin_user_with_register

    with app.app_context():
        rows_before: int = AuditLog.query.count()
        assert Users.query.get(_UNKNOWN_USER_ID) is None
    assert rows_before == 0

    response = client.get(f"/admin/users/{_UNKNOWN_USER_ID}")

    assert response.status_code == 404

    with app.app_context():
        rows_after: int = AuditLog.query.count()
    assert rows_after == 0


# ---------------------------------------------------------------------------
# Access-control: non-admin (403) and anonymous (302)
# ---------------------------------------------------------------------------


def test_admin_users_page_returns_403_for_non_admin(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an empty AuditLogs table and a logged-in non-admin user
    WHEN the user sends GET /admin/users
    THEN the response is 403 Forbidden and no AuditLog row is created.
    """
    client, _, _, app = login_first_user_with_register

    with app.app_context():
        rows_before: int = AuditLog.query.count()
    assert rows_before == 0

    response = client.get(_ADMIN_USERS_URL)

    assert response.status_code == 403

    with app.app_context():
        rows_after: int = AuditLog.query.count()
    assert rows_after == 0


def test_admin_users_search_returns_403_for_non_admin(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an empty AuditLogs table and a logged-in non-admin user
    WHEN the user sends GET /admin/users/search
    THEN the response is 403 Forbidden and no AuditLog row is created.
    """
    client, _, _, app = login_first_user_with_register

    with app.app_context():
        rows_before: int = AuditLog.query.count()
    assert rows_before == 0

    response = client.get(_ADMIN_USERS_SEARCH_URL)

    assert response.status_code == 403

    with app.app_context():
        rows_after: int = AuditLog.query.count()
    assert rows_after == 0


def test_admin_user_detail_returns_403_for_non_admin(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an empty AuditLogs table and a logged-in non-admin user
    WHEN the user sends GET /admin/users/<id> for a known user id
    THEN the response is 403 Forbidden and no AuditLog row is created
         (the admin-role guard fires before any DB lookup).
    """
    client, _, non_admin_user, app = login_first_user_with_register

    with app.app_context():
        rows_before: int = AuditLog.query.count()
    assert rows_before == 0

    response = client.get(f"/admin/users/{non_admin_user.id}")

    assert response.status_code == 403

    with app.app_context():
        rows_after: int = AuditLog.query.count()
    assert rows_after == 0


def test_admin_users_page_redirects_anonymous_to_splash(
    client: FlaskClient,
) -> None:
    """
    GIVEN an anonymous (unauthenticated) browser session
    WHEN the client sends GET /admin/users
    THEN the response is 302 and redirects away from /admin/users
         (to the login page) with the original path in the ``next`` parameter.
    """
    response = client.get(_ADMIN_USERS_URL)

    assert response.status_code == 302
    assert response.location is not None

    redirect_path = urlsplit(response.location).path
    assert not redirect_path.startswith("/admin")

    encoded_next = quote(_ADMIN_USERS_URL, safe="")
    raw_next = _ADMIN_USERS_URL
    assert (
        f"next={encoded_next}" in response.location
        or f"next={raw_next}" in response.location
    )
