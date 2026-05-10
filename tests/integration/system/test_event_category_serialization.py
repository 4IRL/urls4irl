from __future__ import annotations

import pytest
from flask import Flask
from sqlalchemy import text

from backend import db
from backend.metrics.events import EventCategory
from backend.models.event_registry import Event_Registry
from tests.integration.system.conftest import reset_postgres_enum_to_lowercase_values

pytestmark = pytest.mark.cli


def _reset_enum_via_raw_connection() -> None:
    """Adapter that drives the shared psycopg2-based helper from the
    SQLAlchemy engine, then asserts the enum was rebuilt with the
    expected lowercase values."""
    raw_conn = db.engine.raw_connection()
    try:
        reset_postgres_enum_to_lowercase_values(raw_conn)
    finally:
        raw_conn.close()

    enum_values = (
        db.session.execute(
            text(
                "SELECT e.enumlabel FROM pg_type t JOIN pg_enum e"
                " ON e.enumtypid = t.oid WHERE t.typname = 'event_category_enum'"
                " ORDER BY e.enumsortorder"
            )
        )
        .scalars()
        .all()
    )
    assert enum_values == ["api", "domain", "ui"]


def test_event_category_persists_to_postgres(app: Flask):
    """
    GIVEN the Postgres `event_category_enum` type contains only the lowercase
        StrEnum VALUES ('api'/'domain'/'ui'), matching the production migration
    WHEN one EventRegistry row is inserted via the SQLAlchemy model for each
        EventCategory member and `db.session.flush()` is called
    THEN every member round-trips: the flush succeeds and a re-query returns
        each row with the original EventCategory member.

    Regression pin for the EventCategory Postgres enum serialization bug:
    SQLAlchemy was serializing the StrEnum by NAME ("API"/"DOMAIN"/"UI") while
    Postgres only accepted the lowercase VALUES, so every flush rolled back
    with `DataError: invalid input value for enum event_category_enum: "API"`.
    """
    _reset_enum_via_raw_connection()

    rows = [
        Event_Registry(
            name=f"_regression_{category.value}",
            category=category,
            description="regression-pin",
        )
        for category in EventCategory
    ]
    inserted_names = [row.name for row in rows]

    try:
        db.session.add_all(rows)
        db.session.flush()

        queried_rows = Event_Registry.query.filter(
            Event_Registry.name.in_(inserted_names)
        ).all()
        assert len(queried_rows) == 3
        assert {row.category for row in queried_rows} == set(EventCategory)
    finally:
        # Reset the session in case a flush failure left it in a
        # rolled-back state, so the cleanup DELETE can proceed cleanly.
        db.session.rollback()
        Event_Registry.query.filter(Event_Registry.name.in_(inserted_names)).delete(
            synchronize_session=False
        )
        db.session.flush()
