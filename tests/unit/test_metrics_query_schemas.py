from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from backend.metrics.events import EventCategory, EventName
from backend.schemas.metrics import (
    SummaryCategoryCount,
    SummaryResponseSchema,
    TimeseriesBucketSchema,
    TimeseriesResponseSchema,
    TopEventRow,
    TopEventsResponseSchema,
)
from backend.schemas.requests.metrics import (
    SummaryQuerySchema,
    TimeseriesQuerySchema,
    TopEventsQuerySchema,
)

pytestmark = pytest.mark.unit


# -------------------------- TopEventsQuerySchema ---------------------------


def test_top_events_query_happy_path_with_window_only():
    """`{"window": "day"}` parses; `category` defaults to None, `limit` defaults to 10."""
    parsed = TopEventsQuerySchema.model_validate({"window": "day"})
    assert parsed.window == "day"
    assert parsed.category is None
    assert parsed.limit == 10


def test_top_events_query_accepts_bogus_window_string():
    """`window` is a free-form `str` — `parse_window` rejects at the route layer, not Pydantic.

    A bogus window value MUST NOT raise `ValidationError` at the schema layer; the
    route handler catches `ValueError` from `parse_window()` and converts to a
    400 envelope.
    """
    parsed = TopEventsQuerySchema.model_validate({"window": "bogus"})
    assert parsed.window == "bogus"


def test_top_events_query_rejects_invalid_category():
    """`category` must be one of `EventCategory` values."""
    with pytest.raises(ValidationError):
        TopEventsQuerySchema.model_validate({"window": "day", "category": "bogus"})


def test_top_events_query_accepts_valid_categories():
    """All three `EventCategory` values are accepted."""
    for category_value in (member.value for member in EventCategory):
        parsed = TopEventsQuerySchema.model_validate(
            {"window": "day", "category": category_value}
        )
        assert parsed.category == category_value


def test_top_events_query_limit_rejects_zero():
    """`limit=0` raises (ge=1)."""
    with pytest.raises(ValidationError):
        TopEventsQuerySchema.model_validate({"window": "day", "limit": 0})


def test_top_events_query_limit_rejects_over_max():
    """`limit=101` raises (le=100)."""
    with pytest.raises(ValidationError):
        TopEventsQuerySchema.model_validate({"window": "day", "limit": 101})


def test_top_events_query_limit_accepts_boundaries():
    """`limit=1` and `limit=100` are both accepted (inclusive boundaries)."""
    assert TopEventsQuerySchema.model_validate({"window": "day", "limit": 1}).limit == 1
    assert (
        TopEventsQuerySchema.model_validate({"window": "day", "limit": 100}).limit
        == 100
    )


def test_top_events_query_rejects_extra_keys():
    """`extra="forbid"` rejects unknown query params."""
    with pytest.raises(ValidationError):
        TopEventsQuerySchema.model_validate({"window": "day", "foo": "bar"})


# -------------------------- TimeseriesQuerySchema --------------------------


def test_timeseries_query_happy_path():
    """`event_name` + `window` required; `resolution` defaults to `hour`."""
    parsed = TimeseriesQuerySchema.model_validate(
        {"event_name": EventName.UTUB_OPENED.value, "window": "day"}
    )
    assert parsed.event_name == EventName.UTUB_OPENED.value
    assert parsed.window == "day"
    assert parsed.resolution == "hour"


def test_timeseries_query_accepts_api_and_domain_event_names():
    """`event_name` accepts the full `EventName` enum — not just UI values."""
    for event_member in (
        EventName.API_HIT,
        EventName.UTUB_CREATED,
        EventName.UI_URL_COPY,
    ):
        parsed = TimeseriesQuerySchema.model_validate(
            {"event_name": event_member.value, "window": "day"}
        )
        assert parsed.event_name == event_member.value


def test_timeseries_query_rejects_invalid_event_name():
    """`event_name` must be a value from `EventName`."""
    with pytest.raises(ValidationError):
        TimeseriesQuerySchema.model_validate(
            {"event_name": "not_a_real_event", "window": "day"}
        )


def test_timeseries_query_resolution_accepts_hour_and_day():
    """`resolution` must be `hour` or `day`."""
    for resolution_value in ("hour", "day"):
        parsed = TimeseriesQuerySchema.model_validate(
            {
                "event_name": EventName.UTUB_OPENED.value,
                "window": "day",
                "resolution": resolution_value,
            }
        )
        assert parsed.resolution == resolution_value


def test_timeseries_query_rejects_invalid_resolution():
    """`resolution=minute` raises."""
    with pytest.raises(ValidationError):
        TimeseriesQuerySchema.model_validate(
            {
                "event_name": EventName.UTUB_OPENED.value,
                "window": "day",
                "resolution": "minute",
            }
        )


def test_timeseries_query_rejects_missing_event_name():
    """`event_name` is required."""
    with pytest.raises(ValidationError):
        TimeseriesQuerySchema.model_validate({"window": "day"})


