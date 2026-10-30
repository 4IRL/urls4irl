from __future__ import annotations

from typing import Any

import pytest
from flask import Flask

import backend.cli.metrics as metrics_cli_module
import backend.extensions.metrics.middleware as middleware_module
import backend.metrics.flow_validation as flow_validation_module
from backend.metrics.dimension_models import DIMENSION_MODELS
from backend.metrics.event_registry import EVENT_REGISTRY
from backend.metrics.events import (
    DEVICE_TYPE_DIM_KEY,
    EVENT_CATEGORY,
    EventCategory,
    EventName,
)
from backend.metrics.flow_validation import (
    LenientFlowDefinition,
    inspect_flow_payload,
    serialize_flow_steps,
    validate_flow_definition,
    validate_flow_payload,
)
from backend.metrics.flows import FLOWS, FlowDefinition, FlowId
from backend.utils.strings.metric_flow_strs import (
    API_STEP_NO_EVENT_STR,
    BAD_FILTER_VALUE_STR,
    BAD_STATUS_CODE_STR,
    CANNOT_FILTER_STR,
    ENDPOINT_ONLY_API_STR,
    ENDPOINT_REQUIRED_STR,
    EVENT_REQUIRED_STR,
    METHOD_ONLY_API_STR,
    METHOD_REQUIRED_STR,
    WRONG_TYPE_OBJECT_STR,
    echo_input,
    group_by_not_available_message,
    unknown_endpoint_message,
    unknown_event_message,
    unknown_field_message,
    wrong_category_message,
)

pytestmark = pytest.mark.cli

UI_EVENT = EventName.UI_FORM_SUBMIT.value
UI_CANCEL_EVENT = EventName.UI_FORM_CANCEL.value
DOMAIN_EVENT = EventName.CROSS_UTUB_SEARCH_PERFORMED.value
POST_ENDPOINT = "urls.create_url"
GET_ENDPOINT = "utubs.get_single_utub"
CHOOSE_ALLOWED_POST = "Use one of: POST."


def _ui_step(**overrides: Any) -> dict[str, Any]:
    step: dict[str, Any] = {"stream": "ui", "label": "Open", "event_name": UI_EVENT}
    step.update(overrides)
    return step


def _api_step(**overrides: Any) -> dict[str, Any]:
    step: dict[str, Any] = {
        "stream": "api",
        "label": "Request",
        "api_endpoint": POST_ENDPOINT,
        "api_method": "POST",
    }
    step.update(overrides)
    return step


def _payload(*steps: dict[str, Any]) -> dict[str, Any]:
    return {"display_name": "My flow", "steps": list(steps) or [_ui_step(), _ui_step()]}


def _errors(*steps: dict[str, Any]) -> dict[str, list[str]]:
    result = validate_flow_payload(_payload(*steps))
    assert isinstance(result, dict), "expected an error map"
    return result


def _second(**overrides: Any) -> dict[str, Any]:
    return _ui_step(label="Second", **overrides)


def test_valid_payload_returns_flow_definition(app: Flask) -> None:
    result = validate_flow_payload(
        _payload(
            _ui_step(dim_filter=["form:url_create"]),
            _api_step(dim_filter=["status_code:200"]),
        )
    )
    assert isinstance(result, FlowDefinition)
    assert result.steps[0].event_name is EventName.UI_FORM_SUBMIT
    assert result.steps[0].dim_filter == [("form", "url_create")]
    assert result.steps[1].api_method == "POST"


def test_unknown_event_fails_without_raising(app: Flask) -> None:
    errors = _errors(_ui_step(), _second(event_name="removed_event"))
    assert errors == {
        "steps.1.event_name": [unknown_event_message(value="removed_event")]
    }


def test_unknown_breakdown_event_fails_at_breakdown_path(app: Flask) -> None:
    errors = _errors(
        _ui_step(),
        _second(drop_breakdown={"event_name": "gone", "group_by": "reason"}),
    )
    assert errors == {
        "steps.1.drop_breakdown.event_name": [unknown_event_message(value="gone")]
    }


