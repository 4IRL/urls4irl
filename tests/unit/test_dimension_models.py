from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.metrics.dimension_models import (
    DIMENSION_MODELS,
    get_all_dimension_keys,
    validate_dimensions,
)
from backend.metrics.events import (
    EVENT_CATEGORY,
    DeviceType,
    EventCategory,
    EventName,
)

pytestmark = pytest.mark.unit


# Table-driven cases — sourced from
# plans/anonymous-metrics-ingest/tmp/research-schemas.md (the §2b matrix).
# Each tuple: (EventName member, valid dimensions dict). UI-category entries
# include `device_type` (required on all UI events via `UIBaseDimensions`).
PER_EVENT_VALID_DIMS: tuple[tuple[EventName, dict], ...] = (
    (
        EventName.API_HIT,
        {"endpoint": "/utubs", "method": "POST", "status_code": 200},
    ),
    (
        EventName.UI_UTUB_SELECT,
        {"search_active": "true", "device_type": DeviceType.MOBILE},
    ),
    (
        EventName.UI_UTUB_NAME_EDIT_OPEN,
        {"trigger": "pencil_icon", "device_type": DeviceType.DESKTOP},
    ),
    (
        EventName.UI_UTUB_DESC_EDIT_OPEN,
        {"trigger": "create_button", "device_type": DeviceType.MOBILE},
    ),
    (
        EventName.UI_URL_ACCESS,
        {
            "trigger": "corner_button",
            "search_active": "false",
            "active_tag_count": 3,
            "device_type": DeviceType.DESKTOP,
        },
    ),
    (
        EventName.UI_URL_CARD_CLICK,
        {
            "search_active": "true",
            "active_tag_count": 0,
            "device_type": DeviceType.MOBILE,
        },
    ),
    (EventName.UI_URL_COPY, {"result": "success", "device_type": DeviceType.DESKTOP}),
    (EventName.UI_SEARCH_OPEN, {"target": "urls", "device_type": DeviceType.MOBILE}),
    (EventName.UI_SEARCH_CLOSE, {"target": "utubs", "device_type": DeviceType.DESKTOP}),
    (EventName.UI_TAG_CREATE_OPEN, {"scope": "utub", "device_type": DeviceType.MOBILE}),
    (EventName.UI_TAG_CREATE_OPEN, {"scope": "url", "device_type": DeviceType.DESKTOP}),
    (EventName.UI_TAG_DELETE_OPEN, {"scope": "utub", "device_type": DeviceType.MOBILE}),
    (EventName.UI_TAG_DELETE_OPEN, {"scope": "url", "device_type": DeviceType.DESKTOP}),
    (
        EventName.UI_TAG_DELETE_CONFIRM,
        {"scope": "utub", "device_type": DeviceType.MOBILE},
    ),
    (
        EventName.UI_TAG_DELETE_CONFIRM,
        {"scope": "url", "device_type": DeviceType.DESKTOP},
    ),
    (
        EventName.UI_TAG_DELETE_CANCEL,
        {"scope": "utub", "device_type": DeviceType.MOBILE},
    ),
    (
        EventName.UI_TAG_DELETE_CANCEL,
        {"scope": "url", "device_type": DeviceType.DESKTOP},
    ),
    (
        EventName.UI_FORM_SUBMIT,
        {
            "trigger": "enter_key",
            "form": "url_create",
            "device_type": DeviceType.MOBILE,
        },
    ),
    (
        EventName.UI_FORM_SUBMIT,
        {
            "trigger": "button_click",
            "form": "url_title_edit",
            "device_type": DeviceType.DESKTOP,
        },
    ),
    (
        EventName.UI_FORM_SUBMIT,
        {
            "trigger": "enter_key",
            "form": "url_string_edit",
            "device_type": DeviceType.MOBILE,
        },
    ),
    (
        EventName.UI_FORM_SUBMIT,
        {
            "trigger": "button_click",
            "form": "utub_name_edit",
            "device_type": DeviceType.DESKTOP,
        },
    ),
    (
        EventName.UI_FORM_SUBMIT,
        {
            "trigger": "enter_key",
            "form": "utub_desc_edit",
            "device_type": DeviceType.MOBILE,
        },
    ),
    (
        EventName.UI_FORM_SUBMIT,
        {
            "trigger": "button_click",
            "form": "member_invite",
            "device_type": DeviceType.DESKTOP,
        },
    ),
    (
        EventName.UI_FORM_CANCEL,
        {
            "trigger": "escape_key",
            "form": "tag_create",
            "device_type": DeviceType.MOBILE,
        },
    ),
    (
        EventName.UI_FORM_CANCEL,
        {
            "trigger": "escape_key",
            "form": "url_title_edit",
            "device_type": DeviceType.DESKTOP,
        },
    ),
    (
        EventName.UI_VALIDATION_ERROR,
        {"form": "utub_create", "device_type": DeviceType.MOBILE},
    ),
    (
        EventName.UI_VALIDATION_ERROR,
        {"form": "utub_name_edit", "device_type": DeviceType.DESKTOP},
    ),
    (
        EventName.UI_VALIDATION_ERROR,
        {"form": "url_string_edit", "device_type": DeviceType.MOBILE},
    ),
    (
        EventName.UI_DECK_COLLAPSE,
        {"deck": "members", "device_type": DeviceType.DESKTOP},
    ),
    (EventName.UI_DECK_EXPAND, {"deck": "urls", "device_type": DeviceType.MOBILE}),
    (EventName.UI_MOBILE_NAV, {"target": "tags", "device_type": DeviceType.MOBILE}),
    (
        EventName.UI_AUTH_FORM_SWITCH,
        {"target": "register", "device_type": DeviceType.DESKTOP},
    ),
    # `_DimDeviceOnly` event — exercises the model that replaces formerly-None UI entries.
    (EventName.UI_UTUB_CREATE_OPEN, {"device_type": DeviceType.MOBILE}),
)