def test_timeseries_query_rejects_extra_keys():
    """`extra="forbid"` rejects unknown query params."""
    with pytest.raises(ValidationError):
        TimeseriesQuerySchema.model_validate(
            {
                "event_name": EventName.UTUB_OPENED.value,
                "window": "day",
                "extra": "x",
            }
        )


# --------------------------- SummaryQuerySchema ----------------------------


def test_summary_query_happy_path():
    """Only `window` is required."""
    parsed = SummaryQuerySchema.model_validate({"window": "day"})
    assert parsed.window == "day"


def test_summary_query_rejects_missing_window():
    """`window` is required."""
    with pytest.raises(ValidationError):
        SummaryQuerySchema.model_validate({})


def test_summary_query_rejects_extra_keys():
    """`extra="forbid"` rejects unknown query params."""
    with pytest.raises(ValidationError):
        SummaryQuerySchema.model_validate({"window": "day", "category": "api"})


# ------------------------------- TopEventRow -------------------------------


def test_top_event_row_round_trip():
    """`TopEventRow.model_validate({...})` round-trips required fields."""
    row = TopEventRow.model_validate(
        {
            "event_name": EventName.UTUB_OPENED.value,
            "category": EventCategory.DOMAIN.value,
            "description": "UTub explicitly opened/selected",
            "total_count": 42,
        }
    )
    assert row.event_name == EventName.UTUB_OPENED.value
    assert row.category == EventCategory.DOMAIN.value
    assert row.description == "UTub explicitly opened/selected"
    assert row.total_count == 42


# --------------------------- TimeseriesBucketSchema ------------------------


def test_timeseries_bucket_schema_round_trip():
    """`TimeseriesBucketSchema` accepts `bucket: datetime` and `count: int`."""
    bucket_dt = datetime(2026, 1, 15, 14, 0, 0, tzinfo=timezone.utc)
    schema = TimeseriesBucketSchema.model_validate({"bucket": bucket_dt, "count": 7})
    assert schema.bucket == bucket_dt
    assert schema.count == 7


# ---------------------------- Response Envelopes ---------------------------


def test_top_events_response_schema_round_trip():
    """Full envelope schema accepts the route handler's payload shape."""
    start = datetime(2026, 1, 14, 14, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 1, 15, 14, 0, 0, tzinfo=timezone.utc)
    response = TopEventsResponseSchema.model_validate(
        {
            "window": "day",
            "window_start": start,
            "window_end": end,
            "category": None,
            "events": [
                {
                    "event_name": EventName.UTUB_OPENED.value,
                    "category": EventCategory.DOMAIN.value,
                    "description": "x",
                    "total_count": 1,
                }
            ],
        }
    )
    assert response.window == "day"
    assert response.window_start == start
    assert response.window_end == end
    assert response.category is None
    assert len(response.events) == 1


def test_timeseries_response_schema_round_trip():
    """`TimeseriesResponseSchema` accepts the route handler's payload shape."""
    start = datetime(2026, 1, 14, 14, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 1, 15, 14, 0, 0, tzinfo=timezone.utc)
    bucket_dt = datetime(2026, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
    response = TimeseriesResponseSchema.model_validate(
        {
            "event_name": EventName.UTUB_OPENED.value,
            "window": "day",
            "resolution": "hour",
            "window_start": start,
            "window_end": end,
            "buckets": [{"bucket": bucket_dt, "count": 3}],
        }
    )
    assert response.event_name == EventName.UTUB_OPENED.value
    assert response.resolution == "hour"
    assert len(response.buckets) == 1
    assert response.buckets[0].count == 3


def test_summary_category_count_round_trip():
    """`SummaryCategoryCount` accepts string category + current/previous ints."""
    summary_row = SummaryCategoryCount.model_validate(
        {"category": EventCategory.API.value, "current": 60, "previous": 30}
    )
    assert summary_row.category == EventCategory.API.value
    assert summary_row.current == 60
    assert summary_row.previous == 30


def test_summary_response_schema_round_trip():
    """`SummaryResponseSchema` round-trips with list-of-category payload."""
    start = datetime(2026, 1, 14, 14, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 1, 15, 14, 0, 0, tzinfo=timezone.utc)
    prev_start = datetime(2026, 1, 13, 14, 0, 0, tzinfo=timezone.utc)
    prev_end = start
    response = SummaryResponseSchema.model_validate(
        {
            "window": "day",
            "window_start": start,
            "window_end": end,
            "previous_window_start": prev_start,
            "previous_window_end": prev_end,
            "by_category": [
                {"category": "api", "current": 60, "previous": 30},
                {"category": "domain", "current": 5, "previous": 2},
            ],
        }
    )
    assert response.window == "day"
    assert response.previous_window_start == prev_start
    assert response.previous_window_end == prev_end
    assert len(response.by_category) == 2
