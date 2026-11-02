"""Secondary suppression for flow steps over projection dims (UTUB_OPENED)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from flask import Flask

from backend.metrics import flow_counting
from backend.metrics.events import EventCategory, EventName
from backend.metrics.flow_counting import (
    FlowCountError,
    _suppressed_breakdown_withheld,
    count_flow,
)
from backend.metrics.flows import FlowDefinition, FlowStep, FlowStepBreakdown
from backend.metrics.query_service import grouped_count_by
from backend.metrics.suppression import MIN_CELL_COUNT, SUPPRESSED_DIM_VALUE
from backend.utils.datetime_utils import utc_now
from tests.integration.system.test_metrics_query_endpoints import (
    _bucket_inside_window,
    _seed_event_with_count,
)

pytestmark = pytest.mark.cli

_SIZE = "url_count_bucket"
_AGE = "age_bucket"
_DIM_VALUES: list[tuple[str, tuple[str, str, str], dict[str, str]]] = [
    (_SIZE, ("1-5", "6-20", "21-50"), {_AGE: "0-6d"}),
    (_AGE, ("0-6d", "7-29d", "30-89d"), {_SIZE: "6-20"}),
]
_MOBILE = 1
_DESKTOP = 2


def _seed_cell(
    app: Flask,
    *,
    size: str,
    age: str,
    count: int,
    device: int = _DESKTOP,
) -> None:
    """Seed one UTUB_OPENED cell on yesterday's UTC midnight."""
    bucket = utc_now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(
        days=1
    )
    with app.app_context():
        _seed_event_with_count(
            event_name=EventName.UTUB_OPENED,
            category=EventCategory.DOMAIN,
            bucket_start=bucket,
            count=count,
            dimensions={_SIZE: size, _AGE: age, "device_type": device},
        )


def _seed_dim_cells(
    app: Flask,
    *,
    dim_key: str,
    cells: list[tuple[str, int]],
    constant: dict[str, str],
) -> None:
    for value, count in cells:
        dims = {**constant, dim_key: value}
        _seed_cell(app, size=dims[_SIZE], age=dims[_AGE], count=count)


def _opened(
    *filters: tuple[str, str], breakdown: FlowStepBreakdown | None = None
) -> FlowStep:
    return FlowStep(
        stream="domain",
        label="Opened",
        event_name=EventName.UTUB_OPENED,
        dim_filter=list(filters) or None,
        drop_breakdown=breakdown,
    )


def _window() -> tuple[Any, Any]:
    window_end = utc_now()
    return window_end - timedelta(days=1), window_end


def _run(app: Flask, steps: list[FlowStep]) -> list[Any]:
    window_start, window_end = _window()
    with app.app_context():
        return count_flow(
            definition=FlowDefinition(display_name="t", steps=steps),
            window_start=window_start,
            window_end=window_end,
        ).steps


@pytest.mark.parametrize(
    "count,expected_suppressed", [(MIN_CELL_COUNT - 1, True), (MIN_CELL_COUNT, False)]
)
@pytest.mark.parametrize("dim_key,values,constant", _DIM_VALUES)
def test_projection_step_floor_and_exact_floor(
    app: Flask,
    dim_key: str,
    values: tuple[str, str, str],
    constant: dict[str, str],
    count: int,
    expected_suppressed: bool,
) -> None:
    """
    GIVEN a single UTUB_OPENED cell of MIN_CELL_COUNT - 1 or MIN_CELL_COUNT
    WHEN a step filtered on that cell is counted
    THEN the sub-floor step is suppressed and the exact-floor one (no sub-floor
        sibling) reads its real count.
    """
    _seed_dim_cells(app, dim_key=dim_key, cells=[(values[1], count)], constant=constant)

    steps = _run(app, [_opened(), _opened((dim_key, values[1]))])

    assert steps[1].count_suppressed is expected_suppressed
    assert steps[1].count == (0 if expected_suppressed else count)


