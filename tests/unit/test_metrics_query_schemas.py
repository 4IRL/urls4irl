from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from backend.metrics.events import EventCategory, EventName
from backend.metrics.flows import _parse_flow_filter_condition
from backend.schemas.metrics import (
    SummaryCategoryCount,
    SummaryResponseSchema,
    TimeseriesBucketSchema,
    TimeseriesResponseSchema,
    TopEventRow,
    TopEventsResponseSchema,
)
from backend.schemas.requests.metrics import (
    _BOTH_WINDOW_AND_RANGE_ERROR,
    _MISSING_WINDOW_OR_RANGE_ERROR,
    _PARTIAL_RANGE_ERROR,
    _RANGE_ORDER_ERROR,
    GaugesTimeseriesQuerySchema,
    LatencyQuerySchema,
    LatencyTimeseriesQuerySchema,
    SummaryQuerySchema,
    TimeseriesQuerySchema,
    TopEventsQuerySchema,
)

pytestmark = pytest.mark.unit

ABS_RANGE_START_ISO: str = "2026-01-01T00:00:00+00:00"
ABS_RANGE_END_ISO: str = "2026-02-01T00:00:00+00:00"
ABS_RANGE_START: datetime = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
ABS_RANGE_END: datetime = datetime(2026, 2, 1, 0, 0, 0, tzinfo=timezone.utc)

QUERY_SCHEMAS_WITH_BASE_PAYLOAD: tuple[tuple[type, dict[str, str]], ...] = (
    (TopEventsQuerySchema, {}),
    (
        TimeseriesQuerySchema,
        {"event_name": EventName.UTUB_OPENED.value},
    ),
    (SummaryQuerySchema, {}),
)


def _assert_first_validation_message(
    validation_error: ValidationError, expected_message: str
) -> None:
    """Assert the first error in `validation_error` matches the verbatim string.

    Pydantic v2 wraps `ValueError("foo")` inside an `errors()[0]["msg"]` of
    "Value error, foo" — the `Value error, ` prefix is added by the wrapper,
    so the helper strips it before comparison.
    """
    raw_message = validation_error.errors()[0]["msg"]
    stripped = raw_message.removeprefix("Value error, ")
    assert stripped == expected_message


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


def test_top_events_device_type_int_one_parses_ok():
    """`device_type=1` (mobile) parses to `1`."""
    parsed = TopEventsQuerySchema.model_validate({"window": "day", "device_type": 1})
    assert parsed.device_type == 1


def test_top_events_device_type_int_two_parses_ok():
    """`device_type=2` (desktop) parses to `2`."""
    parsed = TopEventsQuerySchema.model_validate({"window": "day", "device_type": 2})
    assert parsed.device_type == 2


def test_top_events_device_type_str_one_coerces_to_int():
    """`device_type="1"` (from query string) coerces to int `1`."""
    parsed = TopEventsQuerySchema.model_validate({"window": "day", "device_type": "1"})
    assert parsed.device_type == 1


def test_top_events_device_type_str_two_coerces_to_int():
    """`device_type="2"` (from query string) coerces to int `2`."""
    parsed = TopEventsQuerySchema.model_validate({"window": "day", "device_type": "2"})
    assert parsed.device_type == 2


def test_top_events_device_type_three_rejected():
    """`device_type=3` is not a valid `DeviceType` member (MOBILE=1, DESKTOP=2)."""
    with pytest.raises(ValidationError):
        TopEventsQuerySchema.model_validate({"window": "day", "device_type": 3})


def test_top_events_device_type_omitted_defaults_to_none():
    """Omitting `device_type` defaults to `None` (no filter)."""
    parsed = TopEventsQuerySchema.model_validate({"window": "day"})
    assert parsed.device_type is None


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