def test_wrong_category_event_fails(app: Flask) -> None:
    errors = _errors(_ui_step(), _second(event_name=DOMAIN_EVENT))
    assert errors == {"steps.1.event_name": [wrong_category_message(stream="ui")]}


def test_ui_step_without_event_fails_and_skips_filters(app: Flask) -> None:
    step = _second(dim_filter=["nope:1"])
    del step["event_name"]
    assert _errors(_ui_step(), step) == {"steps.1.event_name": [EVENT_REQUIRED_STR]}


def test_ui_step_with_api_fields_fails_at_each_field(app: Flask) -> None:
    errors = _errors(_ui_step(), _second(api_endpoint=POST_ENDPOINT, api_method="POST"))
    assert errors == {
        "steps.1.api_endpoint": [ENDPOINT_ONLY_API_STR],
        "steps.1.api_method": [METHOD_ONLY_API_STR],
    }


def test_api_step_with_event_fails(app: Flask) -> None:
    errors = _errors(_ui_step(), _api_step(event_name=UI_EVENT))
    assert errors == {"steps.1.event_name": [API_STEP_NO_EVENT_STR]}


def test_api_step_missing_endpoint_and_method(app: Flask) -> None:
    errors = _errors(_ui_step(), {"stream": "api", "label": "Request"})
    assert errors == {
        "steps.1.api_endpoint": [ENDPOINT_REQUIRED_STR],
        "steps.1.api_method": [METHOD_REQUIRED_STR],
    }


def test_unknown_endpoint_skips_method_check(app: Flask) -> None:
    errors = _errors(
        _ui_step(), _api_step(api_endpoint="nope.nothing", api_method="post")
    )
    assert errors == {
        "steps.1.api_endpoint": [unknown_endpoint_message(value="nope.nothing")]
    }


@pytest.mark.parametrize("method", ["GET", "HEAD", "OPTIONS", "post", "PATCH"])
def test_method_not_allowed_for_post_route(app: Flask, method: str) -> None:
    errors = _errors(_ui_step(), _api_step(api_method=method))
    assert errors == {"steps.1.api_method": [CHOOSE_ALLOWED_POST]}


@pytest.mark.parametrize("method", ["HEAD", "OPTIONS"])
def test_head_and_options_rejected_on_get_route(app: Flask, method: str) -> None:
    errors = _errors(
        _ui_step(), _api_step(api_endpoint=GET_ENDPOINT, api_method=method)
    )
    assert list(errors) == ["steps.1.api_method"]
    assert "GET" in errors["steps.1.api_method"][0]
    assert "HEAD" not in errors["steps.1.api_method"][0]


@pytest.mark.parametrize("endpoint", ["static", "system.health", "metrics.ingest"])
def test_endpoints_api_hit_never_records_are_rejected(
    app: Flask, endpoint: str
) -> None:
    errors = _errors(_ui_step(), _api_step(api_endpoint=endpoint))
    assert errors == {
        "steps.1.api_endpoint": [unknown_endpoint_message(value=endpoint)]
    }


@pytest.mark.parametrize("key", ["endpoint", "method"])
def test_api_step_endpoint_method_filter_keys_rejected(app: Flask, key: str) -> None:
    errors = _errors(_ui_step(), _api_step(dim_filter=[f"{key}:x"]))
    assert errors == {"steps.1.dim_filter.0": [CANNOT_FILTER_STR]}


def test_api_step_status_code_filter_passes(app: Flask) -> None:
    result = validate_flow_payload(
        _payload(_ui_step(), _api_step(dim_filter=["status_code:200"]))
    )
    assert isinstance(result, FlowDefinition)


@pytest.mark.parametrize(
    "value",
    [
        " 200",
        "+200",
        "2_0_0",
        "0200",
        "99999999999999999999",
        "600",
        "99",
        "２００",
        "٢٠٠",
        "abc",
        "200 ",
    ],
)
def test_status_code_non_canonical_values_fail(app: Flask, value: str) -> None:
    errors = _errors(_ui_step(), _api_step(dim_filter=[f"status_code:{value}"]))
    assert errors == {"steps.1.dim_filter.0": [BAD_STATUS_CODE_STR]}