@pytest.mark.parametrize("dim_key,values,constant", _DIM_VALUES)
def test_subtraction_attack_is_closed_by_absorption(
    app: Flask,
    dim_key: str,
    values: tuple[str, str, str],
    constant: dict[str, str],
) -> None:
    """
    GIVEN cells of 3, 20 and 30 in one bucket dim
    WHEN the unfiltered total and one step per value are counted
    THEN the 20-cell (the smallest kept) is absorbed with the 3, the 30-cell
        reads 30, and total minus visible steps is 23, never 3.
    """
    _seed_dim_cells(
        app,
        dim_key=dim_key,
        cells=list(zip(values, (3, 20, 30))),
        constant=constant,
    )

    steps = _run(app, [_opened(), *[_opened((dim_key, value)) for value in values]])

    assert steps[0].count == 53
    assert [(step.count, step.count_suppressed) for step in steps[1:]] == [
        (0, True),
        (0, True),
        (30, False),
    ]
    visible = sum(step.count for step in steps[1:])
    assert steps[0].count - visible == 23


@pytest.mark.parametrize("dim_key,values,constant", _DIM_VALUES)
def test_no_sentinel_means_real_counts_and_empty_value_reads_zero(
    app: Flask,
    dim_key: str,
    values: tuple[str, str, str],
    constant: dict[str, str],
) -> None:
    """
    GIVEN cells of 20 and 30 and an empty third value
    WHEN a step per value is counted
    THEN both real counts show and the empty value reads (0, not suppressed).
    """
    _seed_dim_cells(
        app,
        dim_key=dim_key,
        cells=[(values[0], 20), (values[1], 30)],
        constant=constant,
    )

    steps = _run(app, [_opened(), *[_opened((dim_key, value)) for value in values]])

    assert [(step.count, step.count_suppressed) for step in steps[1:]] == [
        (20, False),
        (30, False),
        (0, False),
    ]


def test_lone_sub_floor_cell_residual_is_still_open(app: Flask) -> None:
    """
    GIVEN a single non-empty cell of 3 (documented as NOT closed)
    WHEN the total and the cell step are counted
    THEN the cell step is suppressed but the unfiltered total still reads 3.
    """
    _seed_cell(app, size="1-5", age="0-6d", count=3)

    steps = _run(app, [_opened(), _opened((_SIZE, "1-5"))])

    assert steps[0].count == 3
    assert (steps[1].count, steps[1].count_suppressed) == (0, True)


def _seed_cross_slice(app: Flask) -> None:
    for size, age, count in (
        ("6-20", "0-6d", 10),
        ("6-20", "7-29d", 10),
        ("21-50", "0-6d", 15),
        ("21-50", "7-29d", 15),
        ("1-5", "30-89d", 3),
    ):
        _seed_cell(app, size=size, age=age, count=count)


def test_cross_slice_two_dim_steps_are_suppressed_outright(app: Flask) -> None:
    """
    GIVEN a cross-tab with a hidden cell of 3 (total 53)
    WHEN the total and the four visible 2-D steps are counted
    THEN every 2-D step is suppressed, so total minus visible is 53, not 3.
    """
    _seed_cross_slice(app)
    two_d = [
        _opened((_SIZE, size), (_AGE, age))
        for size in ("6-20", "21-50")
        for age in ("0-6d", "7-29d")
    ]

    steps = _run(app, [_opened(), *two_d])

    assert steps[0].count == 53
    assert all(step.count_suppressed and step.count == 0 for step in steps[1:])


def test_cross_slice_hidden_empty_and_device_variants(app: Flask) -> None:
    """
    GIVEN the cross-tab seed
    WHEN the hidden-cell 2-D step, an empty-cell 2-D step, a 2-D step with a
        device entry, and the 1-D steps are counted
    THEN the hidden cell and the device variant are suppressed, the empty cell
        reads (0, False), and the 1-D steps absorb as hand-computed (X'=30
        revealed, X suppressed).
    """
    _seed_cross_slice(app)

    steps = _run(
        app,
        [
            _opened(),
            _opened((_SIZE, "1-5"), (_AGE, "30-89d")),
            _opened((_SIZE, "6-20"), (_AGE, "30-89d")),
            _opened((_SIZE, "6-20"), (_AGE, "0-6d"), ("device_type", "2")),
            _opened((_SIZE, "21-50")),
            _opened((_SIZE, "6-20")),
        ],
    )

    assert [(step.count, step.count_suppressed) for step in steps[1:]] == [
        (0, True),
        (0, False),
        (0, True),
        (30, False),
        (0, True),
    ]


