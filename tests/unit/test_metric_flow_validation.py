import copy
from typing import Any

import pytest
from pydantic import ValidationError

from backend.api_common.request_errors import humanize_error_message, max_length_message
from backend.metrics.flow_limits import FLOW_LIMITS
from backend.metrics.flow_validation import (
    LenientFlowDefinition,
    flow_errors_from_validation_error,
    serialize_flow_steps,
)
from backend.metrics.flows import FLOWS, FlowId
from backend.utils.strings.json_strs import FIELD_REQUIRED_STR
from backend.utils.strings.metric_flow_strs import (
    FILTER_FORMAT_STR,
    NAME_CHARACTERS_STR,
)

pytestmark = pytest.mark.unit

MAX_ID = FLOW_LIMITS.IDENTIFIER_MAX_LENGTH
ENTER_TEXT = "Enter text."
ENTER_LIST = "Enter a list of items."
ENTER_OBJECT = "Enter an object."


def _step(**overrides: Any) -> dict[str, Any]:
    step: dict[str, Any] = {"stream": "ui", "label": "Open", "event_name": "x_event"}
    step.update(overrides)
    return step


def _payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "display_name": "My flow",
        "steps": [_step(), _step(label="Submit")],
    }
    payload.update(overrides)
    return payload


def _errors(payload: dict[str, Any]) -> dict[str, list[str]]:
    with pytest.raises(ValidationError) as exc_info:
        LenientFlowDefinition.model_validate(payload)
    return flow_errors_from_validation_error(exc_info.value)


def _with_step(**overrides: Any) -> dict[str, Any]:
    return _payload(steps=[_step(), _step(**overrides)])


def _breakdown(**overrides: Any) -> dict[str, Any]:
    breakdown: dict[str, Any] = {"event_name": "gone_event", "group_by": "reason"}
    breakdown.update(overrides)
    return breakdown


def test_removed_event_hydrates_unchanged() -> None:
    payload = _payload(
        steps=[
            _step(event_name="removed_event"),
            _step(drop_breakdown=_breakdown(event_name="removed_breakdown_event")),
        ]
    )
    flow = LenientFlowDefinition.model_validate(payload)
    assert flow.steps[0].event_name == "removed_event"
    assert flow.steps[1].drop_breakdown is not None
    assert flow.steps[1].drop_breakdown.event_name == "removed_breakdown_event"


@pytest.mark.parametrize(
    ("count", "message"),
    [(1, "Add at least 2 steps."), (9, "Use at most 8 steps.")],
)
def test_step_count_out_of_range(count: int, message: str) -> None:
    errors = _errors(_payload(steps=[_step() for _ in range(count)]))
    assert errors == {"steps": [message]}


@pytest.mark.parametrize("count", [FLOW_LIMITS.MIN_STEPS, FLOW_LIMITS.MAX_STEPS])
def test_step_count_boundaries_accepted(count: int) -> None:
    flow = LenientFlowDefinition.model_validate(
        _payload(steps=[_step() for _ in range(count)])
    )
    assert len(flow.steps) == count


def test_too_many_step_filters() -> None:
    filters = [f"d{index}:v" for index in range(FLOW_LIMITS.MAX_FILTERS + 1)]
    errors = _errors(_with_step(dim_filter=filters))
    assert errors == {"steps.1.dim_filter": ["Use at most 5 filters."]}


def test_too_many_breakdown_filters() -> None:
    filters = [f"d{index}:v" for index in range(FLOW_LIMITS.MAX_FILTERS + 1)]
    errors = _errors(_with_step(drop_breakdown=_breakdown(dim_filter=filters)))
    assert errors == {"steps.1.drop_breakdown.dim_filter": ["Use at most 5 filters."]}


def test_filter_count_boundary_accepted() -> None:
    filters = [f"d{index}:v" for index in range(FLOW_LIMITS.MAX_FILTERS)]
    flow = LenientFlowDefinition.model_validate(
        _with_step(dim_filter=filters, drop_breakdown=_breakdown(dim_filter=filters))
    )
    assert flow.steps[1].dim_filter == filters


