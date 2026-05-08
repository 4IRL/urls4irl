from __future__ import annotations

import pytest
from flask import Flask

from backend import db
from backend.extensions.metrics.registry_sync import sync_event_registry
from backend.metrics.events import (
    EVENT_CATEGORY,
    EVENT_DESCRIPTIONS,
    EventCategory,
    EventName,
)
from backend.models.event_registry import Event_Registry

pytestmark = pytest.mark.cli


def test_sync_event_registry_populates_all_enum_members(app: Flask):
    """
    GIVEN an empty EventRegistry table
    WHEN sync_event_registry() is invoked
    THEN ensure every EventName member is inserted with the canonical
        category and description from the Python source-of-truth dicts
    """
    sync_event_registry(app)

    rows_by_name = {row.name: row for row in Event_Registry.query.all()}
    for member in EventName:
        assert member.value in rows_by_name
        row = rows_by_name[member.value]
        assert row.category == EVENT_CATEGORY[member]
        assert row.description == EVENT_DESCRIPTIONS[member]


def test_sync_event_registry_is_idempotent(app: Flask):
    """
    GIVEN sync_event_registry() has already populated EventRegistry once
    WHEN it is invoked a second time within the same test
    THEN ensure the row count remains equal to the enum member count
        (no duplicate inserts, no row removals)
    """
    sync_event_registry(app)
    sync_event_registry(app)

    assert Event_Registry.query.count() == len(EventName)


def test_sync_event_registry_preserves_retired_rows(app: Flask):
    """
    GIVEN EventRegistry contains a manually-inserted retired event row
        not present in the EventName enum
    WHEN sync_event_registry() is invoked
    THEN ensure the retired row is preserved (sync never deletes) and the
        total row count is len(EventName) + 1
    """
    db.session.add(
        Event_Registry(
            name="retired_event",
            category=EventCategory.DOMAIN,
            description="retired",
        )
    )
    db.session.commit()

    sync_event_registry(app)

    assert Event_Registry.query.count() == len(EventName) + 1
    retired_row = Event_Registry.query.filter_by(name="retired_event").one()
    assert retired_row.description == "retired"


def test_sync_event_registry_updates_drifted_descriptions(app: Flask):
    """
    GIVEN an EventRegistry row whose description has drifted from the
        Python source-of-truth value
    WHEN sync_event_registry() is invoked
    THEN ensure the row's description is updated to the canonical value
    """
    db.session.add(
        Event_Registry(
            name=EventName.API_HIT.value,
            category=EVENT_CATEGORY[EventName.API_HIT],
            description="OLD",
        )
    )
    db.session.commit()

    sync_event_registry(app)

    row = Event_Registry.query.filter_by(name=EventName.API_HIT.value).one()
    assert row.description == EVENT_DESCRIPTIONS[EventName.API_HIT]


def test_sync_event_registry_updates_drifted_category(app: Flask):
    """
    GIVEN an EventRegistry row whose category has drifted from the
        Python source-of-truth value
    WHEN sync_event_registry() is invoked
    THEN ensure the row's category is updated to the canonical value
    """
    db.session.add(
        Event_Registry(
            name=EventName.API_HIT.value,
            category=EventCategory.DOMAIN,
            description=EVENT_DESCRIPTIONS[EventName.API_HIT],
        )
    )
    db.session.commit()

    sync_event_registry(app)

    row = Event_Registry.query.filter_by(name=EventName.API_HIT.value).one()
    assert row.category == EventCategory.API