def test_device_axis_sibling_rule_blocks_cell_minus_other_device(app: Flask) -> None:
    """
    GIVEN one size cell of 3 on mobile and 10 on desktop
    WHEN the cell is counted per device and without a device filter
    THEN both device-scoped steps are suppressed (the 10-side by the sibling
        rule) and the all-device step reads 13.
    """
    _seed_cell(app, size="6-20", age="0-6d", count=3, device=_MOBILE)
    _seed_cell(app, size="6-20", age="0-6d", count=10, device=_DESKTOP)

    steps = _run(
        app,
        [
            _opened(),
            _opened((_SIZE, "6-20"), ("device_type", "2")),
            _opened((_SIZE, "6-20"), ("device_type", "1")),
            _opened((_SIZE, "6-20")),
        ],
    )

    assert [(step.count, step.count_suppressed) for step in steps[1:]] == [
        (0, True),
        (0, True),
        (13, False),
    ]


def test_device_sibling_rule_ignores_zero_count_sibling_device(app: Flask) -> None:
    """
    GIVEN one size cell of 10 on desktop and no mobile rows
    WHEN the cell is counted with a desktop device filter
    THEN rule (c) does not fire for the empty sibling and the step reads 10.
    """
    _seed_cell(app, size="6-20", age="0-6d", count=10, device=_DESKTOP)

    steps = _run(app, [_opened(), _opened((_SIZE, "6-20"), ("device_type", "2"))])

    assert [(step.count, step.count_suppressed) for step in steps[1:]] == [(10, False)]


def test_cross_view_consistency_with_grouped_count_by(app: Flask) -> None:
    """
    GIVEN size cells of 3, 20 and 30
    WHEN grouped_count_by runs on the same dim and window
    THEN suppressed steps' values sit under "suppressed" while the revealed
        step's value is a real label with the same count; a device-sibling-only
        suppression is a real label in its own device-scoped view.
    """
    for size, count in (("1-5", 3), ("6-20", 20), ("21-50", 30)):
        _seed_cell(app, size=size, age="0-6d", count=count)
    window_start, window_end = _window()

    with app.app_context():
        view = dict(
            grouped_count_by(
                event_name=EventName.UTUB_OPENED,
                window_start=window_start,
                window_end=window_end,
                group_by=_SIZE,
            )
        )

    assert "1-5" not in view
    assert "6-20" not in view
    assert view["21-50"] == 30
    assert view[SUPPRESSED_DIM_VALUE] == 23


def test_cross_view_device_sibling_only_suppression(app: Flask) -> None:
    """
    GIVEN one size cell of 3 on mobile and 10 on desktop
    WHEN the desktop-scoped and mobile-scoped cell views are read
    THEN the desktop value is a real label in its own view (the step is
        suppressed only by the sibling clause) while the mobile view hides 3.
    """
    _seed_cell(app, size="6-20", age="0-6d", count=3, device=_MOBILE)
    _seed_cell(app, size="6-20", age="0-6d", count=10, device=_DESKTOP)
    window_start, window_end = _window()

    with app.app_context():
        desktop_view = grouped_count_by(
            event_name=EventName.UTUB_OPENED,
            window_start=window_start,
            window_end=window_end,
            group_by=_SIZE,
            dim_filter=[("device_type", "2")],
        )
        mobile_view = grouped_count_by(
            event_name=EventName.UTUB_OPENED,
            window_start=window_start,
            window_end=window_end,
            group_by=_SIZE,
            dim_filter=[("device_type", "1")],
        )

    assert desktop_view == [("6-20", 10)]
    assert mobile_view == [(SUPPRESSED_DIM_VALUE, 3)]


# --- breakdown rules --------------------------------------------------------


def _seed_three_size_cells(app: Flask) -> None:
    for size, count in (("1-5", 3), ("6-20", 20), ("21-50", 30)):
        _seed_cell(app, size=size, age="0-6d", count=count)


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


def _same_event_breakdown(*filters: tuple[str, str]) -> FlowStepBreakdown:
    return FlowStepBreakdown(
        event_name=EventName.UTUB_OPENED,
        dim_filter=list(filters) or None,
        group_by=_AGE,
    )


def test_same_event_breakdown_on_suppressed_step_is_null(app: Flask) -> None:
    """
    GIVEN the 20-cell step (absorbed, rule b) with a same-event breakdown
    WHEN the flow is counted
    THEN the step is suppressed and its breakdown is null.
    """
    _seed_three_size_cells(app)

    steps = _run(
        app,
        [
            _opened(),
            _opened((_SIZE, "6-20"), breakdown=_same_event_breakdown((_SIZE, "6-20"))),
        ],
    )

    assert steps[1].count_suppressed is True
    assert steps[1].breakdown is None