def test_timeseries_device_type_int_one_parses_ok():
    """`device_type=1` (mobile) parses to `1`."""
    parsed = TimeseriesQuerySchema.model_validate(
        {
            "event_name": EventName.UTUB_OPENED.value,
            "window": "day",
            "device_type": 1,
        }
    )
    assert parsed.device_type == 1


def test_timeseries_device_type_int_two_parses_ok():
    """`device_type=2` (desktop) parses to `2`."""
    parsed = TimeseriesQuerySchema.model_validate(
        {
            "event_name": EventName.UTUB_OPENED.value,
            "window": "day",
            "device_type": 2,
        }
    )
    assert parsed.device_type == 2


def test_timeseries_device_type_str_one_coerces_to_int():
    """`device_type="1"` (from query string) coerces to int `1`."""
    parsed = TimeseriesQuerySchema.model_validate(
        {
            "event_name": EventName.UTUB_OPENED.value,
            "window": "day",
            "device_type": "1",
        }
    )
    assert parsed.device_type == 1


def test_timeseries_device_type_str_two_coerces_to_int():
    """`device_type="2"` (from query string) coerces to int `2`."""
    parsed = TimeseriesQuerySchema.model_validate(
        {
            "event_name": EventName.UTUB_OPENED.value,
            "window": "day",
            "device_type": "2",
        }
    )
    assert parsed.device_type == 2


def test_timeseries_device_type_three_rejected():
    """`device_type=3` is not a valid `DeviceType` member (MOBILE=1, DESKTOP=2)."""
    with pytest.raises(ValidationError):
        TimeseriesQuerySchema.model_validate(
            {
                "event_name": EventName.UTUB_OPENED.value,
                "window": "day",
                "device_type": 3,
            }
        )


def test_timeseries_device_type_omitted_defaults_to_none():
    """Omitting `device_type` defaults to `None` (no filter)."""
    parsed = TimeseriesQuerySchema.model_validate(
        {"event_name": EventName.UTUB_OPENED.value, "window": "day"}
    )
    assert parsed.device_type is None


# --------------------------- SummaryQuerySchema ----------------------------


def test_summary_query_happy_path():
    """Only `window` is required."""
    parsed = SummaryQuerySchema.model_validate({"window": "day"})
    assert parsed.window == "day"


def test_summary_query_rejects_missing_window_and_range():
    """No `window` and no `start`/`end` → 400 via the XOR validator."""
    with pytest.raises(ValidationError) as exc_info:
        SummaryQuerySchema.model_validate({})
    _assert_first_validation_message(exc_info.value, _MISSING_WINDOW_OR_RANGE_ERROR)


def test_summary_query_rejects_extra_keys():
    """`extra="forbid"` rejects unknown query params."""
    with pytest.raises(ValidationError):
        SummaryQuerySchema.model_validate({"window": "day", "category": "api"})


# ---------------------- GaugesTimeseriesQuerySchema ------------------------


def test_gauges_timeseries_query_happy_path_with_window_only():
    """`{"window": "day"}` parses; start/end default to None (batched, no name)."""
    parsed = GaugesTimeseriesQuerySchema.model_validate({"window": "day"})
    assert parsed.window == "day"
    assert parsed.start is None
    assert parsed.end is None


def test_gauges_timeseries_query_accepts_absolute_range():
    """`start`+`end` alone (no window) is accepted."""
    parsed = GaugesTimeseriesQuerySchema.model_validate(
        {"start": ABS_RANGE_START_ISO, "end": ABS_RANGE_END_ISO}
    )
    assert parsed.window is None
    assert parsed.start == ABS_RANGE_START
    assert parsed.end == ABS_RANGE_END


def test_gauges_timeseries_query_rejects_stray_name_key():
    """A `name` key is rejected — the batched schema has no `name` field (extra=forbid)."""
    with pytest.raises(ValidationError):
        GaugesTimeseriesQuerySchema.model_validate(
            {"window": "day", "name": "total_users"}
        )