@pytest.mark.parametrize("value", ["100", "599"])
def test_status_code_boundaries_pass(app: Flask, value: str) -> None:
    result = validate_flow_payload(
        _payload(_ui_step(), _api_step(dim_filter=[f"status_code:{value}"]))
    )
    assert isinstance(result, FlowDefinition)


def test_unknown_dim_key_and_bad_value(app: Flask) -> None:
    errors = _errors(
        _ui_step(),
        _second(dim_filter=["nope:1", "form:not_a_form", "device_type:3"]),
    )
    assert errors == {
        "steps.1.dim_filter.0": [unknown_field_message(value="nope")],
        "steps.1.dim_filter.1": [BAD_FILTER_VALUE_STR],
        "steps.1.dim_filter.2": [BAD_FILTER_VALUE_STR],
    }


@pytest.mark.parametrize("value", ["1", "2"])
def test_device_type_values_pass(app: Flask, value: str) -> None:
    result = validate_flow_payload(
        _payload(_ui_step(), _second(dim_filter=[f"device_type:{value}"]))
    )
    assert isinstance(result, FlowDefinition)


@pytest.mark.parametrize("value", ["abc", "01", "1.0", " 1"])
def test_device_type_non_integer_strings_fail(app: Flask, value: str) -> None:
    errors = _errors(_ui_step(), _second(dim_filter=[f"device_type:{value}"]))
    assert errors == {"steps.1.dim_filter.0": [BAD_FILTER_VALUE_STR]}


def test_whitespace_only_dim_parts_are_rejected(app: Flask) -> None:
    """Filters with whitespace-only parts pass the lenient model but fail validation."""
    errors = _errors(_ui_step(), _second(dim_filter=["  :v", "form:  "]))
    assert errors == {
        "steps.1.dim_filter.0": [unknown_field_message(value="  ")],
        "steps.1.dim_filter.1": [BAD_FILTER_VALUE_STR],
    }


def _filterable_cases() -> list[tuple[EventName, str]]:
    cases: list[tuple[EventName, str]] = []
    for event_name, dim_model in DIMENSION_MODELS.items():
        if dim_model is None or EVENT_CATEGORY[event_name] is EventCategory.API:
            continue
        cases.extend((event_name, key) for key in dim_model.model_fields)
    return cases


def _api_cases() -> list[tuple[EventName, str]]:
    cases: list[tuple[EventName, str]] = []
    for event_name, dim_model in DIMENSION_MODELS.items():
        if dim_model is None or EVENT_CATEGORY[event_name] is not EventCategory.API:
            continue
        cases.extend((event_name, key) for key in dim_model.model_fields)
    return cases


def test_sweeps_are_not_vacuous() -> None:
    non_api = _filterable_cases()
    closed = [
        case
        for case in non_api
        if case[1] != DEVICE_TYPE_DIM_KEY
        and EVENT_REGISTRY[case[0]].dimensions.get(case[1])
    ]
    cannot_filter = [
        case
        for case in non_api
        if case[1] != DEVICE_TYPE_DIM_KEY
        and not EVENT_REGISTRY[case[0]].dimensions.get(case[1])
    ]
    assert closed
    assert cannot_filter
    assert any(key == DEVICE_TYPE_DIM_KEY for _, key in non_api)
    assert _api_cases()


