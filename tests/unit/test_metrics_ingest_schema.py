from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.metrics.events import EVENT_CATEGORY, EventCategory, EventName
from backend.schemas.requests.metrics import (
    UI_EVENT_NAMES,
    MetricsIngestRequest,
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
    # Sanity: module-level UI_EVENT_NAMES matches the live category map.
    assert tuple(sorted(UI_EVENT_NAMES)) == tuple(sorted(_UI_EVENT_VALUES))

    # Happy path — every UI value succeeds.
    for ui_value in _UI_EVENT_VALUES:
        MetricsIngestRequest.model_validate({"events": [{"event_name": ui_value}]})

    # api_hit (the API category) is rejected.
    with pytest.raises(ValidationError):
        MetricsIngestRequest.model_validate(
            {"events": [{"event_name": EventName.API_HIT.value}]}
        )

    # Every domain category value is rejected.
    for domain_value in _DOMAIN_EVENT_VALUES:
        with pytest.raises(ValidationError):
            MetricsIngestRequest.model_validate(
                {"events": [{"event_name": domain_value}]}
            )


def test_top_level_extra_keys_rejected():
    """Top-level `extra="forbid"` blocks unknown keys."""
    with pytest.raises(ValidationError):
        MetricsIngestRequest.model_validate(
            {
                "events": [{"event_name": EventName.UI_URL_COPY.value}],
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
    too_many = [{"event_name": EventName.UI_URL_COPY.value} for _ in range(101)]
    with pytest.raises(ValidationError):
        MetricsIngestRequest.model_validate({"events": too_many})

    # 100 events is fine.
    exactly_max = [{"event_name": EventName.UI_URL_COPY.value} for _ in range(100)]
    MetricsIngestRequest.model_validate({"events": exactly_max})


def test_batch_id_optional():
    """`batch_id` accepts None, str; rejects non-str."""
    base_event = {"event_name": EventName.UI_URL_COPY.value}

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