def test_gauges_timeseries_query_rejects_extra_keys():
    """`extra="forbid"` rejects any unknown query param."""
    with pytest.raises(ValidationError):
        GaugesTimeseriesQuerySchema.model_validate({"window": "day", "foo": "bar"})


def test_gauges_timeseries_query_rejects_window_and_range_together():
    """Supplying both `window` and `start`+`end` is ambiguous → 400 via XOR validator."""
    with pytest.raises(ValidationError) as exc_info:
        GaugesTimeseriesQuerySchema.model_validate(
            {
                "window": "day",
                "start": ABS_RANGE_START_ISO,
                "end": ABS_RANGE_END_ISO,
            }
        )
    _assert_first_validation_message(exc_info.value, _BOTH_WINDOW_AND_RANGE_ERROR)


def test_gauges_timeseries_query_rejects_missing_window_and_range():
    """No window and no range → 400 via the missing-spec XOR branch."""
    with pytest.raises(ValidationError) as exc_info:
        GaugesTimeseriesQuerySchema.model_validate({})
    _assert_first_validation_message(exc_info.value, _MISSING_WINDOW_OR_RANGE_ERROR)


def test_gauges_timeseries_query_rejects_partial_range():
    """`start` without `end` is incomplete → 400 via the partial-range XOR branch."""
    with pytest.raises(ValidationError) as exc_info:
        GaugesTimeseriesQuerySchema.model_validate({"start": ABS_RANGE_START_ISO})
    _assert_first_validation_message(exc_info.value, _PARTIAL_RANGE_ERROR)


# -------------------- Window XOR Absolute-Range Validation -----------------


@pytest.mark.parametrize(
    "schema_cls,base_payload",
    QUERY_SCHEMAS_WITH_BASE_PAYLOAD,
    ids=["top", "timeseries", "summary"],
)
def test_absolute_range_happy_path(schema_cls: type, base_payload: dict[str, str]):
    """`start`+`end` alone (no `window`) is accepted on every query schema."""
    payload = {**base_payload, "start": ABS_RANGE_START_ISO, "end": ABS_RANGE_END_ISO}
    parsed = schema_cls.model_validate(payload)
    assert parsed.window is None
    assert parsed.start == ABS_RANGE_START
    assert parsed.end == ABS_RANGE_END


@pytest.mark.parametrize(
    "schema_cls,base_payload",
    QUERY_SCHEMAS_WITH_BASE_PAYLOAD,
    ids=["top", "timeseries", "summary"],
)
def test_window_and_range_together_rejected(
    schema_cls: type, base_payload: dict[str, str]
):
    """Supplying both `window` and `start`+`end` is ambiguous → 400."""
    payload = {
        **base_payload,
        "window": "day",
        "start": ABS_RANGE_START_ISO,
        "end": ABS_RANGE_END_ISO,
    }
    with pytest.raises(ValidationError) as exc_info:
        schema_cls.model_validate(payload)
    _assert_first_validation_message(exc_info.value, _BOTH_WINDOW_AND_RANGE_ERROR)


@pytest.mark.parametrize(
    "partial_field,partial_value",
    [
        ("start", ABS_RANGE_START_ISO),
        ("end", ABS_RANGE_END_ISO),
    ],
)
@pytest.mark.parametrize(
    "schema_cls,base_payload",
    QUERY_SCHEMAS_WITH_BASE_PAYLOAD,
    ids=["top", "timeseries", "summary"],
)
def test_partial_range_rejected(
    schema_cls: type,
    base_payload: dict[str, str],
    partial_field: str,
    partial_value: str,
):
    """`start` without `end` (and vice versa) is incomplete → 400."""
    payload = {**base_payload, partial_field: partial_value}
    with pytest.raises(ValidationError) as exc_info:
        schema_cls.model_validate(payload)
    _assert_first_validation_message(exc_info.value, _PARTIAL_RANGE_ERROR)


