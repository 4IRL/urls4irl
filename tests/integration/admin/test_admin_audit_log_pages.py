from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Tuple
from urllib.parse import quote

import pytest
from flask import Flask
from flask.testing import FlaskClient

from backend import db
from backend.admin.audit_service import AuditLogFilters, query_audit_log
from backend.models.audit_log import AuditLog
from backend.models.users import Users
from backend.utils.strings.admin_portal_strs import (
    ADMIN_AUDIT_ACTIONS,
    ADMIN_PORTAL_STRINGS,
)

pytestmark = pytest.mark.admin

_ADMIN_AUDIT_LOG_URL: str = "/admin/audit-log"
_ADMIN_AUDIT_LOG_ROWS_URL: str = "/admin/audit-log/rows"

_AUDIT_LOG_TITLE_BYTES: bytes = ADMIN_PORTAL_STRINGS.AUDIT_LOG_TITLE.encode()
_AUDIT_LOG_RESULTS_ID_BYTES: bytes = b'id="AdminAuditLogResults"'
_AUDIT_LOG_EMPTY_BYTES: bytes = ADMIN_PORTAL_STRINGS.AUDIT_LOG_NO_RESULTS.encode()

# Extra users created in filter tests so actor-filter assertions have distinct actors.
_ACTOR_ALPHA_USERNAME: str = "auditalphauser"
_ACTOR_ALPHA_EMAIL: str = "audit.alpha@example.com"
_ACTOR_BETA_USERNAME: str = "auditbetauser"
_ACTOR_BETA_EMAIL: str = "audit.beta@example.com"

# Action values used in filter-matrix tests — deliberately not ADMIN_AUDIT_ACTIONS
# constants so the strings are independent of the closed set.
_ACTION_USER_VIEW: str = "admin.user.view"
_ACTION_HEALTH_VIEW: str = "admin.health.view"

# target_type values used in exact-match test.
_TARGET_TYPE_USER: str = "User"
_TARGET_TYPE_USERS_PLURAL: str = "Users"

# Pagination constants.
_PAGINATION_SEED_COUNT: int = 5
_PAGINATION_LIMIT: int = 2


def _utc_days_ago(days: int) -> datetime:
    """Return a timezone-aware UTC datetime `days` days before now."""
    return datetime.now(tz=timezone.utc) - timedelta(days=days)


def _seed_audit_row(
    actor_id: int,
    action: str,
    *,
    target_type: str | None = None,
    target_id: str | None = None,
    created_at: datetime | None = None,
) -> AuditLog:
    """Insert and return an AuditLog row, optionally with an explicit timestamp.

    Uses the ORM session directly, following the pattern in
    tests/integration/admin/test_audit_record.py.
    """
    audit_row = AuditLog(
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
    )
    if created_at is not None:
        audit_row.created_at = created_at
    db.session.add(audit_row)
    db.session.commit()
    return audit_row


def _make_user(
    username: str,
    email: str,
    password: str = "TestPassword1234",
) -> Users:
    """Create, add, and return an un-committed Users row."""
    new_user = Users(username=username, email=email, plaintext_password=password)
    new_user.email_validated = True
    db.session.add(new_user)
    return new_user


# ---------------------------------------------------------------------------
# Admin audit-log index page
# ---------------------------------------------------------------------------


