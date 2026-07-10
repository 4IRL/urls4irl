from __future__ import annotations

import datetime
import decimal
from typing import Tuple

import pytest
from flask import Flask

from backend import db
from backend.admin import db_browser_service
from backend.admin.db_browser_service import (
    RowDetail,
    TablePage,
    TableSummary,
    format_cell_value,
)
from backend.metrics.events import EventCategory
from backend.models.api_refresh_tokens import ApiRefreshTokens
from backend.models.event_registry import Event_Registry
from backend.models.users import User_Role, Users
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utubs import Utubs

pytestmark = pytest.mark.admin

_USERS_TABLE: str = "Users"
_API_REFRESH_TOKENS_TABLE: str = "ApiRefreshTokens"
_UTUB_MEMBERS_TABLE: str = "UtubMembers"
_EVENT_REGISTRY_TABLE: str = "EventRegistry"

_PASSWORD_COLUMN_KEY: str = "password"
_TOKEN_COLUMN_KEY: str = "token"

_SEEDED_USERNAME_BASE: str = "browseruser"
_SEEDED_EMAIL_DOMAIN: str = "@browser.example.com"
_SEEDED_PASSWORD: str = "SuperSecret123!"

_EVENT_REGISTRY_NAME: str = "db_browser_service_test_event"


def _seed_users(count: int) -> list[Users]:
    """Insert ``count`` validated users (ids assigned sequentially from 1).

    Returns the persisted models so tests can assert against their PKs.
    """
    seeded_users: list[Users] = []
    for index in range(count):
        new_user = Users(
            username=f"{_SEEDED_USERNAME_BASE}{index}",
            email=f"{_SEEDED_USERNAME_BASE}{index}{_SEEDED_EMAIL_DOMAIN}",
            plaintext_password=_SEEDED_PASSWORD,
        )
        new_user.email_validated = True
        db.session.add(new_user)
        seeded_users.append(new_user)
    db.session.commit()
    return seeded_users


def _seed_refresh_token(user_id: int) -> ApiRefreshTokens:
    """Insert one refresh-token row owned by ``user_id``."""
    refresh_token = ApiRefreshTokens(
        user_id=user_id,
        token="a-secret-refresh-token-value",
        family_id="family-abc",
        expires_at=datetime.datetime(2099, 1, 1, tzinfo=datetime.timezone.utc),
    )
    db.session.add(refresh_token)
    db.session.commit()
    return refresh_token


def _seed_utub_member(user_id: int) -> Utub_Members:
    """Insert a Utub owned by ``user_id`` and add ``user_id`` as a member."""
    new_utub = Utubs(
        name="Browser Test UTub",
        utub_creator=user_id,
        utub_description="",
    )
    db.session.add(new_utub)
    db.session.commit()
    utub_member = Utub_Members(
        utub_id=new_utub.id,
        user_id=user_id,
        member_role=Member_Role.CREATOR,
    )
    db.session.add(utub_member)
    db.session.commit()
    return utub_member


def _seed_event_registry_row() -> Event_Registry:
    """Insert one EventRegistry row (String primary key = ``name``)."""
    event_row = Event_Registry(
        name=_EVENT_REGISTRY_NAME,
        category=EventCategory.DOMAIN,
        description="Seeded for the DB-browser service string-PK test.",
    )
    db.session.add(event_row)
    db.session.commit()
    return event_row


# ---------------------------------------------------------------------------
# format_cell_value
# ---------------------------------------------------------------------------


def test_format_cell_value_none_returns_placeholder() -> None:
    assert format_cell_value(None) == "—"


def test_format_cell_value_dict_returns_json_string() -> None:
    formatted = format_cell_value({"device": "mobile", "count": 3})
    assert formatted == '{"device": "mobile", "count": 3}'


def test_format_cell_value_list_returns_json_string() -> None:
    assert format_cell_value([1, 2, 3]) == "[1, 2, 3]"


def test_format_cell_value_tz_aware_datetime_uses_space_separated_iso() -> None:
    moment = datetime.datetime(2026, 7, 1, 8, 30, 0, tzinfo=datetime.timezone.utc)
    assert format_cell_value(moment) == "2026-07-01 08:30:00+00:00"


def test_format_cell_value_date_uses_iso() -> None:
    assert format_cell_value(datetime.date(2026, 7, 1)) == "2026-07-01"


def test_format_cell_value_decimal_preserves_trailing_zero() -> None:
    assert format_cell_value(decimal.Decimal("5.20")) == "5.20"


def test_format_cell_value_enum_uses_value() -> None:
    assert format_cell_value(User_Role.ADMIN) == User_Role.ADMIN.value


def test_format_cell_value_truncates_past_limit() -> None:
    assert format_cell_value("abcdef", truncate=3) == "abc…"


def test_format_cell_value_leaves_short_string_unchanged() -> None:
    assert format_cell_value("ab", truncate=3) == "ab"


# ---------------------------------------------------------------------------
# list_tables
# ---------------------------------------------------------------------------


