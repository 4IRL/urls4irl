from __future__ import annotations

import pytest
from flask import Flask
from sqlalchemy import text

from backend import db
from backend.metrics.events import EventCategory
from backend.models.event_registry import Event_Registry

pytestmark = pytest.mark.cli


def _reset_postgres_enum_to_lowercase_values() -> None:
    """Force the Postgres `event_category_enum` type to contain only the
    lowercase StrEnum VALUES — matching the production migration's
    `postgresql.ENUM("api", "domain", "ui", name="event_category_enum")`.

    `db.create_all()` (used in test setup) generates the enum from the
    SQLAlchemy column definition. Without `values_callable`, SQLAlchemy
    emits the enum using the member NAMES (uppercase), so the test DB's
    enum disagrees with production. We rebuild the enum here so this test
    reproduces the exact mismatch production hits.
    """
    db.session.execute(
        text('ALTER TABLE "EventRegistry" ALTER COLUMN "category" TYPE TEXT')
    )
    db.session.execute(text("DROP TYPE IF EXISTS event_category_enum"))
    db.session.execute(
        text("CREATE TYPE event_category_enum AS ENUM ('api', 'domain', 'ui')")
    )
    db.session.execute(
        text(
            'ALTER TABLE "EventRegistry" ALTER COLUMN "category"'
            " TYPE event_category_enum USING category::event_category_enum"
        )
    )
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
    _reset_postgres_enum_to_lowercase_values()

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