def test_admin_audit_log_page_renders_for_admin(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in admin user and an empty AuditLogs table
    WHEN the admin sends GET /admin/audit-log
    THEN the response is 200 HTML that contains the AUDIT_LOG_TITLE text and
         the ``id="AdminAuditLogResults"`` element, and exactly one AuditLog
         row is created with action AUDIT_LOG_VIEW and actor_id equal to the
         admin's user id.
    """
    client, _, admin_user, app = login_admin_user_with_register

    with app.app_context():
        rows_before: int = AuditLog.query.count()
    assert rows_before == 0

    response = client.get(_ADMIN_AUDIT_LOG_URL)

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert _AUDIT_LOG_TITLE_BYTES in response.data
    assert _AUDIT_LOG_RESULTS_ID_BYTES in response.data

    with app.app_context():
        rows_after: int = AuditLog.query.count()
        assert rows_after == 1
        audit_row: AuditLog | None = AuditLog.query.first()
        assert audit_row is not None
        assert audit_row.action == ADMIN_AUDIT_ACTIONS.AUDIT_LOG_VIEW
        assert audit_row.actor_id == admin_user.id


# ---------------------------------------------------------------------------
# Admin audit-log rows fragment — empty state & no audit side-effect
# ---------------------------------------------------------------------------


def test_admin_audit_log_rows_empty_state_and_no_audit_side_effect(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in admin user and an empty AuditLogs table
    WHEN the admin sends GET /admin/audit-log/rows
    THEN the response is 200, the empty-state text is present in the fragment,
         and no AuditLog row is created (the rows fragment is NOT audited).
    """
    client, _, _, app = login_admin_user_with_register

    with app.app_context():
        rows_before: int = AuditLog.query.count()
    assert rows_before == 0

    response = client.get(_ADMIN_AUDIT_LOG_ROWS_URL)

    assert response.status_code == 200
    assert _AUDIT_LOG_EMPTY_BYTES in response.data

    with app.app_context():
        rows_after: int = AuditLog.query.count()
    assert rows_after == 0


# ---------------------------------------------------------------------------
# Filter: action substring
# ---------------------------------------------------------------------------


def test_admin_audit_log_rows_action_filter_narrows_correctly(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in admin user and two seeded audit rows with distinct actions
         — "admin.user.view" and "admin.health.view"
    WHEN the admin sends GET /admin/audit-log/rows?action=user
    THEN the fragment contains "admin.user.view" but not "admin.health.view",
         and the service-level query confirms total_count == 1.
    """
    client, _, admin_user, app = login_admin_user_with_register

    with app.app_context():
        rows_before: int = AuditLog.query.count()
    assert rows_before == 0

    with app.app_context():
        _seed_audit_row(actor_id=admin_user.id, action=_ACTION_USER_VIEW)
        _seed_audit_row(actor_id=admin_user.id, action=_ACTION_HEALTH_VIEW)

    with app.app_context():
        rows_seeded: int = AuditLog.query.count()
    assert rows_seeded == 2

    response = client.get(f"{_ADMIN_AUDIT_LOG_ROWS_URL}?action=user")

    assert response.status_code == 200
    assert _ACTION_USER_VIEW.encode() in response.data
    assert _ACTION_HEALTH_VIEW.encode() not in response.data

    with app.app_context():
        filtered_page = query_audit_log(
            filters=AuditLogFilters(action="user"),
            limit=50,
            offset=0,
        )
    assert filtered_page.total_count == 1
    assert filtered_page.entries[0].action == _ACTION_USER_VIEW


# ---------------------------------------------------------------------------
# Filter: actor by username and by email
# ---------------------------------------------------------------------------


def test_admin_audit_log_rows_actor_filter_by_username(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN two extra users — "auditalphauser" and "auditbetauser" — each
         with one seeded audit row attributed to them
    WHEN GET /admin/audit-log/rows?actor=alpha
    THEN the fragment contains "auditalphauser" but not "auditbetauser", and
         service-level query confirms total_count == 1.
    """
    client, _, _, app = login_admin_user_with_register

    with app.app_context():
        rows_before: int = AuditLog.query.count()
    assert rows_before == 0

    with app.app_context():
        alpha_user = _make_user(_ACTOR_ALPHA_USERNAME, _ACTOR_ALPHA_EMAIL)
        beta_user = _make_user(_ACTOR_BETA_USERNAME, _ACTOR_BETA_EMAIL)
        db.session.flush()
        alpha_user_id: int = alpha_user.id
        beta_user_id: int = beta_user.id
        db.session.commit()

    with app.app_context():
        _seed_audit_row(actor_id=alpha_user_id, action=_ACTION_USER_VIEW)
        _seed_audit_row(actor_id=beta_user_id, action=_ACTION_USER_VIEW)

    with app.app_context():
        rows_seeded: int = AuditLog.query.count()
    assert rows_seeded == 2

    response = client.get(f"{_ADMIN_AUDIT_LOG_ROWS_URL}?actor=alpha")

    assert response.status_code == 200
    assert _ACTOR_ALPHA_USERNAME.encode() in response.data
    assert _ACTOR_BETA_USERNAME.encode() not in response.data

    with app.app_context():
        filtered_page = query_audit_log(
            filters=AuditLogFilters(actor="alpha"),
            limit=50,
            offset=0,
        )
    assert filtered_page.total_count == 1
    assert filtered_page.entries[0].actor_id == alpha_user_id


def test_admin_audit_log_rows_actor_filter_by_email(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN two extra users with distinct emails — "audit.alpha@example.com" and
         "audit.beta@example.com" — each with one seeded audit row
    WHEN GET /admin/audit-log/rows?actor=audit.beta
    THEN the fragment contains "auditbetauser" but not "auditalphauser", and
         service-level total_count == 1.
    """
    client, _, _, app = login_admin_user_with_register

    with app.app_context():
        rows_before: int = AuditLog.query.count()
    assert rows_before == 0

    with app.app_context():
        alpha_user = _make_user(_ACTOR_ALPHA_USERNAME, _ACTOR_ALPHA_EMAIL)
        beta_user = _make_user(_ACTOR_BETA_USERNAME, _ACTOR_BETA_EMAIL)
        db.session.flush()
        alpha_user_id: int = alpha_user.id
        beta_user_id: int = beta_user.id
        db.session.commit()

    with app.app_context():
        _seed_audit_row(actor_id=alpha_user_id, action=_ACTION_USER_VIEW)
        _seed_audit_row(actor_id=beta_user_id, action=_ACTION_USER_VIEW)

    with app.app_context():
        rows_seeded: int = AuditLog.query.count()
    assert rows_seeded == 2

    response = client.get(f"{_ADMIN_AUDIT_LOG_ROWS_URL}?actor=audit.beta")

    assert response.status_code == 200
    assert _ACTOR_BETA_USERNAME.encode() in response.data
    assert _ACTOR_ALPHA_USERNAME.encode() not in response.data

    with app.app_context():
        filtered_page = query_audit_log(
            filters=AuditLogFilters(actor="audit.beta"),
            limit=50,
            offset=0,
        )
    assert filtered_page.total_count == 1
    assert filtered_page.entries[0].actor_id == beta_user_id


# ---------------------------------------------------------------------------
# Filter: target_type exact match
# ---------------------------------------------------------------------------


def test_admin_audit_log_rows_target_type_exact_match(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN one audit row with target_type "User" and one with target_type "Users"
    WHEN GET /admin/audit-log/rows?target_type=User
    THEN only the "User" row is returned — proves the filter is an EXACT match,
         not a substring/ILIKE match; service total_count == 1.
    """
    client, _, admin_user, app = login_admin_user_with_register

    with app.app_context():
        rows_before: int = AuditLog.query.count()
    assert rows_before == 0

    with app.app_context():
        _seed_audit_row(
            actor_id=admin_user.id,
            action=_ACTION_USER_VIEW,
            target_type=_TARGET_TYPE_USER,
        )
        _seed_audit_row(
            actor_id=admin_user.id,
            action=_ACTION_USER_VIEW,
            target_type=_TARGET_TYPE_USERS_PLURAL,
        )

    with app.app_context():
        rows_seeded: int = AuditLog.query.count()
    assert rows_seeded == 2

    response = client.get(
        f"{_ADMIN_AUDIT_LOG_ROWS_URL}?target_type={quote(_TARGET_TYPE_USER, safe='')}"
    )

    assert response.status_code == 200

    with app.app_context():
        filtered_page = query_audit_log(
            filters=AuditLogFilters(target_type=_TARGET_TYPE_USER),
            limit=50,
            offset=0,
        )
    assert filtered_page.total_count == 1
    assert filtered_page.entries[0].target_type == _TARGET_TYPE_USER


# ---------------------------------------------------------------------------
# Filter: date range (since / until)
# ---------------------------------------------------------------------------


def test_admin_audit_log_rows_date_range_filters(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN three audit rows on three distinct calendar days:
         - "oldest_action" two days ago
         - "middle_action" one day ago
         - "newest_action" today (UTC)
    THEN the date-range semantics hold:
         since=middle-day returns middle + newest (2 rows)
         until=middle-day returns middle + oldest (2 rows)
         since=middle-day&until=middle-day returns only middle (1 row)
    """
    client, _, admin_user, app = login_admin_user_with_register

    with app.app_context():
        rows_before: int = AuditLog.query.count()
    assert rows_before == 0

    now_utc = datetime.now(tz=timezone.utc)
    oldest_dt = _utc_days_ago(2)
    middle_dt = _utc_days_ago(1)
    newest_dt = now_utc

    middle_date_str: str = middle_dt.strftime("%Y-%m-%d")

    # Ensure oldest and middle are on genuinely different calendar days; if the
    # test runs right at midnight they could collide — in that case the date
    # window assertions below still hold because oldest+middle share the same
    # date and the since/until filters are inclusive.

    action_oldest: str = "admin.test.oldest"
    action_middle: str = "admin.test.middle"
    action_newest: str = "admin.test.newest"

    with app.app_context():
        _seed_audit_row(
            actor_id=admin_user.id,
            action=action_oldest,
            created_at=oldest_dt,
        )
        _seed_audit_row(
            actor_id=admin_user.id,
            action=action_middle,
            created_at=middle_dt,
        )
        _seed_audit_row(
            actor_id=admin_user.id,
            action=action_newest,
            created_at=newest_dt,
        )

    with app.app_context():
        rows_seeded: int = AuditLog.query.count()
    assert rows_seeded == 3

    # since=middle: should return middle + newest
    with app.app_context():
        since_middle_page = query_audit_log(
            filters=AuditLogFilters(since=middle_date_str),
            limit=50,
            offset=0,
        )
    since_middle_actions = {entry.action for entry in since_middle_page.entries}
    assert action_middle in since_middle_actions
    assert action_newest in since_middle_actions
    assert action_oldest not in since_middle_actions

    # until=middle: should return oldest + middle
    with app.app_context():
        until_middle_page = query_audit_log(
            filters=AuditLogFilters(until=middle_date_str),
            limit=50,
            offset=0,
        )
    until_middle_actions = {entry.action for entry in until_middle_page.entries}
    assert action_oldest in until_middle_actions
    assert action_middle in until_middle_actions
    assert action_newest not in until_middle_actions

    # since=until=middle: should return only middle
    with app.app_context():
        exact_day_page = query_audit_log(
            filters=AuditLogFilters(since=middle_date_str, until=middle_date_str),
            limit=50,
            offset=0,
        )
    exact_day_actions = {entry.action for entry in exact_day_page.entries}
    assert action_middle in exact_day_actions
    assert action_oldest not in exact_day_actions
    assert action_newest not in exact_day_actions

    # Confirm the HTTP fragment respects since= with a real request.
    response = client.get(f"{_ADMIN_AUDIT_LOG_ROWS_URL}?since={middle_date_str}")
    assert response.status_code == 200
    assert action_middle.encode() in response.data
    assert action_oldest.encode() not in response.data


# ---------------------------------------------------------------------------
# Filter: combined filters narrow conjunctively
# ---------------------------------------------------------------------------


def test_admin_audit_log_rows_combined_filters_narrow_conjunctively(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN two audit rows for two different actors with different actions:
         alpha-actor → "admin.user.view", beta-actor → "admin.health.view"
    WHEN GET /admin/audit-log/rows?actor=alpha&action=user
    THEN only the alpha-actor user-view row is returned (total_count == 1).
    """
    client, _, _, app = login_admin_user_with_register

    with app.app_context():
        rows_before: int = AuditLog.query.count()
    assert rows_before == 0

    with app.app_context():
        alpha_user = _make_user(_ACTOR_ALPHA_USERNAME, _ACTOR_ALPHA_EMAIL)
        beta_user = _make_user(_ACTOR_BETA_USERNAME, _ACTOR_BETA_EMAIL)
        db.session.flush()
        alpha_user_id: int = alpha_user.id
        beta_user_id: int = beta_user.id
        db.session.commit()

    with app.app_context():
        _seed_audit_row(actor_id=alpha_user_id, action=_ACTION_USER_VIEW)
        _seed_audit_row(actor_id=beta_user_id, action=_ACTION_HEALTH_VIEW)

    with app.app_context():
        rows_seeded: int = AuditLog.query.count()
    assert rows_seeded == 2

    response = client.get(f"{_ADMIN_AUDIT_LOG_ROWS_URL}?actor=alpha&action=user")

    assert response.status_code == 200
    assert _ACTOR_ALPHA_USERNAME.encode() in response.data
    assert _ACTOR_BETA_USERNAME.encode() not in response.data

    with app.app_context():
        combined_page = query_audit_log(
            filters=AuditLogFilters(actor="alpha", action="user"),
            limit=50,
            offset=0,
        )
    assert combined_page.total_count == 1
    assert combined_page.entries[0].actor_id == alpha_user_id
    assert combined_page.entries[0].action == _ACTION_USER_VIEW


# ---------------------------------------------------------------------------
# Pagination: service-level
# ---------------------------------------------------------------------------


def test_admin_audit_log_pagination_pages_are_disjoint(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN five seeded audit rows and a page limit of 2
    WHEN query_audit_log() is called for page 1 (offset=0), page 2 (offset=2),
         and page 3 (offset=4)
    THEN pages 1 and 2 are disjoint, page 1 has has_next=True and
         has_previous=False, page 2 has both flags True, page 3 has
         has_next=False and has_previous=True, and offsets compute correctly.
    """
    _, _, admin_user, app = login_admin_user_with_register

    with app.app_context():
        rows_before: int = AuditLog.query.count()
    assert rows_before == 0

    with app.app_context():
        for row_index in range(_PAGINATION_SEED_COUNT):
            _seed_audit_row(
                actor_id=admin_user.id,
                action=f"admin.test.page{row_index}",
            )

    with app.app_context():
        rows_seeded: int = AuditLog.query.count()
    assert rows_seeded == _PAGINATION_SEED_COUNT

    with app.app_context():
        page_one = query_audit_log(
            filters=AuditLogFilters(),
            limit=_PAGINATION_LIMIT,
            offset=0,
        )
        page_two = query_audit_log(
            filters=AuditLogFilters(),
            limit=_PAGINATION_LIMIT,
            offset=_PAGINATION_LIMIT,
        )
        page_three = query_audit_log(
            filters=AuditLogFilters(),
            limit=_PAGINATION_LIMIT,
            offset=_PAGINATION_LIMIT * 2,
        )

    # page 1: first page
    assert not page_one.has_previous
    assert page_one.has_next
    assert page_one.previous_offset == 0
    assert page_one.next_offset == _PAGINATION_LIMIT

    # page 2: middle page
    assert page_two.has_previous
    assert page_two.has_next
    assert page_two.previous_offset == 0
    assert page_two.next_offset == _PAGINATION_LIMIT * 2

    # page 3: last page (only 1 row: index 4)
    assert page_three.has_previous
    assert not page_three.has_next

    # Disjointness
    page_one_ids = {entry.id for entry in page_one.entries}
    page_two_ids = {entry.id for entry in page_two.entries}
    assert page_one_ids.isdisjoint(page_two_ids)


def test_admin_audit_log_rows_empty_result_set_renders_cleanly(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an empty AuditLogs table
    WHEN GET /admin/audit-log/rows?offset=9999
    THEN the response is 200 and the empty-state element is present.
    """
    client, _, _, app = login_admin_user_with_register

    with app.app_context():
        rows_before: int = AuditLog.query.count()
    assert rows_before == 0

    response = client.get(f"{_ADMIN_AUDIT_LOG_ROWS_URL}?offset=9999")

    assert response.status_code == 200
    assert _AUDIT_LOG_EMPTY_BYTES in response.data


# ---------------------------------------------------------------------------
# Ordering: newest first
# ---------------------------------------------------------------------------


def test_admin_audit_log_rows_ordered_newest_first(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN three audit rows seeded with explicit created_at values spanning
         three distinct moments
    WHEN query_audit_log() is called with no filters
    THEN the entries are returned in descending created_at order (newest first),
         confirmed by the explicit sequence of action strings.
    """
    _, _, admin_user, app = login_admin_user_with_register

    with app.app_context():
        rows_before: int = AuditLog.query.count()
    assert rows_before == 0

    action_first_created: str = "admin.test.order.first"
    action_second_created: str = "admin.test.order.second"
    action_third_created: str = "admin.test.order.third"

    base_moment = datetime.now(tz=timezone.utc) - timedelta(hours=3)

    with app.app_context():
        _seed_audit_row(
            actor_id=admin_user.id,
            action=action_first_created,
            created_at=base_moment,
        )
        _seed_audit_row(
            actor_id=admin_user.id,
            action=action_second_created,
            created_at=base_moment + timedelta(hours=1),
        )
        _seed_audit_row(
            actor_id=admin_user.id,
            action=action_third_created,
            created_at=base_moment + timedelta(hours=2),
        )

    with app.app_context():
        result_page = query_audit_log(
            filters=AuditLogFilters(),
            limit=50,
            offset=0,
        )

    ordered_actions = [entry.action for entry in result_page.entries]
    assert ordered_actions == [
        action_third_created,
        action_second_created,
        action_first_created,
    ]


# ---------------------------------------------------------------------------
# Access-control: non-admin (403) and anonymous (302)
# ---------------------------------------------------------------------------


def test_admin_audit_log_page_returns_403_for_non_admin(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an empty AuditLogs table and a logged-in non-admin user
    WHEN the user sends GET /admin/audit-log
    THEN the response is 403 Forbidden and no AuditLog row is created.
    """
    client, _, _, app = login_first_user_with_register

    with app.app_context():
        rows_before: int = AuditLog.query.count()
    assert rows_before == 0

    response = client.get(_ADMIN_AUDIT_LOG_URL)

    assert response.status_code == 403

    with app.app_context():
        rows_after: int = AuditLog.query.count()
    assert rows_after == 0


def test_admin_audit_log_rows_returns_403_for_non_admin(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an empty AuditLogs table and a logged-in non-admin user
    WHEN the user sends GET /admin/audit-log/rows
    THEN the response is 403 Forbidden and no AuditLog row is created.
    """
    client, _, _, app = login_first_user_with_register

    with app.app_context():
        rows_before: int = AuditLog.query.count()
    assert rows_before == 0

    response = client.get(_ADMIN_AUDIT_LOG_ROWS_URL)

    assert response.status_code == 403

    with app.app_context():
        rows_after: int = AuditLog.query.count()
    assert rows_after == 0


def test_admin_audit_log_page_redirects_anonymous(
    client: FlaskClient,
) -> None:
    """
    GIVEN an anonymous (unauthenticated) browser session
    WHEN the client sends GET /admin/audit-log
    THEN the response is 302 and redirects away from /admin/audit-log
         (to the login page) with the original path in the ``next`` parameter.
    """
    response = client.get(_ADMIN_AUDIT_LOG_URL)

    assert response.status_code == 302
    assert response.location is not None

    encoded_next = quote(_ADMIN_AUDIT_LOG_URL, safe="")
    raw_next = _ADMIN_AUDIT_LOG_URL
    assert (
        f"next={encoded_next}" in response.location
        or f"next={raw_next}" in response.location
    )