def test_list_tables_covers_every_mapped_model(
    register_first_user: Tuple[dict, Users],
    app: Flask,
) -> None:
    """
    GIVEN one seeded user
    WHEN list_tables() is called
    THEN every mapped model's __tablename__ appears exactly once, and the
         Users summary reports the seeded row count.
    """
    with app.app_context():
        summaries = db_browser_service.list_tables()

        returned_table_names = {summary.table_name for summary in summaries}
        expected_table_names = {
            mapper.class_.__tablename__ for mapper in db.Model.registry.mappers
        }
        assert returned_table_names == expected_table_names

        users_summary = next(
            summary for summary in summaries if summary.table_name == _USERS_TABLE
        )
        assert isinstance(users_summary, TableSummary)
        assert users_summary.row_count == 1


# ---------------------------------------------------------------------------
# get_table_page
# ---------------------------------------------------------------------------


def test_get_table_page_users_masks_password_column(app: Flask) -> None:
    with app.app_context():
        _seed_users(1)

        table_page = db_browser_service.get_table_page(table_name=_USERS_TABLE)

        assert isinstance(table_page, TablePage)
        assert _PASSWORD_COLUMN_KEY not in table_page.column_keys
        assert "username" in table_page.column_keys
        assert "email" in table_page.column_keys


def test_get_table_page_unknown_table_returns_none(app: Flask) -> None:
    with app.app_context():
        assert db_browser_service.get_table_page(table_name="NotATable") is None


def test_get_table_page_paginates_by_offset_and_limit(app: Flask) -> None:
    with app.app_context():
        _seed_users(4)

        first_page = db_browser_service.get_table_page(
            table_name=_USERS_TABLE, limit=2, offset=0
        )
        second_page = db_browser_service.get_table_page(
            table_name=_USERS_TABLE, limit=2, offset=2
        )

        assert first_page is not None and second_page is not None
        assert first_page.total_count == 4
        assert len(first_page.rows) == 2
        assert len(second_page.rows) == 2

        first_segments = {row.pk_segment for row in first_page.rows}
        second_segments = {row.pk_segment for row in second_page.rows}
        assert first_segments.isdisjoint(second_segments)

        assert first_page.has_next
        assert not first_page.has_previous
        assert not second_page.has_next
        assert second_page.has_previous
        assert second_page.previous_offset == 0
        assert first_page.next_offset == 2


def test_get_table_page_refresh_tokens_masks_token_column(
    register_first_user: Tuple[dict, Users],
    app: Flask,
) -> None:
    with app.app_context():
        _seed_refresh_token(user_id=1)

        table_page = db_browser_service.get_table_page(
            table_name=_API_REFRESH_TOKENS_TABLE
        )

        assert table_page is not None
        assert table_page.total_count == 1
        assert _TOKEN_COLUMN_KEY not in table_page.column_keys


# ---------------------------------------------------------------------------
# get_row_detail
# ---------------------------------------------------------------------------


def test_get_row_detail_users_masks_password(
    register_first_user: Tuple[dict, Users],
    app: Flask,
) -> None:
    with app.app_context():
        row_detail = db_browser_service.get_row_detail(
            table_name=_USERS_TABLE, raw_pk="1"
        )

        assert isinstance(row_detail, RowDetail)
        field_keys = {field.key for field in row_detail.fields}
        assert _PASSWORD_COLUMN_KEY not in field_keys
        assert "username" in field_keys


def test_get_row_detail_unknown_pk_returns_none(
    register_first_user: Tuple[dict, Users],
    app: Flask,
) -> None:
    with app.app_context():
        assert (
            db_browser_service.get_row_detail(table_name=_USERS_TABLE, raw_pk="999999")
            is None
        )


def test_get_row_detail_non_numeric_pk_for_int_table_returns_none(
    register_first_user: Tuple[dict, Users],
    app: Flask,
) -> None:
    with app.app_context():
        assert (
            db_browser_service.get_row_detail(
                table_name=_USERS_TABLE, raw_pk="not-a-number"
            )
            is None
        )


# ---------------------------------------------------------------------------
# Composite and string primary keys
# ---------------------------------------------------------------------------


def test_composite_pk_segment_and_row_detail_resolve(
    register_first_user: Tuple[dict, Users],
    app: Flask,
) -> None:
    with app.app_context():
        utub_member = _seed_utub_member(user_id=1)
        expected_segment = f"{utub_member.utub_id},{utub_member.user_id}"

        assert (
            db_browser_service._row_pk_segment(Utub_Members, utub_member)
            == expected_segment
        )

        row_detail = db_browser_service.get_row_detail(
            table_name=_UTUB_MEMBERS_TABLE, raw_pk=expected_segment
        )
        assert isinstance(row_detail, RowDetail)
        assert row_detail.pk_segment == expected_segment


def test_string_pk_row_detail_resolves(app: Flask) -> None:
    with app.app_context():
        _seed_event_registry_row()

        row_detail = db_browser_service.get_row_detail(
            table_name=_EVENT_REGISTRY_TABLE, raw_pk=_EVENT_REGISTRY_NAME
        )
        assert isinstance(row_detail, RowDetail)
        name_field = next(field for field in row_detail.fields if field.key == "name")
        assert name_field.value == _EVENT_REGISTRY_NAME
