from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.metrics.events import (
    EVENT_CATEGORY,
    DeviceType,
    EventCategory,
    EventName,
)
from backend.schemas.requests.metrics import (
    MetricsIngestRequest,
    TransportQuerySchema,
)

pytestmark = pytest.mark.unit


# Pre-computed UI / domain event-name lists for cleaner assertions.
_UI_EVENT_VALUES = tuple(
    member.value for member in EventName if EVENT_CATEGORY[member] is EventCategory.UI
)
_DOMAIN_EVENT_VALUES = tuple(
    member.value
    for member in EventName
    if EVENT_CATEGORY[member] is EventCategory.DOMAIN
)


def test_event_name_accepts_only_ui_category():
    """Every UI EventName value validates; api/domain values raise."""
    # Happy path — every UI value succeeds. `dimensions` is now a required
    # field on `MetricsIngestEvent`; the schema only enforces the dict shape,
    # so any non-empty dict suffices (per-event content checks happen at the
    # route layer via `validate_dimensions()`).
    for ui_value in _UI_EVENT_VALUES:
        MetricsIngestRequest.model_validate(
            {
                "events": [
                    {
                        "event_name": ui_value,
                        "dimensions": {"device_type": DeviceType.MOBILE},
                    }
                ]
            }
        )

    # api_hit (the API category) is rejected.
    with pytest.raises(ValidationError):
        MetricsIngestRequest.model_validate(
            {
                "events": [
                    {
                        "event_name": EventName.API_HIT.value,
                        "dimensions": {"device_type": DeviceType.MOBILE},
                    }
                ]
            }
        )

    # Every domain category value is rejected.
    for domain_value in _DOMAIN_EVENT_VALUES:
        with pytest.raises(ValidationError):
            MetricsIngestRequest.model_validate(
                {
                    "events": [
                        {
                            "event_name": domain_value,
                            "dimensions": {"device_type": DeviceType.MOBILE},
                        }
                    ]
                }
            )


def test_dimensions_field_is_required():
    """Omitting `dimensions` raises ValidationError — the field is required.

    `MetricsIngestEvent.dimensions` is a required field (no default); a payload
    missing the key must be rejected by Pydantic's schema validation before
    reaching the route-level `validate_dimensions()` per-event check.
    """
    with pytest.raises(ValidationError):
        MetricsIngestRequest.model_validate(
            {"events": [{"event_name": EventName.UI_URL_COPY.value}]}
        )


def test_top_level_extra_keys_rejected():
    """Top-level `extra="forbid"` blocks unknown keys."""
    with pytest.raises(ValidationError):
        MetricsIngestRequest.model_validate(
            {
                "events": [
                    {
                        "event_name": EventName.UI_URL_COPY.value,
                        "dimensions": {"device_type": DeviceType.MOBILE},
                    }
                ],
                "unknown_top_key": 1,
            }
        )


def test_event_extra_keys_rejected():
    """Event-item `extra="forbid"` blocks unknown keys."""
    with pytest.raises(ValidationError):
        MetricsIngestRequest.model_validate(
            {
                "events": [
                    {
                        "event_name": EventName.UI_URL_COPY.value,
                        "result": "success",
                        "extra": "x",
                    }
                ]
            }
        )


def test_dimensions_validated_per_event():
    """Schema accepts loose `dimensions: dict` shape; per-event Literal checks
    happen at the route layer via `validate_dimensions()`."""
    # Schema-level validation is intentionally permissive on dimension content;
    # the route handler enforces per-event Literal values with
    # validate_dimensions(...). The schema here just enforces the dict shape.
    MetricsIngestRequest.model_validate(
        {
            "events": [
                {
                    "event_name": EventName.UI_URL_COPY.value,
                    "dimensions": {"result": "maybe"},
                }
            ]
        }
    )
    # Confirm dimensions can be a dict[str, str|int|bool] but not, e.g., a list.
    with pytest.raises(ValidationError):
        MetricsIngestRequest.model_validate(
            {
                "events": [
                    {
                        "event_name": EventName.UI_URL_COPY.value,
                        "dimensions": ["not", "a", "dict"],
                    }
                ]
            }
        )