@pytest.mark.parametrize(
    "event_name,dim_key",
    _api_cases(),
    ids=lambda value: getattr(value, "value", value),
)
def test_api_event_dim_keys_follow_api_rules(
    app: Flask, event_name: EventName, dim_key: str
) -> None:
    def breakdown(value: str) -> dict[str, Any]:
        return _second(
            drop_breakdown={
                "event_name": event_name.value,
                "dim_filter": [f"{dim_key}:{value}"],
                "group_by": "endpoint",
            }
        )

    path = "steps.1.drop_breakdown.dim_filter.0"
    group_by_path = "steps.1.drop_breakdown.group_by"

    def errors_for(value: str) -> dict[str, list[str]]:
        errors = _errors(_ui_step(), breakdown(value))
        if event_name is not EventName.API_HIT:
            # The fixed `group_by: endpoint` is not groupable for these events.
            assert errors.pop(group_by_path) == [
                group_by_not_available_message(group_by="endpoint", allowed=[])
            ]
        return errors

    if dim_key == "status_code":
        if event_name is EventName.API_HIT:
            ok = validate_flow_payload(_payload(_ui_step(), breakdown("200")))
            assert isinstance(ok, FlowDefinition)
        else:
            assert errors_for("200") == {}
        assert errors_for("600") == {path: [BAD_STATUS_CODE_STR]}
    elif dim_key in ("endpoint", "method"):
        assert errors_for("x") == {path: [CANNOT_FILTER_STR]}
    else:
        assert errors_for("x") == {path: [unknown_field_message(value=dim_key)]}


@pytest.mark.parametrize(
    "event_name,dim_key",
    _filterable_cases(),
    ids=lambda value: getattr(value, "value", value),
)
def test_every_dim_key_has_a_rule_or_is_rejected_fail_closed(
    app: Flask, event_name: EventName, dim_key: str
) -> None:
    category = EVENT_CATEGORY[event_name].value
    step = {"stream": category, "label": "Probe", "event_name": event_name.value}
    closed_set = EVENT_REGISTRY[event_name].dimensions.get(dim_key)
    if dim_key == DEVICE_TYPE_DIM_KEY:
        good, bad = "1", "9"
    elif closed_set is not None and len(closed_set) > 0:
        good, bad = closed_set[0], "definitely_not_allowed"
    else:
        errors = _errors(_ui_step(), {**step, "dim_filter": [f"{dim_key}:anything"]})
        assert errors == {"steps.1.dim_filter.0": [CANNOT_FILTER_STR]}
        return
    ok = validate_flow_payload(
        _payload(_ui_step(), {**step, "dim_filter": [f"{dim_key}:{good}"]})
    )
    assert isinstance(ok, FlowDefinition)
    errors = _errors(_ui_step(), {**step, "dim_filter": [f"{dim_key}:{bad}"]})
    assert errors == {"steps.1.dim_filter.0": [BAD_FILTER_VALUE_STR]}


def test_active_tag_count_is_rejected_by_name(app: Flask) -> None:
    event_name = next(
        name
        for name, dim_model in DIMENSION_MODELS.items()
        if dim_model is not None and "active_tag_count" in dim_model.model_fields
    )
    step = {
        "stream": EVENT_CATEGORY[event_name].value,
        "label": "Tags",
        "event_name": event_name.value,
        "dim_filter": ["active_tag_count:3"],
    }
    assert _errors(_ui_step(), step) == {"steps.1.dim_filter.0": [CANNOT_FILTER_STR]}


def test_unknown_event_with_bad_filter_reports_only_event(app: Flask) -> None:
    errors = _errors(_ui_step(), _second(event_name="gone", dim_filter=["x:1"]))
    assert list(errors) == ["steps.1.event_name"]


def test_wrong_category_with_bad_filter_reports_only_event(app: Flask) -> None:
    errors = _errors(_ui_step(), _second(event_name=DOMAIN_EVENT, dim_filter=["x:1"]))
    assert list(errors) == ["steps.1.event_name"]


def test_unknown_breakdown_event_skips_filter_and_group_by(app: Flask) -> None:
    errors = _errors(
        _ui_step(),
        _second(
            drop_breakdown={
                "event_name": "gone",
                "dim_filter": ["x:1"],
                "group_by": "nope",
            }
        ),
    )
    assert list(errors) == ["steps.1.drop_breakdown.event_name"]


def test_bad_breakdown_filter_and_group_by(app: Flask) -> None:
    errors = _errors(
        _ui_step(),
        _second(
            drop_breakdown={
                "event_name": UI_CANCEL_EVENT,
                "dim_filter": ["form:url_create", "x:1"],
                "group_by": "nope",
            }
        ),
    )
    assert errors == {
        "steps.1.drop_breakdown.dim_filter.1": [unknown_field_message(value="x")],
        "steps.1.drop_breakdown.group_by": [unknown_field_message(value="nope")],
    }


