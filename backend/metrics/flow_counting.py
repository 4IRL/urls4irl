"""HTTP-agnostic funnel counting shared by `/flow` and the flow preview.

`count_flow` takes a validated, enum-typed `FlowDefinition` and fans out one
`grouped_count_scalar()` per step plus one `grouped_count_by()` per
`drop_breakdown`, tagging any count-time `ValueError` with the failing step.
"""

from __future__ import annotations

from datetime import datetime

from backend.metrics.events import DEVICE_TYPE_DIM_KEY, DeviceType, EventName
from backend.metrics.flows import FlowDefinition, FlowStep
from backend.metrics.query_service import grouped_count_by, grouped_count_scalar
from backend.metrics.suppression import (
    MIN_CELL_COUNT,
    SUPPRESSED_DIM_VALUE,
    single_key_group_by_choices,
)
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


def _is_revealable(
    *,
    event_name: EventName,
    dim_key: str,
    dim_value: str,
    window_start: datetime,
    window_end: datetime,
    device_filter: list[tuple[str, str]],
) -> bool:
    """Return whether `dim_value` is a real label in the `dim_key` cell view.

    The cell view is `grouped_count_by` over `dim_key` scoped by
    `device_filter`. A value that is absent or only present through the
    suppression sentinel is not revealable (fail closed).
    """
    cell_view = grouped_count_by(
        event_name=event_name,
        window_start=window_start,
        window_end=window_end,
        group_by=dim_key,
        dim_filter=device_filter,
    )
    return any(
        label == dim_value and label != SUPPRESSED_DIM_VALUE for label, _ in cell_view
    )


def _is_secondarily_suppressed(
    *,
    step: FlowStep,
    window_start: datetime,
    window_end: datetime,
) -> bool:
    """Apply rules (b) and (c) to a step with exactly one projection filter."""
    event_name = step.event_name
    if event_name is None:
        return True
    entries = step.dim_filter or []
    partition_key, partition_value = next(
        entry for entry in entries if entry[0] != DEVICE_TYPE_DIM_KEY
    )
    device_entries = [entry for entry in entries if entry[0] == DEVICE_TYPE_DIM_KEY]
    if not _is_revealable(
        event_name=event_name,
        dim_key=partition_key,
        dim_value=partition_value,
        window_start=window_start,
        window_end=window_end,
        device_filter=device_entries,
    ):
        return True
    if not device_entries:
        return False
    own_device = int(device_entries[0][1])
    for member in DeviceType:
        if int(member.value) == own_device:
            continue
        sibling_device_filter = [(DEVICE_TYPE_DIM_KEY, str(member.value))]
        sibling_full_filter = [
            entry for entry in entries if entry[0] != DEVICE_TYPE_DIM_KEY
        ] + sibling_device_filter
        sibling_count = grouped_count_scalar(
            event_name=event_name,
            window_start=window_start,
            window_end=window_end,
            dim_filter=sibling_full_filter,
        )
        if sibling_count > 0 and not _is_revealable(
            event_name=event_name,
            dim_key=partition_key,
            dim_value=partition_value,
            window_start=window_start,
            window_end=window_end,
            device_filter=sibling_device_filter,
        ):
            return True
    return False


def _count_flow_step(
    step: FlowStep, window_start: datetime, window_end: datetime
) -> tuple[int, bool]:
    """Compute `(count, suppressed)` for one funnel step over the window.

    UI/DOMAIN steps count `step.event_name`; API steps match `API_HIT`'s flat
    `endpoint`/`method` columns (plus any per-step filter). Both call
    `grouped_count_scalar`, which returns a scalar `int`. A non-API step is
    floored to `0` and flagged suppressed when:

    (a) it has a non-`device_type` filter and `0 < count < MIN_CELL_COUNT`;
    (d) it has two or more non-`device_type` entries, one a registered
        single-key projection of the event (a cross-tab);
    (b) its single projection value is not a real label in the matching
        `grouped_count_by` cell view (a small cell or the cell a sub-floor
        sibling was folded into);
    (c) it is device-filtered and a non-empty sibling-device cell of the same
        value is not revealable.

    A zero count is never suppressed. Unfiltered, device-only, API and
    non-projection steps issue no extra queries.
    """
    if step.event_name is not None:
        count = grouped_count_scalar(
            event_name=step.event_name,
            window_start=window_start,
            window_end=window_end,
            dim_filter=step.dim_filter,
        )
        if count == 0:
            return 0, False
        non_device_entries = [
            entry
            for entry in (step.dim_filter or [])
            if entry[0] != DEVICE_TYPE_DIM_KEY
        ]
        if non_device_entries and count < MIN_CELL_COUNT:
            return 0, True
        projection_keys = single_key_group_by_choices(step.event_name)
        projection_entries = [
            entry for entry in non_device_entries if entry[0] in projection_keys
        ]
        if not projection_entries:
            return count, False
        if len(non_device_entries) >= 2:
            return 0, True
        if _is_secondarily_suppressed(
            step=step,
            window_start=window_start,
            window_end=window_end,
        ):
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


def _suppressed_breakdown_withheld(step: FlowStep) -> bool:
    """Return whether a suppressed step's breakdown must be withheld.

    Kept only when the breakdown's event provably differs from the step's.
    An undeterminable event (API step) withholds (fail closed).
    """
    if step.drop_breakdown is None or step.event_name is None:
        return True
    return step.drop_breakdown.event_name == step.event_name


def _breakdown_points_at_other_cell(step: FlowStep) -> bool:
    """Return whether a breakdown filtered on a projection dim may leak a cell.

    A breakdown with a projection-dim filter entry is allowed only when it is
    on the step's own event, that entry is also in the step's `dim_filter`,
    and it has no other non-`device_type` entry.
    """
    breakdown = step.drop_breakdown
    if breakdown is None:
        return False
    non_device_entries = [
        entry
        for entry in (breakdown.dim_filter or [])
        if entry[0] != DEVICE_TYPE_DIM_KEY
    ]
    projection_keys = single_key_group_by_choices(breakdown.event_name)
    if not any(entry[0] in projection_keys for entry in non_device_entries):
        return False
    if step.event_name is None or step.event_name != breakdown.event_name:
        return True
    if len(non_device_entries) != 1:
        return True
    return non_device_entries[0] not in (step.dim_filter or [])


def _build_step_breakdown(
    step: FlowStep,
    window_start: datetime,
    window_end: datetime,
    *,
    suppressed: bool = False,
) -> list[FlowBreakdownRow] | None:
    """Build a step's per-cause breakdown rows, or `None` when empty (DD-6).

    Returns `None` both when the step has no `drop_breakdown` configured and
    when the breakdown event has no rows in the window, so the renderer can
    skip the per-cause pill block uniformly. It also returns `None` without
    querying when a suppressed step's breakdown is on the same event, or when
    a projection-dim filter would point the breakdown at a different cell.
    """
    if step.drop_breakdown is None:
        return None
    if suppressed and _suppressed_breakdown_withheld(step):
        return None
    if _breakdown_points_at_other_cell(step):
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
                _build_step_breakdown(
                    step, window_start, window_end, suppressed=suppressed
                )
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