def test_every_eventname_member_has_an_entry():
    """Every member of `EventName` is keyed in `DIMENSION_MODELS`."""
    assert set(DIMENSION_MODELS.keys()) == set(EventName)


def test_none_entries_reject_non_empty_dimensions():
    """For non-UI events with `DIMENSION_MODELS[event] is None` (domain events), non-empty dims fail."""
    none_events = [
        event
        for event, model in DIMENSION_MODELS.items()
        if model is None and EVENT_CATEGORY[event] != EventCategory.UI
    ]
    assert none_events, "expected at least one non-UI event with no dim model"
    for event in none_events:
        # Empty dict and None pass silently
        validate_dimensions(event, {})
        validate_dimensions(event, None)
        # Non-empty dict fails
        with pytest.raises(ValidationError):
            validate_dimensions(event, {"x": 1})


def test_device_only_events_require_device_type():
    """Formerly-None UI events now require `device_type` via `_DimDeviceOnly`."""
    device_only_events = [
        event
        for event, model in DIMENSION_MODELS.items()
        if EVENT_CATEGORY[event] == EventCategory.UI
        and model is not None
        and set(model.model_fields.keys()) == {"device_type"}
    ]
    assert device_only_events, "expected at least one `_DimDeviceOnly` event"
    for event in device_only_events:
        with pytest.raises(ValidationError):
            validate_dimensions(event, {})
        validate_dimensions(event, {"device_type": DeviceType.MOBILE})
        validate_dimensions(event, {"device_type": DeviceType.DESKTOP})
        validate_dimensions(event, {"device_type": int(DeviceType.MOBILE)})
        validate_dimensions(event, {"device_type": int(DeviceType.DESKTOP)})


