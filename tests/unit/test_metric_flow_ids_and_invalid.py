import re

import pytest

from backend.metrics.flow_invalid import first_invalid_detail, flow_invalid_response
from backend.metrics.flows import (
    ALL_FLOW_IDS,
    CUSTOM_FLOW_ID_PREFIX,
    FLOW_ID_PATTERN,
    FlowId,
    format_custom_flow_id,
    parse_custom_flow_id,
)
from backend.utils.strings.metric_flow_strs import FLOW_INVALID_UNKNOWN_STR

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "flow_id,expected",
    [("custom_1", 1), ("custom_999999999", 999999999), ("custom_42", 42)],
)
def test_parse_custom_flow_id_accepts_valid(flow_id, expected):
    assert parse_custom_flow_id(flow_id) == expected


@pytest.mark.parametrize(
    "flow_id",
    [
        "custom_0",
        "custom_007",
        "custom_-1",
        "custom_abc",
        "custom_1000000000",
        "custom_2147483648",
        "Custom_1",
        "custom_1\n",
        "",
        *ALL_FLOW_IDS,
    ],
)
def test_parse_custom_flow_id_rejects_invalid(flow_id):
    assert parse_custom_flow_id(flow_id) is None


def test_format_custom_flow_id_round_trips():
    assert format_custom_flow_id(7) == "custom_7"
    assert parse_custom_flow_id(format_custom_flow_id(7)) == 7


def test_no_built_in_flow_id_uses_custom_prefix():
    assert not any(member.value.startswith(CUSTOM_FLOW_ID_PREFIX) for member in FlowId)


def test_flow_id_pattern_matches_built_ins_and_custom_only():
    for flow_id in ALL_FLOW_IDS:
        assert re.fullmatch(FLOW_ID_PATTERN, flow_id)
    assert re.fullmatch(FLOW_ID_PATTERN, "custom_12")
    assert re.fullmatch(FLOW_ID_PATTERN, "create_utubx") is None
    assert re.fullmatch(FLOW_ID_PATTERN, "xlogin") is None
    assert re.fullmatch(FLOW_ID_PATTERN, "custom_0") is None


def _pick(errors: dict[str, list[str]]) -> str:
    return first_invalid_detail(errors).field


def test_flow_level_before_step():
    detail = first_invalid_detail({"steps.0.event_name": ["a"], "display_name": ["b"]})
    assert detail.field == "display_name"
    assert detail.step_index is None
    assert detail.reason == "b"


def test_flow_level_order():
    assert _pick({"display_name": ["x"], "__root__": ["x"], "steps": ["x"]}) == (
        "__root__"
    )
    assert _pick({"steps": ["x"], "display_name": ["x"]}) == "display_name"
    assert _pick({"zeta": ["x"], "alpha": ["x"], "steps": ["x"]}) == "steps"
    assert _pick({"zeta": ["x"], "alpha": ["x"]}) == "alpha"


def test_steps_ordered_numerically():
    assert _pick({"steps.10.label": ["x"], "steps.2.label": ["x"]}) == "steps.2.label"
    assert first_invalid_detail({"steps.3.label": ["x"]}).step_index == 3


@pytest.mark.parametrize(
    "earlier,later",
    [
        ("steps.0", "steps.0.event_name"),
        ("steps.0.stream", "steps.0.event_name"),
        ("steps.0.event_name", "steps.0.api_endpoint"),
        ("steps.0.api_endpoint", "steps.0.api_method"),
        ("steps.0.api_method", "steps.0.label"),
        ("steps.0.label", "steps.0.dim_filter"),
        ("steps.0.dim_filter", "steps.0.dim_filter.0"),
        ("steps.0.dim_filter.2", "steps.0.dim_filter.10"),
        ("steps.0.dim_filter.10", "steps.0.drop_breakdown"),
        ("steps.0.drop_breakdown", "steps.0.drop_breakdown.event_name"),
        ("steps.0.drop_breakdown.event_name", "steps.0.drop_breakdown.dim_filter"),
        (
            "steps.0.drop_breakdown.dim_filter",
            "steps.0.drop_breakdown.dim_filter.0",
        ),
        (
            "steps.0.drop_breakdown.dim_filter.2",
            "steps.0.drop_breakdown.dim_filter.10",
        ),
        (
            "steps.0.drop_breakdown.dim_filter.10",
            "steps.0.drop_breakdown.group_by",
        ),
        ("steps.0.drop_breakdown.group_by", "steps.0.zzz"),
        ("steps.0.aaa", "steps.0.zzz"),
        ("steps.0.dim_filter.5", "steps.0.drop_breakdown.event_name"),
    ],
)
def test_within_step_order(earlier, later):
    assert _pick({later: ["x"], earlier: ["x"]}) == earlier
    assert _pick({earlier: ["x"], later: ["x"]}) == earlier


def test_three_key_map_picks_step_zero():
    detail = first_invalid_detail(
        {
            "steps.2.api_endpoint": ["c"],
            "steps.1.dim_filter.0": ["b"],
            "steps.0.event_name": ["a"],
        }
    )
    assert detail.step_index == 0
    assert detail.field == "steps.0.event_name"
    assert detail.reason == "a"


def test_reason_is_first_message():
    assert first_invalid_detail({"display_name": ["one", "two"]}).reason == "one"


def test_empty_paths_are_skipped():
    detail = first_invalid_detail({"display_name": [], "steps.1.label": ["x"]})
    assert detail.field == "steps.1.label"


@pytest.mark.parametrize("errors", [{}, {"display_name": [], "steps.0.label": []}])
def test_nothing_selectable_fails_closed(errors):
    detail = first_invalid_detail(errors)
    assert detail.step_index is None
    assert detail.field == "__root__"
    assert detail.reason == FLOW_INVALID_UNKNOWN_STR


def test_flow_invalid_response_body_and_status(app):
    detail = first_invalid_detail({"steps": ["Add at least 2 steps."]})
    with app.app_context():
        response, status_code = flow_invalid_response(detail)
        payload = response.get_json()

    assert status_code == 422
    assert payload == {
        "error": "flow_invalid",
        "invalid": {
            "step_index": None,
            "field": "steps",
            "reason": "Add at least 2 steps.",
        },
    }