@pytest.mark.parametrize(
    "entries",
    [
        ["form:url_create", "form:utub_create"],
        ["form:url_create", "form:url_create"],
    ],
)
def test_duplicate_dim_key_fails_at_later_entry(app: Flask, entries: list[str]) -> None:
    duplicate = 'Only one filter per field; "form" is already used.'
    step_errors = _errors(_ui_step(), _second(dim_filter=entries))
    assert step_errors == {"steps.1.dim_filter.1": [duplicate]}
    breakdown_errors = _errors(
        _ui_step(),
        _second(
            drop_breakdown={
                "event_name": UI_CANCEL_EVENT,
                "dim_filter": entries,
                "group_by": "trigger",
            }
        ),
    )
    assert breakdown_errors == {"steps.1.drop_breakdown.dim_filter.1": [duplicate]}


def test_repeated_unknown_key_reports_only_unknown_key(app: Flask) -> None:
    errors = _errors(_ui_step(), _second(dim_filter=["nope:1", "nope:2"]))
    assert errors == {
        "steps.1.dim_filter.0": [unknown_field_message(value="nope")],
        "steps.1.dim_filter.1": [unknown_field_message(value="nope")],
    }


def test_duplicate_step_labels_are_accepted(app: Flask) -> None:
    result = validate_flow_payload(
        _payload(_ui_step(label="Same"), _ui_step(label="Same"))
    )
    assert isinstance(result, FlowDefinition)


@pytest.mark.parametrize(
    "event_name",
    [EventName.API_HIT.value, EventName.API_METRICS_INGEST_BATCH.value],
)
def test_api_category_breakdown_rules(app: Flask, event_name: str) -> None:
    def breakdown(**overrides: Any) -> dict[str, Any]:
        value: dict[str, Any] = {"event_name": event_name, "group_by": "endpoint"}
        value.update(overrides)
        return _second(drop_breakdown=value)

    group_by_path = "steps.1.drop_breakdown.group_by"
    filter_path = "steps.1.drop_breakdown.dim_filter.0"
    # Only API_HIT is exempt from the group_by registry; every other API event
    # is refused with the distinct "cannot break down" message.
    exempt = event_name == EventName.API_HIT.value
    not_groupable = {
        group_by_path: [group_by_not_available_message(group_by="endpoint", allowed=[])]
    }

    def filter_errors(**overrides: Any) -> dict[str, list[str]]:
        errors = _errors(_ui_step(), breakdown(**overrides))
        if not exempt:
            assert errors.pop(group_by_path) == not_groupable[group_by_path]
        return errors

    for group_by in ("endpoint", "method", "status_code"):
        result = validate_flow_payload(
            _payload(_ui_step(), breakdown(group_by=group_by))
        )
        if exempt:
            assert isinstance(result, FlowDefinition)
        else:
            assert result == {
                group_by_path: [
                    group_by_not_available_message(group_by=group_by, allowed=[])
                ]
            }
    errors = _errors(_ui_step(), breakdown(group_by="trigger"))
    assert errors == {group_by_path: [unknown_field_message(value="trigger")]}
    for key in ("endpoint", "method"):
        assert filter_errors(dim_filter=[f"{key}:x"]) == {
            filter_path: [CANNOT_FILTER_STR]
        }
    ok = validate_flow_payload(
        _payload(_ui_step(), breakdown(dim_filter=["status_code:200"]))
    )
    if exempt:
        assert isinstance(ok, FlowDefinition)
    else:
        assert isinstance(ok, dict)
        assert set(ok) == {group_by_path}
    assert filter_errors(dim_filter=["status_code:600"]) == {
        filter_path: [BAD_STATUS_CODE_STR]
    }


