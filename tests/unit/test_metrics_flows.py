from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.metrics.events import EventName
from backend.metrics.flows import (
    FLOWS,
    FlowDefinition,
    FlowId,
    FlowStep,
    FlowStepBreakdown,
)

pytestmark = pytest.mark.unit


def test_flow_step_valid_with_event_name_only() -> None:
    """
    GIVEN a FlowStep with only `event_name` set
    WHEN the model is constructed
    THEN no ValidationError is raised (event/api mutual-exclusion satisfied).
    """
    step = FlowStep(
        stream="ui",
        label="Submit",
        event_name=EventName.UI_FORM_SUBMIT,
    )

    assert step.event_name is EventName.UI_FORM_SUBMIT
    assert step.api_endpoint is None
    assert step.api_method is None


def test_flow_step_valid_with_api_endpoint_and_method() -> None:
    """
    GIVEN a FlowStep with `api_endpoint` + `api_method` set and `event_name=None`
    WHEN the model is constructed
    THEN no ValidationError is raised (the API branch satisfies the XOR).
    """
    step = FlowStep(
        stream="api",
        label="POST .../urls",
        api_endpoint="urls.create_url",
        api_method="POST",
    )

    assert step.event_name is None
    assert step.api_endpoint == "urls.create_url"
    assert step.api_method == "POST"


def test_flow_step_invalid_with_both_event_name_and_api_endpoint() -> None:
    """
    GIVEN a FlowStep with BOTH `event_name` and `api_endpoint` set
    WHEN the model is constructed
    THEN a ValidationError is raised (mutual-exclusion validator).
    """
    with pytest.raises(ValidationError):
        FlowStep(
            stream="api",
            label="Both",
            event_name=EventName.UI_FORM_SUBMIT,
            api_endpoint="urls.create_url",
            api_method="POST",
        )


def test_flow_step_invalid_with_neither_event_name_nor_api_endpoint() -> None:
    """
    GIVEN a FlowStep with neither `event_name` nor `api_endpoint`/`api_method`
    WHEN the model is constructed
    THEN a ValidationError is raised (at-least-one validator).
    """
    with pytest.raises(ValidationError):
        FlowStep(stream="ui", label="Neither")


def test_flow_definition_invalid_with_one_step() -> None:
    """
    GIVEN a FlowDefinition with exactly one FlowStep
    WHEN the model is constructed
    THEN a ValidationError is raised (minimum 2 steps).
    """
    only_step = FlowStep(
        stream="ui",
        label="Open",
        event_name=EventName.UI_URL_CREATE_OPEN,
    )

    with pytest.raises(ValidationError):
        FlowDefinition(display_name="One step", steps=[only_step])


def test_flow_definition_valid_with_two_steps() -> None:
    """
    GIVEN a FlowDefinition with two valid FlowSteps
    WHEN the model is constructed
    THEN no ValidationError is raised (minimum-2-steps satisfied).
    """
    flow = FlowDefinition(
        display_name="Two steps",
        steps=[
            FlowStep(
                stream="ui",
                label="Open",
                event_name=EventName.UI_URL_CREATE_OPEN,
            ),
            FlowStep(
                stream="ui",
                label="Submit",
                event_name=EventName.UI_FORM_SUBMIT,
            ),
        ],
    )

    assert len(flow.steps) == 2


def test_all_registry_flows_have_at_least_two_steps() -> None:
    """
    GIVEN the static FLOWS registry
    WHEN every FlowDefinition is inspected
    THEN each has at least 2 steps and a non-empty display name — this is the
        startup guard the route handler relies on (a misconfigured flow would
        have raised at import time).
    """
    assert set(FLOWS.keys()) == set(FlowId)
    for flow_id, flow in FLOWS.items():
        assert len(flow.steps) >= 2, flow_id
        assert flow.display_name


def test_flow_step_breakdown_requires_group_by() -> None:
    """
    GIVEN a FlowStepBreakdown built without `group_by`
    WHEN the model is constructed
    THEN a ValidationError is raised (group_by is required).
    """
    with pytest.raises(ValidationError):
        FlowStepBreakdown(event_name=EventName.URL_CREATE_REJECTED)  # type: ignore[call-arg]
