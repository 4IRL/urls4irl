"""Unit tests for the per-event dimension-combination cap audit helper."""

from __future__ import annotations

from typing import Literal

import pytest
from pydantic import BaseModel

from backend.metrics.audit import diff_dimension_combination_cap
from backend.metrics.events import DeviceType, EventName
from backend.metrics.suppression import (
    MAX_DIM_COMBINATIONS_PER_EVENT,
    UNBOUNDED_DIM_EXEMPTIONS,
)

pytestmark = pytest.mark.unit

_EVENT = EventName.UI_URL_ACCESS


class _OverCapDims(BaseModel):
    first: Literal[
        "a0", "a1", "a2", "a3", "a4", "a5", "a6", "a7", "a8", "a9", "a10", "a11"
    ]
    second: Literal[
        "b0", "b1", "b2", "b3", "b4", "b5", "b6", "b7", "b8", "b9", "b10", "b11"
    ]
    third: Literal[
        "c0", "c1", "c2", "c3", "c4", "c5", "c6", "c7", "c8", "c9", "c10", "c11"
    ]


class _UnboundedIntDims(BaseModel):
    kind: Literal["a", "b"]
    count: int


def test_cap_is_700() -> None:
    """
    GIVEN the committed cap constant
    WHEN it is read
    THEN ensure it is 700
    """
    assert MAX_DIM_COMBINATIONS_PER_EVENT == 700


def test_current_registry_passes_cap() -> None:
    """
    GIVEN today's DIMENSION_MODELS and exemptions
    WHEN the cap audit runs
    THEN ensure there are no errors
    """
    assert diff_dimension_combination_cap() == []


def test_exemptions_all_carry_a_reason() -> None:
    """
    GIVEN the committed exemptions
    WHEN each reason is read
    THEN ensure every reason is a non-empty string
    """
    assert UNBOUNDED_DIM_EXEMPTIONS
    assert all(reason.strip() for reason in UNBOUNDED_DIM_EXEMPTIONS.values())


def test_over_cap_event_fails_naming_event_and_product() -> None:
    """
    GIVEN a synthetic event whose closed sets multiply to 1728
    WHEN the cap audit runs
    THEN ensure one error names the event and the product
    """
    errors = diff_dimension_combination_cap(
        dimension_models={_EVENT: _OverCapDims}, exemptions={}
    )

    assert len(errors) == 1
    assert _EVENT.name in errors[0]
    assert "1728" in errors[0]


def test_unexempted_int_dim_fails() -> None:
    """
    GIVEN an event with an int dim that is not exempted
    WHEN the cap audit runs
    THEN ensure an error names the event and the dim
    """
    errors = diff_dimension_combination_cap(
        dimension_models={_EVENT: _UnboundedIntDims}, exemptions={}
    )

    assert len(errors) == 1
    assert _EVENT.name in errors[0]
    assert "'count'" in errors[0]


def test_exempted_int_dim_passes() -> None:
    """
    GIVEN the same int dim with an explicit exemption
    WHEN the cap audit runs
    THEN ensure there are no errors
    """
    errors = diff_dimension_combination_cap(
        dimension_models={_EVENT: _UnboundedIntDims},
        exemptions={(_EVENT, "count"): "bounded elsewhere"},
    )

    assert errors == []


class _DeviceDims(BaseModel):
    device_type: DeviceType
    kind: Literal["a", "b", "c"]


def test_device_type_counts_as_enum_size_and_boundary() -> None:
    """
    GIVEN an event with device_type and a 3-value Literal (product 3 * |DeviceType|)
    WHEN the cap is set exactly at, then one below, that product
    THEN ensure it passes at the product and fails one below
    """
    product = 3 * len(DeviceType)

    at_cap = diff_dimension_combination_cap(
        dimension_models={_EVENT: _DeviceDims}, exemptions={}, max_combinations=product
    )
    below_cap = diff_dimension_combination_cap(
        dimension_models={_EVENT: _DeviceDims},
        exemptions={},
        max_combinations=product - 1,
    )

    assert at_cap == []
    assert len(below_cap) == 1
    assert str(product) in below_cap[0]


def test_api_hit_and_none_models_are_skipped() -> None:
    """
    GIVEN API_HIT with an over-cap model and an event with a None model
    WHEN the cap audit runs
    THEN ensure neither produces an error
    """
    errors = diff_dimension_combination_cap(
        dimension_models={
            EventName.API_HIT: _OverCapDims,
            _EVENT: None,
        },
        exemptions={},
    )

    assert errors == []


def test_stale_exemption_event_fails() -> None:
    """
    GIVEN an exemption for an event absent from the registry
    WHEN the cap audit runs
    THEN ensure a stale-exemption error is reported
    """
    errors = diff_dimension_combination_cap(
        dimension_models={},
        exemptions={(_EVENT, "count"): "gone"},
    )

    assert len(errors) == 1
    assert "stale exemption" in errors[0]


def test_stale_exemption_dim_fails() -> None:
    """
    GIVEN an exemption for a dim the event's model no longer has
    WHEN the cap audit runs
    THEN ensure a stale-exemption error is reported
    """
    errors = diff_dimension_combination_cap(
        dimension_models={_EVENT: _UnboundedIntDims},
        exemptions={
            (_EVENT, "count"): "still here",
            (_EVENT, "removed_dim"): "gone",
        },
    )

    assert len(errors) == 1
    assert "stale exemption" in errors[0]
    assert "removed_dim" in errors[0]