@pytest.mark.parametrize(
    "schema_cls,base_payload",
    QUERY_SCHEMAS_WITH_BASE_PAYLOAD,
    ids=["top", "timeseries", "summary"],
)
def test_neither_window_nor_range_rejected(
    schema_cls: type, base_payload: dict[str, str]
):
    """Empty spec (no window, no range) → 400 with the missing-spec message."""
    with pytest.raises(ValidationError) as exc_info:
        schema_cls.model_validate(base_payload)
    _assert_first_validation_message(exc_info.value, _MISSING_WINDOW_OR_RANGE_ERROR)


@pytest.mark.parametrize(
    "schema_cls,base_payload",
    QUERY_SCHEMAS_WITH_BASE_PAYLOAD,
    ids=["top", "timeseries", "summary"],
)
def test_start_equal_to_end_rejected(schema_cls: type, base_payload: dict[str, str]):
    """An empty-duration range (start == end) is rejected."""
    payload = {
        **base_payload,
        "start": ABS_RANGE_START_ISO,
        "end": ABS_RANGE_START_ISO,
    }
    with pytest.raises(ValidationError) as exc_info:
        schema_cls.model_validate(payload)
    _assert_first_validation_message(exc_info.value, _RANGE_ORDER_ERROR)


@pytest.mark.parametrize(
    "schema_cls,base_payload",
    QUERY_SCHEMAS_WITH_BASE_PAYLOAD,
    ids=["top", "timeseries", "summary"],
)
def test_start_after_end_rejected(schema_cls: type, base_payload: dict[str, str]):
    """`start` after `end` is rejected — admin cannot ask for a reversed range."""
    payload = {
        **base_payload,
        "start": ABS_RANGE_END_ISO,
        "end": ABS_RANGE_START_ISO,
    }
    with pytest.raises(ValidationError) as exc_info:
        schema_cls.model_validate(payload)
    _assert_first_validation_message(exc_info.value, _RANGE_ORDER_ERROR)


@pytest.mark.parametrize(
    "naive_field,naive_value",
    [
        ("start", "2026-01-01T00:00:00"),
        ("end", "2026-02-01T00:00:00"),
    ],
)
@pytest.mark.parametrize(
    "schema_cls,base_payload",
    QUERY_SCHEMAS_WITH_BASE_PAYLOAD,
    ids=["top", "timeseries", "summary"],
)
def test_naive_datetime_rejected(
    schema_cls: type,
    base_payload: dict[str, str],
    naive_field: str,
    naive_value: str,
):
    """`AwareDatetime` rejects ISO-8601 strings without a timezone designator.

    The other half of the range is supplied as a valid `Z`-suffixed ISO so the
    failure is unambiguously the AwareDatetime check, not the partial-range
    or missing-spec branch of the XOR validator.
    """
    paired_field = "end" if naive_field == "start" else "start"
    paired_value = ABS_RANGE_END_ISO if naive_field == "start" else ABS_RANGE_START_ISO
    payload = {
        **base_payload,
        naive_field: naive_value,
        paired_field: paired_value,
    }
    with pytest.raises(ValidationError) as exc_info:
        schema_cls.model_validate(payload)
    failing_fields = {error["loc"][0] for error in exc_info.value.errors()}
    assert naive_field in failing_fields


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


# ----------------------- _parse_flow_filter_condition ----------------------


def test_parse_flow_filter_condition_well_formed_returns_tuple():
    """A well-formed `dim:value` scalar parses into a `(dim, value)` tuple."""
    assert _parse_flow_filter_condition("form:utub_create") == ("form", "utub_create")


def test_parse_flow_filter_condition_value_may_contain_colons():
    """Only the FIRST colon splits dim from value, so values may contain colons."""
    assert _parse_flow_filter_condition("endpoint:urls:create") == (
        "endpoint",
        "urls:create",
    )


def test_parse_flow_filter_condition_passes_through_existing_tuple():
    """An already-tuple input (in-code `FLOWS` entries) passes through unchanged."""
    assert _parse_flow_filter_condition(("form", "login")) == ("form", "login")