def test_name_and_label_too_long() -> None:
    errors = _errors(
        _payload(
            display_name="a" * (FLOW_LIMITS.NAME_MAX_LENGTH + 1),
            steps=[_step(), _step(label="b" * (FLOW_LIMITS.LABEL_MAX_LENGTH + 1))],
        )
    )
    assert errors == {
        "display_name": [max_length_message(FLOW_LIMITS.NAME_MAX_LENGTH)],
        "steps.1.label": [max_length_message(FLOW_LIMITS.LABEL_MAX_LENGTH)],
    }


@pytest.mark.parametrize(
    ("length_name", "length_label"),
    [(1, 1), (FLOW_LIMITS.NAME_MAX_LENGTH, FLOW_LIMITS.LABEL_MAX_LENGTH)],
    ids=["min", "max"],
)
def test_name_and_label_length_boundaries_accepted(
    length_name: int, length_label: int
) -> None:
    flow = LenientFlowDefinition.model_validate(
        _payload(
            display_name="n" * length_name,
            steps=[_step(label="l" * length_label), _step()],
        )
    )
    assert len(flow.display_name) == length_name
    assert len(flow.steps[0].label) == length_label


@pytest.mark.parametrize("blank", ["", "   ", "\t \n"])
def test_blank_name_and_label_read_required(blank: str) -> None:
    errors = _errors(_payload(display_name=blank, steps=[_step(label=blank), _step()]))
    assert errors == {
        "display_name": [FIELD_REQUIRED_STR],
        "steps.0.label": [FIELD_REQUIRED_STR],
    }


def test_nbsp_only_name_and_label_read_required() -> None:
    nbsp = "\u00a0\u00a0"
    errors = _errors(_payload(display_name=nbsp, steps=[_step(label=nbsp), _step()]))
    assert errors == {
        "display_name": [FIELD_REQUIRED_STR],
        "steps.0.label": [FIELD_REQUIRED_STR],
    }


def test_name_and_label_are_trimmed() -> None:
    flow = LenientFlowDefinition.model_validate(
        _payload(display_name="  Foo  ", steps=[_step(label="\tBar\n"), _step()])
    )
    assert flow.display_name == "Foo"
    assert flow.steps[0].label == "Bar"
    flow = LenientFlowDefinition.model_validate(_payload(display_name="\tFoo\n"))
    assert flow.display_name == "Foo"


def test_leading_trailing_line_separator_is_trimmed() -> None:
    flow = LenientFlowDefinition.model_validate(
        _payload(
            display_name="\u2028Foo\u2028", steps=[_step(label="\u2028Bar"), _step()]
        )
    )
    assert flow.display_name == "Foo"
    assert flow.steps[0].label == "Bar"


@pytest.mark.parametrize(
    "bad",
    ["a\nb", "a\tb", "a\x00b", "a\u2028b", "a\u2029b", "a\u0085b"],
    ids=["newline", "tab", "nul", "u2028", "u2029", "u0085"],
)
def test_internal_control_characters_rejected(bad: str) -> None:
    errors = _errors(_payload(display_name=bad, steps=[_step(label=bad), _step()]))
    assert errors == {
        "display_name": [NAME_CHARACTERS_STR],
        "steps.0.label": [NAME_CHARACTERS_STR],
    }
    assert NAME_CHARACTERS_STR == "Use letters, numbers and punctuation only."


def test_zero_width_space_accepted() -> None:
    flow = LenientFlowDefinition.model_validate(_payload(display_name="a\u200bb"))
    assert flow.display_name == "a\u200bb"


def test_filter_value_too_long() -> None:
    long_value = "x" * (FLOW_LIMITS.FILTER_VALUE_MAX_LENGTH + 1)
    errors = _errors(_with_step(dim_filter=[f"form:{long_value}"]))
    assert errors == {
        "steps.1.dim_filter.0": [
            max_length_message(FLOW_LIMITS.FILTER_VALUE_MAX_LENGTH)
        ]
    }


def test_filter_dim_too_long_step_and_breakdown() -> None:
    long_dim = "d" * (MAX_ID + 1)
    errors = _errors(
        _with_step(
            dim_filter=[f"{long_dim}:v"],
            drop_breakdown=_breakdown(dim_filter=[f"{long_dim}:v"]),
        )
    )
    expected = [max_length_message(MAX_ID)]
    assert errors == {
        "steps.1.dim_filter.0": expected,
        "steps.1.drop_breakdown.dim_filter.0": expected,
    }