def test_different_event_breakdown_on_suppressed_step_still_renders(
    app: Flask,
) -> None:
    """
    GIVEN the same suppressed 20-cell step with a UI_FORM_CANCEL breakdown
    WHEN the flow is counted
    THEN count_suppressed is true and the breakdown rows are present.
    """
    _seed_three_size_cells(app)
    _seed_cancel_row(app)
    breakdown = FlowStepBreakdown(
        event_name=EventName.UI_FORM_CANCEL, group_by="trigger"
    )

    steps = _run(app, [_opened(), _opened((_SIZE, "6-20"), breakdown=breakdown)])

    assert steps[1].count_suppressed is True
    assert steps[1].breakdown is not None
    assert [(row.label, row.count) for row in steps[1].breakdown] == [("escape_key", 6)]


def test_breakdown_pointed_at_hidden_cell_from_unfiltered_step_is_null(
    app: Flask,
) -> None:
    """
    GIVEN an unfiltered step whose breakdown is filtered to the hidden 3-cell
    WHEN the flow is counted
    THEN the breakdown is null.
    """
    _seed_three_size_cells(app)

    steps = _run(
        app,
        [_opened(), _opened(breakdown=_same_event_breakdown((_SIZE, "1-5")))],
    )

    assert steps[1].breakdown is None


def test_breakdown_on_own_revealed_cell_keeps_rows(app: Flask) -> None:
    """
    GIVEN the revealable 30-cell step with a breakdown filtered to its own cell
    WHEN the flow is counted
    THEN the breakdown rows are kept.
    """
    _seed_three_size_cells(app)

    steps = _run(
        app,
        [
            _opened(),
            _opened(
                (_SIZE, "21-50"), breakdown=_same_event_breakdown((_SIZE, "21-50"))
            ),
        ],
    )

    assert steps[1].count == 30
    assert steps[1].breakdown is not None
    assert [(row.label, row.count) for row in steps[1].breakdown] == [("0-6d", 30)]


def test_different_event_breakdown_filtered_on_projection_dim_is_null(
    app: Flask,
) -> None:
    """
    GIVEN a URL_CREATE_REJECTED breakdown filtered on its `reason` projection
        under an UTUB_OPENED step
    WHEN the flow is counted
    THEN the breakdown is null (different event than the step).
    """
    _seed_three_size_cells(app)
    breakdown = FlowStepBreakdown(
        event_name=EventName.URL_CREATE_REJECTED,
        dim_filter=[("reason", "invalid_url")],
        group_by="reason",
    )

    steps = _run(app, [_opened(), _opened(breakdown=breakdown)])

    assert steps[1].breakdown is None


def test_api_step_breakdown_filtered_on_projection_dim_is_null(app: Flask) -> None:
    """
    GIVEN an API step (no event_name) whose breakdown is filtered on a
        projection dim, with matching breakdown rows seeded
    WHEN the flow is counted
    THEN the breakdown is null.
    """
    with app.app_context():
        _seed_event_with_count(
            event_name=EventName.URL_CREATE_REJECTED,
            category=EventCategory.DOMAIN,
            bucket_start=_bucket_inside_window(),
            count=6,
            dimensions={"reason": "invalid_url", "device_type": 2},
        )
    breakdown = FlowStepBreakdown(
        event_name=EventName.URL_CREATE_REJECTED,
        dim_filter=[("reason", "invalid_url")],
        group_by="reason",
    )
    api_step = FlowStep(
        stream="api",
        label="API",
        api_endpoint="urls.create_url",
        api_method="POST",
        drop_breakdown=breakdown,
    )

    steps = _run(app, [_opened(), api_step])

    assert steps[1].breakdown is None


def test_two_dim_slice_breakdown_is_null_even_when_entry_matches_step(
    app: Flask,
) -> None:
    """
    GIVEN a breakdown filtered on a projection dim plus another dim, whose
        projection entry matches the step's own
    WHEN the flow is counted
    THEN the breakdown is null.
    """
    _seed_three_size_cells(app)

    steps = _run(
        app,
        [
            _opened(),
            _opened(
                (_SIZE, "21-50"),
                breakdown=_same_event_breakdown((_SIZE, "21-50"), (_AGE, "0-6d")),
            ),
        ],
    )

    assert steps[1].breakdown is None