def test_parse_flow_filter_condition_rejects_entry_without_colon():
    """A scalar lacking a colon raises `ValueError`."""
    with pytest.raises(ValueError):
        _parse_flow_filter_condition("nocolon")


def test_parse_flow_filter_condition_rejects_empty_dim():
    """A scalar with an empty dim (leading colon) raises `ValueError`."""
    with pytest.raises(ValueError):
        _parse_flow_filter_condition(":value")


def test_parse_flow_filter_condition_accepts_empty_value():
    """An empty value after the colon (`form:`) parses to `("form", "")`.

    Empty values are allowed by design — only an empty dim (before the colon)
    or a missing colon is rejected. The funnel never queries an empty value in
    practice, but the parser stays permissive so a future filter on a sentinel
    empty-string dim value does not require a change.
    """
    assert _parse_flow_filter_condition("form:") == ("form", "")


def test_parse_flow_filter_condition_rejects_non_str_non_tuple():
    """A scalar that is neither a `str` nor a `tuple` raises `ValueError`.

    The `BeforeValidator` accepts only the colon-encoded `str` wire form or an
    already-parsed `tuple` passthrough; any other type (here an `int`) is
    rejected before Pydantic binds the `tuple[str, str]` field.
    """
    with pytest.raises(ValueError):
        _parse_flow_filter_condition(42)


# --------------------------- LatencyQuerySchema ----------------------------


def test_latency_query_happy_path_with_window_only():
    """`{"window": "day"}` parses; metric_name/endpoint default None, limit=25."""
    parsed = LatencyQuerySchema.model_validate({"window": "day"})
    assert parsed.window == "day"
    assert parsed.metric_name is None
    assert parsed.endpoint is None
    assert parsed.method is None
    assert parsed.device_type is None
    assert parsed.limit == 25


def test_latency_query_accepts_absolute_range():
    """`start`+`end` alone (no window) is accepted."""
    parsed = LatencyQuerySchema.model_validate(
        {"start": ABS_RANGE_START_ISO, "end": ABS_RANGE_END_ISO}
    )
    assert parsed.window is None
    assert parsed.start == ABS_RANGE_START
    assert parsed.end == ABS_RANGE_END


def test_latency_query_accepts_known_metric_name():
    """The sole `api_request_duration` metric name is accepted."""
    parsed = LatencyQuerySchema.model_validate(
        {"window": "day", "metric_name": "api_request_duration"}
    )
    assert parsed.metric_name == "api_request_duration"


def test_latency_query_rejects_unknown_metric_name():
    """An unknown metric name is rejected by the Literal."""
    with pytest.raises(ValidationError):
        LatencyQuerySchema.model_validate(
            {"window": "day", "metric_name": "bogus_metric"}
        )


def test_latency_query_device_type_str_coerces_to_int():
    """A digit-string `device_type` query param coerces to the int enum value."""
    parsed = LatencyQuerySchema.model_validate({"window": "day", "device_type": "1"})
    assert int(parsed.device_type) == 1


def test_latency_query_device_type_invalid_rejected():
    """A device_type outside {1, 2} is rejected."""
    with pytest.raises(ValidationError):
        LatencyQuerySchema.model_validate({"window": "day", "device_type": 3})


def test_latency_query_limit_rejects_zero():
    """`limit` has a `ge=1` bound; 0 is rejected."""
    with pytest.raises(ValidationError):
        LatencyQuerySchema.model_validate({"window": "day", "limit": 0})


def test_latency_query_limit_rejects_over_max():
    """`limit` has a `le=200` bound; 201 is rejected."""
    with pytest.raises(ValidationError):
        LatencyQuerySchema.model_validate({"window": "day", "limit": 201})