def test_unregistered_group_by_gets_distinct_message_naming_allowed(
    app: Flask,
) -> None:
    """
    GIVEN a declared dim that is not a registered projection
    WHEN the flow is validated
    THEN the field error is the "cannot break down" text, distinct from the
         unknown-dim text, and registered dims are accepted.
    """
    path = "steps.1.drop_breakdown.group_by"

    def breakdown(group_by: str) -> dict[str, Any]:
        return _second(
            drop_breakdown={"event_name": UI_CANCEL_EVENT, "group_by": group_by}
        )

    errors = _errors(_ui_step(), breakdown("form"))
    assert errors == {
        path: [
            'Cannot break down this event by "form". Allowed: "trigger". '
            "Choose one or remove the breakdown."
        ]
    }
    unknown = _errors(_ui_step(), breakdown("zzz"))
    assert unknown == {path: [unknown_field_message(value="zzz")]}
    assert unknown[path] != errors[path]
    assert isinstance(
        validate_flow_payload(_payload(_ui_step(), breakdown("trigger"))),
        FlowDefinition,
    )


def test_event_without_single_key_projection_cannot_be_broken_down(
    app: Flask,
) -> None:
    """
    GIVEN a breakdown on API_METRICS_INGEST_BATCH (multi-key projection only)
    THEN the group_by error is "This event cannot be broken down."
    """
    errors = _errors(
        _ui_step(),
        _second(
            drop_breakdown={
                "event_name": EventName.API_METRICS_INGEST_BATCH.value,
                "group_by": "endpoint",
            }
        ),
    )
    assert errors == {
        "steps.1.drop_breakdown.group_by": ["This event cannot be broken down."]
    }


def test_breakdown_event_category_may_differ_from_step(app: Flask) -> None:
    result = validate_flow_payload(
        _payload(
            _ui_step(),
            _api_step(
                drop_breakdown={
                    "event_name": UI_CANCEL_EVENT,
                    "dim_filter": ["form:url_create"],
                    "group_by": "trigger",
                }
            ),
        )
    )
    assert isinstance(result, FlowDefinition)


def test_messages_do_not_echo_valid_keys_list(app: Flask) -> None:
    errors = _errors(_ui_step(), _second(dim_filter=["nope:1"]))
    assert "Valid keys" not in errors["steps.1.dim_filter.0"][0]


@pytest.mark.parametrize(
    "path,step",
    [
        ("steps.1.event_name", _second(event_name="a\nb")),
        ("steps.1.api_endpoint", _api_step(api_endpoint="a\nb")),
        ("steps.1.dim_filter.0", _second(dim_filter=["a\nb:1"])),
    ],
    ids=["event_name", "api_endpoint", "dim_key"],
)
def test_echoed_input_is_repr_style_and_escaped(
    app: Flask, path: str, step: dict[str, Any]
) -> None:
    errors = _errors(_ui_step(), step)
    message = errors[path][0]
    assert "'a\\nb" in message
    assert "\n" not in message


def test_filter_value_splits_on_first_colon(app: Flask) -> None:
    errors = _errors(_ui_step(), _second(dim_filter=["form:a:b"]))
    assert errors == {"steps.1.dim_filter.0": [BAD_FILTER_VALUE_STR]}


def test_get_method_passes_on_get_endpoint(app: Flask) -> None:
    result = validate_flow_payload(
        _payload(_ui_step(), _api_step(api_endpoint=GET_ENDPOINT, api_method="GET"))
    )
    assert isinstance(result, FlowDefinition)


def test_api_step_endpoint_only_and_method_only(app: Flask) -> None:
    no_method = _api_step()
    del no_method["api_method"]
    no_endpoint = _api_step()
    del no_endpoint["api_endpoint"]
    assert _errors(_ui_step(), no_method) == {
        "steps.1.api_method": [METHOD_REQUIRED_STR]
    }
    assert _errors(_ui_step(), no_endpoint) == {
        "steps.1.api_endpoint": [ENDPOINT_REQUIRED_STR]
    }


def test_duplicate_status_code_on_api_step(app: Flask) -> None:
    errors = _errors(
        _ui_step(), _api_step(dim_filter=["status_code:200", "status_code:404"])
    )
    assert list(errors) == ["steps.1.dim_filter.1"]


