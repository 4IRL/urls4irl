"""Secondary suppression for flow steps over TAG_APPLIED's utub_size_bucket."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from flask import Flask

from backend.metrics.events import EventCategory, EventName
from backend.metrics.flow_counting import count_flow
from backend.metrics.flows import FlowDefinition, FlowStep, FlowStepBreakdown
from backend.metrics.suppression import MIN_CELL_COUNT
from backend.utils.datetime_utils import utc_now
from tests.integration.system.test_metrics_query_endpoints import (
    _bucket_inside_window,
    _seed_event_with_count,
)

pytestmark = pytest.mark.cli

_SIZE = "utub_size_bucket"
_MOBILE = 1
_DESKTOP = 2


def _seed_cell(
    app: Flask, *, size: str | None, count: int, device: int = _DESKTOP
) -> None:
    """Seed one TAG_APPLIED cell on yesterday's UTC midnight (daily event)."""
    bucket = utc_now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(
        days=1
    )
    dimensions: dict[str, Any] = {"device_type": device}
    if size is not None:
        dimensions[_SIZE] = size
    with app.app_context():
        _seed_event_with_count(
            event_name=EventName.TAG_APPLIED,
            category=EventCategory.DOMAIN,
            bucket_start=bucket,
            count=count,
            dimensions=dimensions,
        )


def _applied(
    *filters: tuple[str, str], breakdown: FlowStepBreakdown | None = None
) -> FlowStep:
    return FlowStep(
        stream="domain",
        label="Tag applied",
        event_name=EventName.TAG_APPLIED,
        dim_filter=list(filters) or None,
        drop_breakdown=breakdown,
    )


def _run(app: Flask, steps: list[FlowStep]) -> list[Any]:
    window_end = utc_now()
    with app.app_context():
        return count_flow(
            definition=FlowDefinition(display_name="t", steps=steps),
            window_start=window_end - timedelta(days=1),
            window_end=window_end,
        ).steps


def _seed_three_size_cells(app: Flask) -> None:
    for size, count in (("1-5", 3), ("6-20", 20), ("21-50", 30)):
        _seed_cell(app, size=size, count=count)


def _seed_cancel_row(app: Flask) -> None:
    with app.app_context():
        _seed_event_with_count(
            event_name=EventName.UI_FORM_CANCEL,
            category=EventCategory.UI,
            bucket_start=_bucket_inside_window(),
            count=6,
            dimensions={
                "trigger": "escape_key",
                "form": "url_create",
                "device_type": 2,
            },
        )


def test_lone_sub_floor_cell_plus_kept_cell_hides_both_steps(app: Flask) -> None:
    """
    GIVEN size cells of 3 and 20 (unfiltered total 23)
    WHEN a step per cell is counted
    THEN both report 0 / suppressed, so total minus one step cannot recover the other.
    """
    _seed_cell(app, size="1-5", count=3)
    _seed_cell(app, size="6-20", count=20)

    steps = _run(app, [_applied(), _applied((_SIZE, "1-5")), _applied((_SIZE, "6-20"))])

    assert steps[0].count == 23
    assert [(step.count, step.count_suppressed) for step in steps[1:]] == [
        (0, True),
        (0, True),
    ]


def test_exact_floor_cell_is_revealed_without_sub_floor_sibling(app: Flask) -> None:
    """
    GIVEN a single cell at exactly MIN_CELL_COUNT
    WHEN a step filtered on it is counted
    THEN it reads its real count.
    """
    _seed_cell(app, size="6-20", count=MIN_CELL_COUNT)

    steps = _run(app, [_applied(), _applied((_SIZE, "6-20"))])

    assert (steps[1].count, steps[1].count_suppressed) == (MIN_CELL_COUNT, False)


def test_exact_floor_cell_with_lone_sub_floor_sibling_is_absorbed(app: Flask) -> None:
    """
    GIVEN cells of 4 and 5 (MIN_CELL_COUNT)
    WHEN a step per cell is counted
    THEN both are suppressed (one sentinel of 9 in the cell view).
    """
    _seed_cell(app, size="1-5", count=MIN_CELL_COUNT - 1)
    _seed_cell(app, size="6-20", count=MIN_CELL_COUNT)

    steps = _run(app, [_applied(), _applied((_SIZE, "1-5")), _applied((_SIZE, "6-20"))])

    assert steps[0].count == 2 * MIN_CELL_COUNT - 1
    assert [(step.count, step.count_suppressed) for step in steps[1:]] == [
        (0, True),
        (0, True),
    ]