def test_latency_query_limit_accepts_boundaries():
    """`limit` accepts both 1 and 200 inclusive."""
    assert LatencyQuerySchema.model_validate({"window": "day", "limit": 1}).limit == 1
    assert (
        LatencyQuerySchema.model_validate({"window": "day", "limit": 200}).limit == 200
    )


def test_latency_query_rejects_extra_keys():
    """`extra="forbid"` rejects any unknown query param."""
    with pytest.raises(ValidationError):
        LatencyQuerySchema.model_validate({"window": "day", "foo": "bar"})


def test_latency_query_rejects_window_and_range_together():
    """Supplying both `window` and `start`+`end` is ambiguous → 400 via XOR validator."""
    with pytest.raises(ValidationError) as exc_info:
        LatencyQuerySchema.model_validate(
            {
                "window": "day",
                "start": ABS_RANGE_START_ISO,
                "end": ABS_RANGE_END_ISO,
            }
        )
    _assert_first_validation_message(exc_info.value, _BOTH_WINDOW_AND_RANGE_ERROR)


def test_latency_query_rejects_missing_window_and_range():
    """No window and no range → 400 via the missing-spec XOR branch."""
    with pytest.raises(ValidationError) as exc_info:
        LatencyQuerySchema.model_validate({})
    _assert_first_validation_message(exc_info.value, _MISSING_WINDOW_OR_RANGE_ERROR)


def test_latency_query_rejects_partial_range():
    """`start` without `end` is incomplete → 400 via the partial-range XOR branch."""
    with pytest.raises(ValidationError) as exc_info:
        LatencyQuerySchema.model_validate({"start": ABS_RANGE_START_ISO})
    _assert_first_validation_message(exc_info.value, _PARTIAL_RANGE_ERROR)


# ----------------------- LatencyTimeseriesQuerySchema ----------------------


def test_latency_timeseries_query_happy_path():
    """`{"window": "day", "endpoint": "..."}` parses; resolution defaults to hour."""
    parsed = LatencyTimeseriesQuerySchema.model_validate(
        {"window": "day", "endpoint": "utubs.get_utub"}
    )
    assert parsed.window == "day"
    assert parsed.endpoint == "utubs.get_utub"
    assert parsed.resolution == "hour"
    assert parsed.method is None


def test_latency_timeseries_query_requires_endpoint():
    """`endpoint` is required — omitting it raises ValidationError."""
    with pytest.raises(ValidationError):
        LatencyTimeseriesQuerySchema.model_validate({"window": "day"})


def test_latency_timeseries_query_accepts_resolution_day():
    """`resolution=day` is accepted."""
    parsed = LatencyTimeseriesQuerySchema.model_validate(
        {"window": "day", "endpoint": "utubs.get_utub", "resolution": "day"}
    )
    assert parsed.resolution == "day"


def test_latency_timeseries_query_rejects_bad_resolution():
    """A resolution outside {hour, day} is rejected."""
    with pytest.raises(ValidationError):
        LatencyTimeseriesQuerySchema.model_validate(
            {"window": "day", "endpoint": "utubs.get_utub", "resolution": "minute"}
        )


def test_latency_timeseries_query_rejects_extra_keys():
    """`extra="forbid"` rejects any unknown query param."""
    with pytest.raises(ValidationError):
        LatencyTimeseriesQuerySchema.model_validate(
            {"window": "day", "endpoint": "utubs.get_utub", "foo": "bar"}
        )


def test_latency_timeseries_query_rejects_window_and_range_together():
    """Supplying both `window` and `start`+`end` is rejected by the XOR validator."""
    with pytest.raises(ValidationError) as exc_info:
        LatencyTimeseriesQuerySchema.model_validate(
            {
                "endpoint": "utubs.get_utub",
                "window": "day",
                "start": ABS_RANGE_START_ISO,
                "end": ABS_RANGE_END_ISO,
            }
        )
    _assert_first_validation_message(exc_info.value, _BOTH_WINDOW_AND_RANGE_ERROR)
