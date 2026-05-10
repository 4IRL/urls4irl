from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.metrics.dimension_models import DIMENSION_MODELS, validate_dimensions
from backend.metrics.events import EventName

pytestmark = pytest.mark.unit


# Table-driven cases — sourced from
# plans/anonymous-metrics-ingest/tmp/research-schemas.md (the §2b matrix).
# Each tuple: (EventName member, valid dimensions dict).
PER_EVENT_VALID_DIMS: tuple[tuple[EventName, dict], ...] = (
    (
        EventName.API_HIT,
        {"endpoint": "/utubs", "method": "POST", "status_code": 200},
    ),
    (EventName.UI_UTUB_SELECT, {"search_active": "true"}),
    (EventName.UI_UTUB_NAME_EDIT_OPEN, {"trigger": "pencil_icon"}),
    (EventName.UI_UTUB_DESC_EDIT_OPEN, {"trigger": "create_button"}),
    (
        EventName.UI_URL_ACCESS,
        {
            "trigger": "corner_button",
            "search_active": "false",
            "active_tag_count": 3,
        },
    ),
    (
        EventName.UI_URL_CARD_CLICK,
        {"search_active": "true", "active_tag_count": 0},
    ),
    (EventName.UI_URL_COPY, {"result": "success"}),
    (EventName.UI_SEARCH_OPEN, {"target": "urls"}),
    (EventName.UI_SEARCH_CLOSE, {"target": "utubs"}),
    (EventName.UI_TAG_CREATE_OPEN, {"scope": "utub"}),
    (EventName.UI_TAG_CREATE_OPEN, {"scope": "url"}),
    (EventName.UI_TAG_DELETE_OPEN, {"scope": "utub"}),
    (EventName.UI_TAG_DELETE_OPEN, {"scope": "url"}),
    (EventName.UI_TAG_DELETE_CONFIRM, {"scope": "utub"}),
    (EventName.UI_TAG_DELETE_CONFIRM, {"scope": "url"}),
    (EventName.UI_TAG_DELETE_CANCEL, {"scope": "utub"}),
    (EventName.UI_TAG_DELETE_CANCEL, {"scope": "url"}),
    (EventName.UI_FORM_SUBMIT, {"trigger": "enter_key", "form": "url_create"}),
    (EventName.UI_FORM_SUBMIT, {"trigger": "button_click", "form": "url_title_edit"}),
    (EventName.UI_FORM_SUBMIT, {"trigger": "enter_key", "form": "url_string_edit"}),
    (EventName.UI_FORM_SUBMIT, {"trigger": "button_click", "form": "utub_name_edit"}),
    (EventName.UI_FORM_SUBMIT, {"trigger": "enter_key", "form": "utub_desc_edit"}),
    (
        EventName.UI_FORM_CANCEL,
        {"trigger": "escape_key", "form": "tag_create"},
    ),
    (EventName.UI_VALIDATION_ERROR, {"form": "utub_create"}),
    (EventName.UI_VALIDATION_ERROR, {"form": "utub_name_edit"}),
    (EventName.UI_DECK_COLLAPSE, {"deck": "members"}),
    (EventName.UI_DECK_EXPAND, {"deck": "urls"}),
    (EventName.UI_MOBILE_NAV, {"target": "tags"}),
    (EventName.UI_AUTH_FORM_SWITCH, {"target": "register"}),
)


def test_every_eventname_member_has_an_entry():
    """Every member of `EventName` is keyed in `DIMENSION_MODELS`."""
    assert set(DIMENSION_MODELS.keys()) == set(EventName)


def test_none_entries_reject_non_empty_dimensions():
    """For events with `DIMENSION_MODELS[event] is None`, non-empty dims fail."""
    none_events = [event for event, model in DIMENSION_MODELS.items() if model is None]
    assert none_events, "expected at least one event with no dim model"
    for event in none_events:
        # Empty dict and None pass silently
        validate_dimensions(event, {})
        validate_dimensions(event, None)
        # Non-empty dict fails
        with pytest.raises(ValidationError):
            validate_dimensions(event, {"x": 1})


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
            {"trigger": "pencil"}
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
