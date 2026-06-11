import pytest

from backend.metrics.events import (
    EVENT_CATEGORY,
    EVENT_DESCRIPTIONS,
    EventCategory,
    EventName,
)

pytestmark = pytest.mark.unit


def test_event_category_has_three_values():
    """EventCategory has exactly three members and lowercase string values."""
    assert set(EventCategory) == {
        EventCategory.API,
        EventCategory.DOMAIN,
        EventCategory.UI,
    }
    for category in EventCategory:
        assert category.value == category.name.lower()


def test_event_name_value_format():
    """Every EventName value is the lowercase form of its member name."""
    for member in EventName:
        assert member.value == member.name.lower()


def test_every_event_has_category():
    """Every EventName member is mapped to an EventCategory in EVENT_CATEGORY."""
    for member in EventName:
        assert member in EVENT_CATEGORY
        assert isinstance(EVENT_CATEGORY[member], EventCategory)


def test_every_event_has_description():
    """Every EventName member has a non-empty description in EVENT_DESCRIPTIONS."""
    for member in EventName:
        assert member in EVENT_DESCRIPTIONS
        assert EVENT_DESCRIPTIONS[member]


def test_api_category_contains_only_server_emitted_api_events():
    """The API category contains the two server-emitted middleware/route counters.

    `API_HIT` is auto-emitted by middleware on every request; `API_METRICS_INGEST_BATCH`
    is explicitly emitted by the `POST /api/metrics` ingest route per batch attempt.
    No other event belongs in the API category — UI and domain events have their own
    categories and emission paths.
    """
    api_members = {
        member
        for member, category in EVENT_CATEGORY.items()
        if category is EventCategory.API
    }
    assert api_members == {
        EventName.API_HIT,
        EventName.API_METRICS_INGEST_BATCH,
    }


def test_ui_events_have_ui_prefix():
    """Every UI-categorized event's member name starts with 'UI_'."""
    for member, category in EVENT_CATEGORY.items():
        if category is EventCategory.UI:
            assert member.name.startswith("UI_")