@pytest.mark.parametrize(
    "entry", ["nocolon", ":value", "dim:"], ids=["no-colon", "empty-dim", "empty-value"]
)
def test_malformed_filter_entries(entry: str) -> None:
    errors = _errors(
        _with_step(dim_filter=[entry], drop_breakdown=_breakdown(dim_filter=[entry]))
    )
    assert errors == {
        "steps.1.dim_filter.0": [FILTER_FORMAT_STR],
        "steps.1.drop_breakdown.dim_filter.0": [FILTER_FORMAT_STR],
    }


def test_filter_boundaries_accepted() -> None:
    entry = f"{'d' * MAX_ID}:{'v' * FLOW_LIMITS.FILTER_VALUE_MAX_LENGTH}"
    flow = LenientFlowDefinition.model_validate(
        _with_step(dim_filter=[entry], drop_breakdown=_breakdown(dim_filter=[entry]))
    )
    assert flow.steps[1].dim_filter == [entry]


def test_filter_value_may_contain_colons() -> None:
    flow = LenientFlowDefinition.model_validate(
        _with_step(dim_filter=["endpoint:a:b:c"])
    )
    assert flow.steps[1].dim_filter == ["endpoint:a:b:c"]


def test_unknown_key_forbidden() -> None:
    assert _errors(_payload(extra=1)) == {"extra": ["Unexpected field."]}
    errors = _errors(_with_step(foo=1, drop_breakdown=_breakdown(bar=2)))
    assert errors == {
        "steps.1.foo": ["Unexpected field."],
        "steps.1.drop_breakdown.bar": ["Unexpected field."],
    }


def test_wrong_type_inputs() -> None:
    assert _errors(_payload(display_name=123)) == {"display_name": [ENTER_TEXT]}
    assert _errors(_with_step(label=None)) == {"steps.1.label": [ENTER_TEXT]}
    assert _errors(_payload(steps="x")) == {"steps": [ENTER_LIST]}
    assert _errors(_with_step(dim_filter="x")) == {"steps.1.dim_filter": [ENTER_LIST]}
    assert _errors(_with_step(dim_filter=["a:b", 5])) == {
        "steps.1.dim_filter.1": [ENTER_TEXT]
    }
    assert _errors(_with_step(drop_breakdown=_breakdown(dim_filter=[5]))) == {
        "steps.1.drop_breakdown.dim_filter.0": [ENTER_TEXT]
    }


def test_missing_fields() -> None:
    step = _step()
    del step["label"]
    assert _errors(_payload(steps=[step, _step()])) == {
        "steps.0.label": [FIELD_REQUIRED_STR]
    }
    payload = _payload()
    del payload["steps"]
    assert _errors(payload) == {"steps": [FIELD_REQUIRED_STR]}
    breakdown = _breakdown()
    del breakdown["group_by"]
    assert _errors(_with_step(drop_breakdown=breakdown)) == {
        "steps.1.drop_breakdown.group_by": [FIELD_REQUIRED_STR]
    }


@pytest.mark.parametrize("field", ["event_name", "api_endpoint", "api_method"])
def test_step_identifier_over_limit_fails_at_own_path(field: str) -> None:
    over = "i" * (MAX_ID + 1)
    errors = _errors(_with_step(**{field: over}))
    assert errors == {f"steps.1.{field}": [max_length_message(MAX_ID)]}


def test_breakdown_group_by_over_limit() -> None:
    over = "i" * (MAX_ID + 1)
    errors = _errors(_with_step(drop_breakdown=_breakdown(group_by=over)))
    assert errors == {"steps.1.drop_breakdown.group_by": [max_length_message(MAX_ID)]}


def test_breakdown_event_name_over_limit() -> None:
    over = "i" * (MAX_ID + 1)
    errors = _errors(_with_step(drop_breakdown=_breakdown(event_name=over)))
    assert errors == {"steps.1.drop_breakdown.event_name": [max_length_message(MAX_ID)]}


def test_identifiers_at_limit_accepted() -> None:
    at_limit = "i" * MAX_ID
    flow = LenientFlowDefinition.model_validate(
        _with_step(
            event_name=at_limit,
            api_endpoint=at_limit,
            api_method=at_limit,
            drop_breakdown=_breakdown(event_name=at_limit, group_by=at_limit),
        )
    )
    assert flow.steps[1].api_method == at_limit


