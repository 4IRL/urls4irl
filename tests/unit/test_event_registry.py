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


def test_event_name_count_matches_master_plan():
    """EventName has 47 members: 1 API + 11 domain + 35 UI."""
    assert len(EventName) == 47


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


def test_api_category_contains_only_api_hit():
    """The API category contains exactly one event: API_HIT."""
    api_members = {
        member
        for member, category in EVENT_CATEGORY.items()
        if category is EventCategory.API
    }
    assert api_members == {EventName.API_HIT}


def test_domain_category_size():
    """The DOMAIN category contains exactly 11 events."""
    domain_members = {
        member
        for member, category in EVENT_CATEGORY.items()
        if category is EventCategory.DOMAIN
    }
    assert len(domain_members) == 11


def test_ui_category_size():
    """The UI category contains exactly 35 events."""
    ui_members = {
        member
        for member, category in EVENT_CATEGORY.items()
        if category is EventCategory.UI
    }
    assert len(ui_members) == 35


def test_ui_events_have_ui_prefix():
    """Every UI-categorized event's member name starts with 'UI_'."""
    for member, category in EVENT_CATEGORY.items():
        if category is EventCategory.UI:
            assert member.name.startswith("UI_")
