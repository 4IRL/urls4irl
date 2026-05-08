from datetime import datetime, timezone

import pytest
from flask import Flask
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from backend import db
from backend.metrics.events import EventCategory, EventName
from backend.models.anonymous_metrics import Anonymous_Metrics
from backend.models.event_registry import Event_Registry

pytestmark = pytest.mark.cli


def _seed_event_registry_row(
    name: str, category: EventCategory, description: str
) -> None:
    """Insert a single Event_Registry row and flush so subsequent inserts can FK to it."""
    db.session.add(
        Event_Registry(name=name, category=category, description=description)
    )
    db.session.flush()


def test_event_registry_table_columns(app: Flask):
    """
    GIVEN the EventRegistry table created by the metrics-tables migration
    WHEN the table columns are inspected
    THEN ensure all four expected columns exist with correct broad SQL types
    """
    with app.app_context():
        inspector = inspect(db.engine)
        columns_by_name = {
            column["name"]: column
            for column in inspector.get_columns(Event_Registry.__tablename__)
        }

        assert set(columns_by_name.keys()) == {
            "name",
            "category",
            "description",
            "addedAt",
        }

        # Postgres VARCHAR(N) is reported as VARCHAR by the inspector
        assert "VARCHAR" in str(columns_by_name["name"]["type"]).upper()
        assert "VARCHAR" in str(columns_by_name["description"]["type"]).upper()
        # Postgres reflects the enum as ENUM with its named type; check the
        # type's class name and its ``name`` attribute for the registered
        # enum-type name (SQLAlchemy's str() on the type returns the
        # underlying VARCHAR(N), so check the type object itself instead).
        category_type = columns_by_name["category"]["type"]
        assert type(category_type).__name__.upper() == "ENUM"
        assert getattr(category_type, "name", "") == "event_category_enum"
        # Timezone-aware timestamp
        added_at_type_str = str(columns_by_name["addedAt"]["type"]).upper()
        assert "TIMESTAMP" in added_at_type_str or "DATETIME" in added_at_type_str


def test_anonymous_metrics_jsonb_default_is_empty_dict(app: Flask):
    """
    GIVEN the AnonymousMetrics table with a JSONB ``dimensions`` column
    WHEN a row is inserted without specifying ``dimensions``
    THEN ensure the column round-trips as an empty dict
    """
    with app.app_context():
        _seed_event_registry_row(EventName.API_HIT.value, EventCategory.API, "test")

        bucket_start = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        metric_row = Anonymous_Metrics(
            event_name=EventName.API_HIT.value,
            bucket_start=bucket_start,
            count=1,
        )
        db.session.add(metric_row)
        db.session.commit()

        reloaded = Anonymous_Metrics.query.filter_by(
            event_name=EventName.API_HIT.value
        ).one()
        assert reloaded.dimensions == {}


def test_anonymous_metrics_unique_constraint_is_jsonb_key_order_insensitive(app: Flask):
    """
    GIVEN two AnonymousMetrics rows with same bucket_start, event_name, and
        logically-equal dimensions but different key insertion order
    WHEN the second insert is attempted
    THEN ensure Postgres rejects it via the unique_metric_bucket constraint,
        confirming JSONB equality is key-order-insensitive
    """
    with app.app_context():
        _seed_event_registry_row(EventName.API_HIT.value, EventCategory.API, "test")

        bucket_start = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        first_row = Anonymous_Metrics(
            event_name=EventName.API_HIT.value,
            bucket_start=bucket_start,
            dimensions={"a": 1, "b": 2},
            count=1,
        )
        db.session.add(first_row)
        db.session.commit()

        second_row = Anonymous_Metrics(
            event_name=EventName.API_HIT.value,
            bucket_start=bucket_start,
            dimensions={"b": 2, "a": 1},
            count=1,
        )
        db.session.add(second_row)
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_anonymous_metrics_rejects_unregistered_event_name(app: Flask):
    """
    GIVEN an AnonymousMetrics row referencing an event_name not present in
        EventRegistry
    WHEN the row insert is attempted
    THEN ensure the foreign-key constraint rejects the insert
    """
    with app.app_context():
        _seed_event_registry_row(EventName.API_HIT.value, EventCategory.API, "test")

        bucket_start = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        unregistered_row = Anonymous_Metrics(
            event_name="not_registered",
            bucket_start=bucket_start,
            dimensions={},
            count=1,
        )
        db.session.add(unregistered_row)
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_event_category_enum_round_trip(app: Flask):
    """
    GIVEN one EventRegistry row per EventCategory enum value
    WHEN each row is flushed and reloaded from the database
    THEN ensure ``category`` round-trips back to the same EventCategory member
    """
    with app.app_context():
        category_to_row_name = {
            EventCategory.API: "round_trip_api",
            EventCategory.DOMAIN: "round_trip_domain",
            EventCategory.UI: "round_trip_ui",
        }
        for category, row_name in category_to_row_name.items():
            db.session.add(
                Event_Registry(
                    name=row_name, category=category, description="round-trip"
                )
            )
        db.session.flush()

        for category, row_name in category_to_row_name.items():
            row = Event_Registry.query.filter_by(name=row_name).one()
            db.session.refresh(row)
            assert row.category == category