def test_same_event_breakdown_under_cross_tab_suppressed_step_is_null(
    app: Flask,
) -> None:
    """
    GIVEN a step suppressed by rule (d) with an unfiltered same-event breakdown
    WHEN the flow is counted
    THEN the step is suppressed and the breakdown is null.
    """
    _seed_three_size_cells(app)

    steps = _run(
        app,
        [
            _opened(),
            _opened(
                (_SIZE, "21-50"),
                (_AGE, "0-6d"),
                breakdown=_same_event_breakdown(),
            ),
        ],
    )

    assert steps[1].count_suppressed is True
    assert steps[1].breakdown is None


def test_withhold_helper_fails_closed_for_unknown_or_equal_events() -> None:
    """
    GIVEN steps with an undeterminable, equal and different breakdown event
    WHEN the withhold decision is read
    THEN only the provably different event keeps the breakdown.
    """
    other = FlowStepBreakdown(event_name=EventName.UI_FORM_CANCEL, group_by="trigger")
    api_step = FlowStep(
        stream="api",
        label="api",
        api_endpoint="urls.create_url",
        api_method="POST",
        drop_breakdown=_same_event_breakdown(),
    )

    assert _suppressed_breakdown_withheld(api_step) is True
    assert _suppressed_breakdown_withheld(_opened(breakdown=_same_event_breakdown()))
    assert _suppressed_breakdown_withheld(_opened(breakdown=other)) is False


def test_suppressed_top_step_nulls_pct_of_top_everywhere(app: Flask) -> None:
    """
    GIVEN a flow whose first step is the absorbed 20-cell step
    WHEN the flow is counted
    THEN step 0 is suppressed with count 0 and every pct_of_top is null.
    """
    _seed_three_size_cells(app)

    steps = _run(
        app,
        [_opened((_SIZE, "6-20")), _opened((_SIZE, "21-50")), _opened()],
    )

    assert (steps[0].count, steps[0].count_suppressed) == (0, True)
    assert [step.pct_of_top for step in steps] == [None, None, None]


# --- fail closed, call counts, identity, non-regression -----------------------


@pytest.mark.parametrize("stub_rows", [[], [(SUPPRESSED_DIM_VALUE, 20)]])
def test_missing_or_sentinel_only_cell_view_fails_closed(
    app: Flask, monkeypatch: pytest.MonkeyPatch, stub_rows: list[tuple[str, int]]
) -> None:
    """
    GIVEN a cell view that omits the step's value or only holds the sentinel
    WHEN a positive-count projection step is counted
    THEN it is suppressed.
    """
    _seed_cell(app, size="6-20", age="0-6d", count=20)
    monkeypatch.setattr(flow_counting, "grouped_count_by", lambda **_: stub_rows)

    steps = _run(app, [_opened(), _opened((_SIZE, "6-20"))])

    assert (steps[1].count, steps[1].count_suppressed) == (0, True)


def test_two_projection_filters_are_suppressed_even_when_each_is_revealable(
    app: Flask,
) -> None:
    """
    GIVEN a cell of 20 where both 1-D cell views would reveal each value
    WHEN a step filters on both projection dims
    THEN rule (d) suppresses it; with a zero-count cell it reads (0, False).
    """
    _seed_cell(app, size="6-20", age="0-6d", count=20)

    steps = _run(
        app,
        [
            _opened(),
            _opened((_SIZE, "6-20"), (_AGE, "0-6d")),
            _opened((_SIZE, "6-20"), (_AGE, "7-29d")),
        ],
    )

    assert (steps[1].count, steps[1].count_suppressed) == (0, True)
    assert (steps[2].count, steps[2].count_suppressed) == (0, False)


def test_projection_plus_non_projection_closed_set_filter_is_suppressed(
    app: Flask,
) -> None:
    """
    GIVEN UI_FORM_CANCEL (projection `trigger`, non-projection `form`) with 20
    WHEN a step filters on both
    THEN rule (d) suppresses it.
    """
    with app.app_context():
        _seed_event_with_count(
            event_name=EventName.UI_FORM_CANCEL,
            category=EventCategory.UI,
            bucket_start=_bucket_inside_window(),
            count=20,
            dimensions={
                "trigger": "escape_key",
                "form": "url_create",
                "device_type": 2,
            },
        )
    step = FlowStep(
        stream="ui",
        label="Cancel",
        event_name=EventName.UI_FORM_CANCEL,
        dim_filter=[("trigger", "escape_key"), ("form", "url_create")],
    )
    top = FlowStep(stream="ui", label="Top", event_name=EventName.UI_FORM_CANCEL)

    steps = _run(app, [top, step])

    assert (steps[1].count, steps[1].count_suppressed) == (0, True)


