from __future__ import annotations

import pytest

from backend.metrics.dimension_models import DIMENSION_MODELS
from backend.metrics.events import EventName
from backend.metrics.flows import FLOWS
from backend.metrics.suppression import (
    ALLOWED_GROUP_BY_PROJECTIONS,
    single_key_group_by_choices,
    validate_group_by_projection,
)
from backend.utils.strings.metric_flow_strs import group_by_not_available_message

pytestmark = pytest.mark.unit

_PIPELINE_HEALTH_PROJECTION = frozenset(
    {"batch_size_bucket", "transport", "device_type"}
)


def test_no_event_registers_nested_projections():
    for event, projections in ALLOWED_GROUP_BY_PROJECTIONS.items():
        for first in projections:
            for second in projections:
                if first is not second:
                    assert not first <= second, f"{event} nests {first} in {second}"


def test_every_registered_key_is_a_declared_dim_and_api_hit_is_exempt():
    assert EventName.API_HIT not in ALLOWED_GROUP_BY_PROJECTIONS
    for event, projections in ALLOWED_GROUP_BY_PROJECTIONS.items():
        model = DIMENSION_MODELS[event]
        assert model is not None
        declared = set(model.model_fields)
        for projection in projections:
            assert projection <= declared, f"{event} registers undeclared {projection}"


def test_every_built_in_flow_breakdown_and_pipeline_health_is_registered():
    assert (
        _PIPELINE_HEALTH_PROJECTION
        in ALLOWED_GROUP_BY_PROJECTIONS[EventName.API_METRICS_INGEST_BATCH]
    )
    breakdowns = [
        step.drop_breakdown
        for flow in FLOWS.values()
        for step in flow.steps
        if step.drop_breakdown is not None
    ]
    assert any(
        breakdown.event_name is not EventName.API_HIT for breakdown in breakdowns
    )
    for breakdown in breakdowns:
        validate_group_by_projection(breakdown.event_name, [breakdown.group_by])


def test_exact_projection_in_any_order_is_accepted():
    validate_group_by_projection(
        EventName.API_METRICS_INGEST_BATCH,
        ["device_type", "batch_size_bucket", "transport"],
    )


def test_api_hit_is_exempt():
    validate_group_by_projection(EventName.API_HIT, ["endpoint"])


@pytest.mark.parametrize(
    "event_name,group_by",
    [
        (EventName.API_METRICS_INGEST_BATCH, ["transport", "device_type"]),
        (EventName.API_METRICS_INGEST_BATCH, ["device_type"]),
        (EventName.UI_FORM_CANCEL, ["trigger", "form"]),
        (EventName.UI_FORM_CANCEL, ["form"]),
        (EventName.UI_FORM_CANCEL, ["trigger", "trigger"]),
        (EventName.UI_URL_ACCESS, ["device_type"]),
        (EventName.UTUB_OPENED, ["url_count_bucket", "age_bucket"]),
        (EventName.UTUB_OPENED, ["device_type"]),
    ],
)
def test_non_member_projection_is_refused(event_name, group_by):
    with pytest.raises(ValueError):
        validate_group_by_projection(event_name, group_by)


def test_refusal_text_names_event_and_allowed_projections_only():
    with pytest.raises(ValueError) as exc_info:
        validate_group_by_projection(EventName.UI_FORM_CANCEL, ["form", "zzz"])
    message = str(exc_info.value)
    assert EventName.UI_FORM_CANCEL.value in message
    assert "[trigger]" in message
    assert "[form, zzz]" in message


def test_single_key_group_by_choices_excludes_multi_key_projections():
    assert single_key_group_by_choices(EventName.UI_FORM_CANCEL) == ["trigger"]
    assert single_key_group_by_choices(EventName.LOGIN_FAILURE) == ["reason"]
    assert single_key_group_by_choices(EventName.API_METRICS_INGEST_BATCH) == []
    assert single_key_group_by_choices(EventName.UI_URL_ACCESS) == []


def test_utub_opened_registers_exactly_the_two_bucket_keys():
    assert single_key_group_by_choices(EventName.UTUB_OPENED) == [
        "age_bucket",
        "url_count_bucket",
    ]
    validate_group_by_projection(EventName.UTUB_OPENED, ["url_count_bucket"])
    validate_group_by_projection(EventName.UTUB_OPENED, ["age_bucket"])


def test_group_by_not_available_message_exact_wording():
    assert (
        group_by_not_available_message(group_by="x", allowed=["a", "b"])
        == 'Cannot break down this event by "x". Allowed: "a", "b". '
        "Choose one or remove the breakdown."
    )
    assert (
        group_by_not_available_message(group_by="x", allowed=[])
        == "This event cannot be broken down."
    )
