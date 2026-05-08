import pytest

from backend.extensions.metrics.writer import record_event
from backend.metrics.events import EventName

pytestmark = pytest.mark.unit


def test_record_event_is_callable_and_returns_none():
    """The Phase 1 stub is callable with just an EventName and returns None."""
    assert record_event(EventName.API_HIT) is None


def test_record_event_accepts_all_documented_kwargs():
    """All documented keyword arguments are accepted without raising."""
    result = record_event(
        EventName.API_HIT,
        endpoint="/foo",
        method="GET",
        status_code=200,
        dimensions={"x": 1},
    )
    assert result is None
