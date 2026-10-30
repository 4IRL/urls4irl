"""HTTP-agnostic funnel counting shared by `/flow` and the flow preview.

`count_flow` takes a validated, enum-typed `FlowDefinition` and fans out one
`grouped_count_scalar()` per step plus one `grouped_count_by()` per
`drop_breakdown`, tagging any count-time `ValueError` with the failing step.
"""

from __future__ import annotations

from datetime import datetime

from backend.metrics.events import DEVICE_TYPE_DIM_KEY, EventName
from backend.metrics.flows import FlowDefinition, FlowStep
from backend.metrics.query_service import grouped_count_by, grouped_count_scalar
from backend.metrics.suppression import MIN_CELL_COUNT
from backend.schemas.metrics import (
    FlowBreakdownRow,
    FlowResponseSchema,
    FlowStepSchema,
)


class FlowCountError(ValueError):
    """A count-time `ValueError` tagged with the step (and field) that raised it.

    `str(error)` is exactly `reason`, so callers that only render the message
    (the built-in 400 body) see the original text unchanged.
    """

    def __init__(self, *, step_index: int, field: str, reason: str) -> None:
        super().__init__(reason)
        self.step_index = step_index
        self.field = field
        self.reason = reason


def _count_flow_step(
    step: FlowStep, window_start: datetime, window_end: datetime
) -> tuple[int, bool]:
    """Compute `(count, suppressed)` for one funnel step over the window.

    UI/DOMAIN steps count `step.event_name`; API steps match `API_HIT`'s flat
    `endpoint`/`method` columns (plus any per-step filter). Both call
    `grouped_count_scalar`, which returns a scalar `int`. A non-API step
    filtered on a non-`device_type` dimension whose count is below
    `MIN_CELL_COUNT` (and above zero) is floored to `0` and flagged suppressed.
    """
    if step.event_name is not None:
        count = grouped_count_scalar(
            event_name=step.event_name,
            window_start=window_start,
            window_end=window_end,
            dim_filter=step.dim_filter,
        )
        has_non_device_filter = any(
            key != DEVICE_TYPE_DIM_KEY for key, _ in (step.dim_filter or [])
        )
        if has_non_device_filter and 0 < count < MIN_CELL_COUNT:
            return 0, True
        return count, False
    api_filter: list[tuple[str, str]] = [
        ("endpoint", step.api_endpoint or ""),
        ("method", step.api_method or ""),
    ] + (step.dim_filter or [])
    api_count = grouped_count_scalar(
        event_name=EventName.API_HIT,
        window_start=window_start,
        window_end=window_end,
        dim_filter=api_filter,
    )
    return api_count, False


def _build_step_breakdown(
    step: FlowStep, window_start: datetime, window_end: datetime
) -> list[FlowBreakdownRow] | None:
    """Build a step's per-cause breakdown rows, or `None` when empty (DD-6).

    Returns `None` both when the step has no `drop_breakdown` configured and
    when the breakdown event has no rows in the window, so the renderer can
    skip the per-cause pill block uniformly.
    """
    if step.drop_breakdown is None:
        return None
    raw_rows = grouped_count_by(
        event_name=step.drop_breakdown.event_name,
        window_start=window_start,
        window_end=window_end,
        dim_filter=step.drop_breakdown.dim_filter,
        group_by=step.drop_breakdown.group_by,
    )
    if not raw_rows:
        return None
    breakdown_total = sum(count for _, count in raw_rows)
    return [
        FlowBreakdownRow(
            label=group_value,
            count=count,
            pct_of_step=0.0 if breakdown_total == 0 else count / breakdown_total,
        )
        for group_value, count in raw_rows
    ]


def count_flow(
    *, definition: FlowDefinition, window_start: datetime, window_end: datetime
) -> FlowResponseSchema:
    """Count every step of `definition` over the window and assemble the response.

    Evaluation is interleaved per step (count, then that step's breakdown), so
    when several steps would fail the lowest step index is the one reported.

    Raises:
        FlowCountError: a count-time `ValueError`, tagged with the step index
            and field (`steps.<i>` or `steps.<i>.drop_breakdown`).
    """
    step_counts: list[int] = []
    step_suppressed: list[bool] = []
    step_breakdowns: list[list[FlowBreakdownRow] | None] = []
    for step_index, step in enumerate(definition.steps):
        try:
            count, suppressed = _count_flow_step(step, window_start, window_end)
            step_counts.append(count)
            step_suppressed.append(suppressed)
        except ValueError as error:
            raise FlowCountError(
                step_index=step_index, field=f"steps.{step_index}", reason=str(error)
            ) from error
        try:
            step_breakdowns.append(
                _build_step_breakdown(step, window_start, window_end)
            )
        except ValueError as error:
            raise FlowCountError(
                step_index=step_index,
                field=f"steps.{step_index}.drop_breakdown",
                reason=str(error),
            ) from error

    top_count = step_counts[0]
    response_steps: list[FlowStepSchema] = []
    for step, count, suppressed, breakdown in zip(
        definition.steps, step_counts, step_suppressed, step_breakdowns
    ):
        pct_of_top = (
            None if suppressed or top_count == 0 else min(count, top_count) / top_count
        )
        event_name = step.label if step.event_name is None else step.event_name.value
        response_steps.append(
            FlowStepSchema(
                stream=step.stream,
                label=step.label,
                event_name=event_name,
                count=count,
                pct_of_top=pct_of_top,
                count_suppressed=suppressed,
                breakdown=breakdown,
            )
        )
    return FlowResponseSchema(steps=response_steps)