def test_echoed_input_is_truncated_before_repr(app: Flask) -> None:
    draft = LenientFlowDefinition.model_validate(_payload())
    draft.steps[1].event_name = "a" * 300
    result = validate_flow_definition(draft)
    assert isinstance(result, dict)
    assert result["steps.1.event_name"] == [
        f"Event {repr('a' * 255 + '...')} does not exist."
    ]
    assert echo_input("a" * 255) == repr("a" * 255)


def test_allowed_method_set_is_shared_and_pinned(app: Flask) -> None:
    shared = middleware_module.API_HIT_COUNTED_METHODS
    assert metrics_cli_module.API_HIT_COUNTED_METHODS is shared
    assert flow_validation_module.API_HIT_COUNTED_METHODS is shared
    assert shared == frozenset({"GET", "POST", "PATCH", "PUT", "DELETE"})
    assert "HEAD" not in shared
    assert "OPTIONS" not in shared


def test_three_bad_fields_return_three_keys(app: Flask) -> None:
    errors = _errors(
        _ui_step(event_name="gone"),
        _second(dim_filter=["nope:1"]),
        _api_step(api_endpoint="nope.nothing"),
    )
    assert sorted(errors) == [
        "steps.0.event_name",
        "steps.1.dim_filter.0",
        "steps.2.api_endpoint",
    ]


def test_non_dict_payload_returns_root_error(app: Flask) -> None:
    result = validate_flow_payload(["not", "a", "dict"])
    assert isinstance(result, dict)
    assert result == {"__root__": [WRONG_TYPE_OBJECT_STR]}
    assert inspect_flow_payload(None) == (None, result)


def test_structural_error_short_circuits_registry_layer(app: Flask) -> None:
    payload = _payload(_ui_step(event_name="gone"), _ui_step(label=""))
    result = validate_flow_payload(payload)
    assert isinstance(result, dict)
    assert list(result) == ["steps.1.label"]
    draft, errors = inspect_flow_payload(payload)
    assert draft is None
    assert errors == result


def test_inspect_flow_payload_registry_errors_and_valid(app: Flask) -> None:
    bad = _payload(_ui_step(event_name="gone"), _ui_step())
    draft, errors = inspect_flow_payload(bad)
    assert isinstance(draft, LenientFlowDefinition)
    assert list(errors) == ["steps.0.event_name"]
    assert validate_flow_payload(bad) == errors
    good_draft, good_errors = inspect_flow_payload(_payload())
    assert isinstance(good_draft, LenientFlowDefinition)
    assert good_errors == {}


def test_registry_layer_runs_once_per_call(
    app: Flask, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[LenientFlowDefinition] = []
    original = flow_validation_module.validate_flow_definition

    def spy(draft: LenientFlowDefinition) -> FlowDefinition | dict[str, list[str]]:
        calls.append(draft)
        return original(draft)

    monkeypatch.setattr(flow_validation_module, "validate_flow_definition", spy)
    validate_flow_payload(_payload())
    assert len(calls) == 1
    inspect_flow_payload(_payload())
    assert len(calls) == 2
    calls.clear()
    validate_flow_payload(["not", "a", "dict"])
    validate_flow_payload(_payload(_ui_step(label="")))
    inspect_flow_payload(None)
    assert calls == []


def test_invalid_returns_dict_and_valid_returns_enum_typed_definition(
    app: Flask,
) -> None:
    assert isinstance(validate_flow_payload(_payload(_ui_step(event_name="x"))), dict)
    result = validate_flow_payload(
        _payload(_ui_step(dim_filter=["form:url_create"]), _ui_step())
    )
    assert isinstance(result, FlowDefinition)
    assert isinstance(result.steps[0].event_name, EventName)
    assert isinstance(result.steps[0].dim_filter[0], tuple)


@pytest.mark.parametrize("flow_id", list(FlowId))
def test_builtin_flows_round_trip_through_both_layers(
    app: Flask, flow_id: FlowId
) -> None:
    builtin = FLOWS[flow_id]
    payload = {"display_name": builtin.display_name, **serialize_flow_steps(builtin)}
    assert validate_flow_payload(payload) == builtin