def test_invalid_stream_literal() -> None:
    assert _errors(_with_step(stream="mobile")) == {
        "steps.1.stream": ["Choose a step type."]
    }


def test_non_object_step_and_breakdown() -> None:
    assert _errors(_payload(steps=[5, _step()])) == {"steps.0": [ENTER_OBJECT]}
    assert _errors(_with_step(drop_breakdown=5)) == {
        "steps.1.drop_breakdown": [ENTER_OBJECT]
    }


def test_missing_stream_reads_required() -> None:
    step = _step()
    del step["stream"]
    assert _errors(_payload(steps=[step, _step()])) == {
        "steps.0.stream": [FIELD_REQUIRED_STR]
    }


def test_null_dim_filter_hydrates_as_no_filters() -> None:
    flow = LenientFlowDefinition.model_validate(_with_step(dim_filter=None))
    assert flow.steps[1].dim_filter is None


def test_empty_loc_maps_to_root_key() -> None:
    error = ValidationError.from_exception_data(
        "Flow",
        [
            {
                "type": "value_error",
                "loc": (),
                "input": 1,
                "ctx": {"error": ValueError("boom")},
            }
        ],
    )
    assert flow_errors_from_validation_error(error) == {"__root__": ["boom"]}


def test_dict_type_error_maps_to_enter_object() -> None:
    error = ValidationError.from_exception_data(
        "Flow", [{"type": "dict_type", "loc": ("steps", 0), "input": 1}]
    )
    assert flow_errors_from_validation_error(error) == {"steps.0": [ENTER_OBJECT]}


def test_length_error_on_unknown_segment_falls_back_to_humanized_text() -> None:
    error = ValidationError.from_exception_data(
        "Flow",
        [
            {
                "type": "too_long",
                "loc": ("display_name",),
                "input": [1, 2, 3, 4],
                "ctx": {"field_type": "List", "max_length": 3, "actual_length": 4},
            }
        ],
    )
    raw = error.errors(include_url=False)[0]["msg"]
    assert flow_errors_from_validation_error(error) == {
        "display_name": [humanize_error_message(raw)]
    }


def test_multiple_errors_collected_with_full_paths() -> None:
    errors = _errors(
        _payload(
            display_name="",
            steps=[_step(label=""), _step(dim_filter=["bad"])],
        )
    )
    assert set(errors) == {"display_name", "steps.0.label", "steps.1.dim_filter.0"}


@pytest.mark.parametrize("flow_id", list(FLOWS))
def test_builtin_flows_serialize_and_hydrate(flow_id: FlowId) -> None:
    definition = FLOWS[flow_id]
    serialized = serialize_flow_steps(definition)
    stored = {"display_name": definition.display_name, **serialized}
    hydrated = LenientFlowDefinition.model_validate(copy.deepcopy(stored))
    assert hydrated.display_name == definition.display_name
    assert len(hydrated.steps) == len(definition.steps)

    for source, stored_step, loaded in zip(
        definition.steps, serialized["steps"], hydrated.steps
    ):
        assert None not in stored_step.values()
        assert loaded.label == source.label
        assert loaded.event_name == source.event_name
        expected_filters = [f"{dim}:{value}" for dim, value in source.dim_filter or []]
        assert stored_step.get("dim_filter", []) == expected_filters
        assert (loaded.dim_filter or []) == expected_filters
        breakdown = stored_step.get("drop_breakdown")
        if source.drop_breakdown is None:
            assert breakdown is None
            continue
        assert isinstance(breakdown, dict)
        assert None not in breakdown.values()
        expected_breakdown_filters = [
            f"{dim}:{value}" for dim, value in source.drop_breakdown.dim_filter or []
        ]
        assert breakdown.get("dim_filter", []) == expected_breakdown_filters
        assert loaded.drop_breakdown is not None
        assert loaded.drop_breakdown.group_by == source.drop_breakdown.group_by


def test_serialize_omits_none_and_formats_filters() -> None:
    stored = serialize_flow_steps(FLOWS[FlowId.CREATE_UTUB])
    submit = stored["steps"][1]
    assert submit["dim_filter"] == ["form:utub_create"]
    assert isinstance(submit["drop_breakdown"], dict)
    assert submit["drop_breakdown"]["dim_filter"] == ["form:utub_create"]
    assert "api_endpoint" not in stored["steps"][0]
    assert "dim_filter" not in stored["steps"][0]