def test_same_event_breakdown_on_suppressed_step_is_null(app: Flask) -> None:
    """
    GIVEN the absorbed 20-cell step with a same-event breakdown
    WHEN the flow is counted
    THEN the step is suppressed and its breakdown is null.
    """
    _seed_three_size_cells(app)
    breakdown = FlowStepBreakdown(
        event_name=EventName.TAG_APPLIED,
        dim_filter=[(_SIZE, "6-20")],
        group_by=_SIZE,
    )

    steps = _run(app, [_applied(), _applied((_SIZE, "6-20"), breakdown=breakdown)])

    assert steps[1].count_suppressed is True
    assert steps[1].breakdown is None


def test_different_event_breakdown_on_suppressed_step_still_renders(
    app: Flask,
) -> None:
    """
    GIVEN the suppressed 20-cell step with a UI_FORM_CANCEL breakdown
    WHEN the flow is counted
    THEN count_suppressed is true and the breakdown rows are present.
    """
    _seed_three_size_cells(app)
    _seed_cancel_row(app)
    breakdown = FlowStepBreakdown(
        event_name=EventName.UI_FORM_CANCEL, group_by="trigger"
    )

    steps = _run(app, [_applied(), _applied((_SIZE, "6-20"), breakdown=breakdown)])

    assert steps[1].count_suppressed is True
    assert steps[1].breakdown is not None
    assert [(row.label, row.count) for row in steps[1].breakdown] == [("escape_key", 6)]


def test_breakdown_on_revealed_cell_keeps_rows(app: Flask) -> None:
    """
    GIVEN the revealed 30-cell step with a same-event breakdown on its own cell
    WHEN the flow is counted
    THEN the step reads 30 and its breakdown rows are kept.
    """
    _seed_three_size_cells(app)
    breakdown = FlowStepBreakdown(
        event_name=EventName.TAG_APPLIED,
        dim_filter=[(_SIZE, "21-50")],
        group_by=_SIZE,
    )

    steps = _run(app, [_applied(), _applied((_SIZE, "21-50"), breakdown=breakdown)])

    assert (steps[1].count, steps[1].count_suppressed) == (30, False)
    assert steps[1].breakdown is not None
    assert sum(row.count for row in steps[1].breakdown) == 30


def test_device_filtered_step_suppressed_by_nonzero_unrevealable_sibling(
    app: Flask,
) -> None:
    """
    GIVEN one size cell of 3 on mobile and 10 on desktop
    WHEN the desktop-scoped step is counted
    THEN it is suppressed by the swapped-device sibling (rule c).
    """
    _seed_cell(app, size="6-20", count=3, device=_MOBILE)
    _seed_cell(app, size="6-20", count=10, device=_DESKTOP)

    steps = _run(app, [_applied(), _applied((_SIZE, "6-20"), ("device_type", "2"))])

    assert (steps[1].count, steps[1].count_suppressed) == (0, True)


def test_device_sibling_rule_ignores_zero_count_sibling(app: Flask) -> None:
    """
    GIVEN one size cell of 10 on desktop and no mobile rows
    WHEN the cell is counted with a desktop filter
    THEN the empty sibling does not trigger suppression.
    """
    _seed_cell(app, size="6-20", count=10, device=_DESKTOP)

    steps = _run(app, [_applied(), _applied((_SIZE, "6-20"), ("device_type", "2"))])

    assert (steps[1].count, steps[1].count_suppressed) == (10, False)


def test_rows_without_the_dim_stay_in_total_and_in_no_cell(app: Flask) -> None:
    """
    GIVEN pre-deploy rows (no utub_size_bucket) of 7 plus a 20-cell
    WHEN the unfiltered total and the 20-cell step are counted
    THEN the total is 27 and the cell reads 20 (the dimensionless rows join no cell).
    """
    _seed_cell(app, size=None, count=7)
    _seed_cell(app, size="6-20", count=20)

    steps = _run(app, [_applied(), _applied((_SIZE, "6-20"))])

    assert steps[0].count == 27
    assert (steps[1].count, steps[1].count_suppressed) == (20, False)