def test_empty_events_list_rejected():
    """`min_length=1` enforced on `events`."""
    with pytest.raises(ValidationError):
        MetricsIngestRequest.model_validate({"events": []})


def test_max_events_limit():
    """`max_length=100` enforced on `events`."""
    too_many = [
        {
            "event_name": EventName.UI_URL_COPY.value,
            "dimensions": {"device_type": DeviceType.MOBILE},
        }
        for _ in range(101)
    ]
    with pytest.raises(ValidationError):
        MetricsIngestRequest.model_validate({"events": too_many})

    # 100 events is fine.
    exactly_max = [
        {
            "event_name": EventName.UI_URL_COPY.value,
            "dimensions": {"device_type": DeviceType.MOBILE},
        }
        for _ in range(100)
    ]
    MetricsIngestRequest.model_validate({"events": exactly_max})


def test_batch_id_optional():
    """`batch_id` accepts None, str; rejects non-str."""
    base_event = {
        "event_name": EventName.UI_URL_COPY.value,
        "dimensions": {"device_type": DeviceType.MOBILE},
    }

    # None is allowed
    MetricsIngestRequest.model_validate({"events": [base_event], "batch_id": None})

    # String is allowed
    MetricsIngestRequest.model_validate({"events": [base_event], "batch_id": "abc-123"})

    # Non-string raises (Pydantic v2 doesn't coerce int -> str unless lax;
    # for `str` annotations Pydantic is lax enough to accept int as string,
    # so test with a list which definitely fails).
    with pytest.raises(ValidationError):
        MetricsIngestRequest.model_validate(
            {"events": [base_event], "batch_id": ["a", "b"]}
        )


def test_batch_id_max_length_boundary_accepts_128_chars():
    """`batch_id` with exactly 128 characters is accepted (boundary inclusive).

    Documents the `max_length=128` cap on `MetricsIngestRequest.batch_id` —
    UUID4 strings are 36 chars, so 128 gives generous headroom for any future
    client format. The cap exists because the value is used verbatim as a
    Redis key suffix (`metrics:batch:<batch_id>`); without it, an unbounded
    length would enable large-key allocation within rate-limit windows.
    """
    base_event = {
        "event_name": EventName.UI_URL_COPY.value,
        "dimensions": {"device_type": DeviceType.MOBILE},
    }

    MetricsIngestRequest.model_validate({"events": [base_event], "batch_id": "a" * 128})


def test_batch_id_max_length_boundary_rejects_129_chars():
    """`batch_id` with 129 characters raises ValidationError (boundary exclusive)."""
    base_event = {
        "event_name": EventName.UI_URL_COPY.value,
        "dimensions": {"device_type": DeviceType.MOBILE},
    }

    with pytest.raises(ValidationError):
        MetricsIngestRequest.model_validate(
            {"events": [base_event], "batch_id": "a" * 129}
        )


def test_transport_query_schema_absent_param_yields_none():
    """Empty payload yields `transport is None` (the param is optional)."""
    schema_instance = TransportQuerySchema.model_validate({})
    assert schema_instance.transport is None


def test_transport_query_schema_accepts_beacon():
    """`transport='beacon'` is accepted and round-trips on the model."""
    schema_instance = TransportQuerySchema.model_validate({"transport": "beacon"})
    assert schema_instance.transport == "beacon"


def test_transport_query_schema_rejects_non_beacon_literal():
    """Any non-`'beacon'` value raises ValidationError (Literal mismatch)."""
    with pytest.raises(ValidationError):
        TransportQuerySchema.model_validate({"transport": "quic"})


def test_transport_query_schema_rejects_extra_key():
    """`extra='forbid'` blocks unknown query keys (e.g. typo'd `transports`)."""
    with pytest.raises(ValidationError):
        TransportQuerySchema.model_validate({"transports": "beacon"})