def test_duplicated_projection_entry_is_counted_as_two_entries(app: Flask) -> None:
    """
    GIVEN a FlowStep built directly with a duplicated projection entry
    WHEN it is counted
    THEN entry counting suppresses it (fail closed).
    """
    _seed_cell(app, size="6-20", age="0-6d", count=20)

    steps = _run(app, [_opened(), _opened((_SIZE, "6-20"), (_SIZE, "6-20"))])

    assert (steps[1].count, steps[1].count_suppressed) == (0, True)


def test_cell_view_error_is_tagged_with_the_failing_step(
    app: Flask, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    GIVEN grouped_count_by raising ValueError for the cell view of step 1
    WHEN count_flow runs
    THEN FlowCountError carries step_index 1 and field steps.1.
    """
    _seed_cell(app, size="6-20", age="0-6d", count=20)

    def _raise(**_: Any) -> list[tuple[str, int]]:
        raise ValueError("boom")

    monkeypatch.setattr(flow_counting, "grouped_count_by", _raise)

    with pytest.raises(FlowCountError) as exc_info:
        _run(app, [_opened(), _opened((_SIZE, "6-20"))])

    assert exc_info.value.step_index == 1
    assert exc_info.value.field == "steps.1"


def _count_calls(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    real = flow_counting.grouped_count_by

    def _wrapper(**kwargs: Any) -> list[tuple[str, int]]:
        calls.append(kwargs)
        return real(**kwargs)

    monkeypatch.setattr(flow_counting, "grouped_count_by", _wrapper)
    return calls


def _count_one(app: Flask, step: FlowStep) -> tuple[int, bool]:
    window_start, window_end = _window()
    with app.app_context():
        return flow_counting._count_flow_step(step, window_start, window_end)


def test_extra_queries_only_for_projection_steps_reaching_the_cell_view(
    app: Flask, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    GIVEN a size cell of 10 on each device
    WHEN various step shapes are counted
    THEN unfiltered, device-only, API, non-projection and rule (a)/(d) steps
        issue zero grouped_count_by calls, a projection step one, and a
        device-filtered one two (own view plus the sibling's).
    """
    _seed_cell(app, size="6-20", age="0-6d", count=10, device=_MOBILE)
    _seed_cell(app, size="6-20", age="0-6d", count=10, device=_DESKTOP)
    with app.app_context():
        _seed_event_with_count(
            event_name=EventName.UI_FORM_CANCEL,
            category=EventCategory.UI,
            bucket_start=_bucket_inside_window(),
            count=3,
            dimensions={
                "trigger": "escape_key",
                "form": "utub_create",
                "device_type": 2,
            },
        )
    calls = _count_calls(monkeypatch)

    api_step = FlowStep(
        stream="api",
        label="api",
        api_endpoint="urls.create_url",
        api_method="POST",
    )
    form_step = FlowStep(
        stream="ui",
        label="form",
        event_name=EventName.UI_FORM_CANCEL,
        dim_filter=[("form", "url_create")],
    )
    for step in (
        _opened(),
        _opened(("device_type", "2")),
        api_step,
        form_step,
        FlowStep(
            stream="ui",
            label="floor",
            event_name=EventName.UI_FORM_CANCEL,
            dim_filter=[("form", "utub_create")],
        ),
        _opened((_SIZE, "6-20"), (_AGE, "0-6d")),
    ):
        _count_one(app, step)
    assert calls == []

    assert _count_one(app, _opened((_SIZE, "6-20"))) == (20, False)
    assert len(calls) == 1

    calls.clear()
    assert _count_one(app, _opened((_SIZE, "6-20"), ("device_type", "2"))) == (
        10,
        False,
    )
    assert len(calls) == 2
    assert calls[0]["dim_filter"] == [("device_type", "2")]
    assert calls[1]["dim_filter"] == [("device_type", "1")]


def test_device_identity_is_compared_as_integers(
    app: Flask, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    GIVEN a step whose device filter is written "02"
    WHEN it is counted
    THEN the sibling probed is exactly the other member ("1"), never its own.
    """
    _seed_cell(app, size="6-20", age="0-6d", count=10, device=_MOBILE)
    _seed_cell(app, size="6-20", age="0-6d", count=10, device=_DESKTOP)
    calls = _count_calls(monkeypatch)

    _count_one(app, _opened((_SIZE, "6-20"), ("device_type", "02")))

    assert len(calls) == 2
    assert calls[0]["dim_filter"] == [("device_type", "02")]
    assert calls[1]["dim_filter"] == [("device_type", "1")]


def test_device_identity_sibling_value_probes_the_other_member(
    app: Flask, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    GIVEN a step on device "1"
    WHEN it is counted
    THEN the sibling probed is exactly device "2".
    """
    _seed_cell(app, size="6-20", age="0-6d", count=10, device=_MOBILE)
    _seed_cell(app, size="6-20", age="0-6d", count=10, device=_DESKTOP)
    calls = _count_calls(monkeypatch)

    _count_one(app, _opened((_SIZE, "6-20"), ("device_type", "1")))

    assert len(calls) == 2
    assert calls[1]["dim_filter"] == [("device_type", "2")]


def test_same_event_breakdown_under_device_sibling_suppressed_step_is_null(
    app: Flask,
) -> None:
    """
    GIVEN a step suppressed only by the device-sibling rule (c) with a
        same-event breakdown
    WHEN the flow is counted
    THEN the step is suppressed and the breakdown is null.
    """
    _seed_cell(app, size="6-20", age="0-6d", count=3, device=_MOBILE)
    _seed_cell(app, size="6-20", age="0-6d", count=10, device=_DESKTOP)

    steps = _run(
        app,
        [
            _opened(),
            _opened(
                (_SIZE, "6-20"),
                ("device_type", "2"),
                breakdown=_same_event_breakdown(),
            ),
        ],
    )

    assert steps[1].count_suppressed is True
    assert steps[1].breakdown is None


def test_steps_agree_with_cell_views(app: Flask) -> None:
    """
    GIVEN size cells of 3, 20 and 30 and a device-split 3/10 cell
    WHEN steps and cell views are read
    THEN suppressed steps match "suppressed" in the view, the revealed step
        matches its real label, and the device-sibling-only step is a real
        label in its own device view.
    """
    for size, count in (("1-5", 3), ("6-20", 20), ("21-50", 30)):
        _seed_cell(app, size=size, age="0-6d", count=count)

    steps = _run(
        app,
        [_opened(), *[_opened((_SIZE, bucket)) for bucket in ("1-5", "6-20", "21-50")]],
    )

    assert [(step.count, step.count_suppressed) for step in steps[1:]] == [
        (0, True),
        (0, True),
        (30, False),
    ]


def test_zero_extra_queries_for_projection_step_below_floor(
    app: Flask, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    GIVEN a projection cell of 3
    WHEN its step is counted
    THEN rule (a) suppresses it with zero grouped_count_by calls.
    """
    _seed_cell(app, size="1-5", age="0-6d", count=3)
    calls = _count_calls(monkeypatch)

    assert _count_one(app, _opened((_SIZE, "1-5"))) == (0, True)
    assert calls == []


def test_non_projection_and_existing_projection_steps_are_unchanged(
    app: Flask,
) -> None:
    """
    GIVEN a URL_CREATE_REJECTED `reason` cell at exactly the floor, and a
        UI_FORM_CANCEL `form` (non-projection) cell at exactly the floor
    WHEN steps filtered on them are counted
    THEN both keep their real counts.
    """
    with app.app_context():
        _seed_event_with_count(
            event_name=EventName.URL_CREATE_REJECTED,
            category=EventCategory.DOMAIN,
            bucket_start=_bucket_inside_window(),
            count=MIN_CELL_COUNT,
            dimensions={"reason": "invalid_url", "device_type": 2},
        )
    _seed_cancel_row(app)
    rejected = FlowStep(
        stream="domain",
        label="Rejected",
        event_name=EventName.URL_CREATE_REJECTED,
        dim_filter=[("reason", "invalid_url")],
    )
    cancel = FlowStep(
        stream="ui",
        label="Cancel",
        event_name=EventName.UI_FORM_CANCEL,
        dim_filter=[("form", "url_create")],
    )

    assert _count_one(app, rejected) == (MIN_CELL_COUNT, False)
    assert _count_one(app, cancel) == (6, False)