def test_device_only_events_reject_unknown_device_type_value():
    """A `device_type` value outside the `DeviceType` int enum raises.

    Proves the schema rejects out-of-range integers (a future TABLET=3 must
    be added to the enum, not silently accepted), rejects the legacy string
    form ("mobile"/"desktop") so int-only wire format is enforced, and —
    because `device_type` uses a `BeforeValidator` that rejects strings —
    also rejects stringified int inputs ("1", "2") that Pydantic v2 lax mode
    would otherwise coerce.
    """
    device_only_events = [
        event
        for event, model in DIMENSION_MODELS.items()
        if EVENT_CATEGORY[event] == EventCategory.UI
        and model is not None
        and set(model.model_fields.keys()) == {"device_type"}
    ]
    assert device_only_events, "expected at least one `_DimDeviceOnly` event"
    for event in device_only_events:
        with pytest.raises(ValidationError):
            validate_dimensions(event, {"device_type": 0})
        with pytest.raises(ValidationError):
            validate_dimensions(event, {"device_type": 3})
        with pytest.raises(ValidationError):
            validate_dimensions(event, {"device_type": "mobile"})
        with pytest.raises(ValidationError):
            validate_dimensions(event, {"device_type": "tablet"})
        with pytest.raises(ValidationError):
            validate_dimensions(event, {"device_type": "1"})
        with pytest.raises(ValidationError):
            validate_dimensions(event, {"device_type": "2"})


def test_per_event_models_accept_documented_values():
    """Each documented (event, dims) pair from §2b validates cleanly."""
    for event, valid_dims in PER_EVENT_VALID_DIMS:
        model_class = DIMENSION_MODELS[event]
        assert model_class is not None, f"{event} should have a dim model"
        instance = model_class.model_validate(valid_dims)
        for field_name, expected_value in valid_dims.items():
            assert getattr(instance, field_name) == expected_value


def test_per_event_models_reject_unknown_keys():
    """`extra="forbid"` is set on every per-event dim model."""
    for event, valid_dims in PER_EVENT_VALID_DIMS:
        model_class = DIMENSION_MODELS[event]
        assert model_class is not None
        bad_payload = {**valid_dims, "extra_key": "x"}
        with pytest.raises(ValidationError):
            model_class.model_validate(bad_payload)


def test_per_event_models_reject_unknown_literal_values():
    """A non-Literal value for a Literal field raises ValidationError."""
    with pytest.raises(ValidationError):
        DIMENSION_MODELS[EventName.UI_UTUB_NAME_EDIT_OPEN].model_validate(
            {"trigger": "pencil", "device_type": DeviceType.MOBILE}
        )


def test_per_event_models_reject_missing_required_keys():
    """Omitting a required field raises ValidationError."""
    with pytest.raises(ValidationError):
        DIMENSION_MODELS[EventName.UI_UTUB_NAME_EDIT_OPEN].model_validate({})


def test_api_hit_model_validates_endpoint_method_status_code():
    """`_DimApiHit` validates endpoint/method/status_code with strict typing."""
    api_hit_model = DIMENSION_MODELS[EventName.API_HIT]
    assert api_hit_model is not None

    # Happy path
    valid = api_hit_model.model_validate(
        {"endpoint": "/utubs", "method": "POST", "status_code": 200}
    )
    assert valid.endpoint == "/utubs"
    assert valid.method == "POST"
    assert valid.status_code == 200

    # Bad HTTP method
    with pytest.raises(ValidationError):
        api_hit_model.model_validate(
            {"endpoint": "/utubs", "method": "TEAPOT", "status_code": 200}
        )

    # status_code must be int (strict — no string coercion)
    with pytest.raises(ValidationError):
        api_hit_model.model_validate(
            {"endpoint": "/utubs", "method": "POST", "status_code": "200"}
        )


def test_get_all_dimension_keys_returns_union_of_ui_model_fields():
    """`get_all_dimension_keys()` returns sorted union of UI-category dim model fields."""
    expected: set[str] = set()
    for event_name, dim_model in DIMENSION_MODELS.items():
        if dim_model is None:
            continue
        if EVENT_CATEGORY[event_name] != EventCategory.UI:
            continue
        expected.update(dim_model.model_fields.keys())
    assert set(get_all_dimension_keys()) == expected
    assert get_all_dimension_keys() == tuple(sorted(expected))
