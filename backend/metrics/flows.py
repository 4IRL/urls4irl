"""Declarative registry of admin-dashboard conversion funnels ("flows").

A *flow* is an ordered, variable-length funnel — a `list[FlowStep]` of 2..N
steps — that joins the three metric streams (browser UI, request API, service
DOMAIN) into one intent → request → outcome view for a single user action.
Each step names the event it counts and may carry an optional drop-off
breakdown explaining WHY users dropped between the previous step and this one:

    step[0]  →  step[1]  →  step[2]  →  …  →  step[N-1]
     (top)        ↘ drop_breakdown (by trigger / reason, optional per step)

Each flow is one `FlowDefinition` entry in `FLOWS`, holding `display_name` and
an ordered `steps` list. The `/api/metrics/query/flow` endpoint loops over
`flow.steps`, fanning out one `grouped_count_scalar()` call per step (plus one
`grouped_count_by()` per drop_breakdown) over the requested window; nothing is
inferred from the data —
the steps are exactly the events named here. The first step is the funnel top
(the `pct_of_top` denominator).

Adding a new funnel
-------------------
1. Add a member to `FlowId` (StrEnum; value = lowercase member name).
2. Add `FLOWS[FlowId.X] = FlowDefinition(display_name=..., steps=[...])`,
   appending/composing `FlowStep` entries in order. Each `FlowStep`:
     - stream            'ui' | 'api' | 'domain' (drives renderer coloring)
     - label             display label for this step (becomes one entry in
                         stepLabels in metrics-flows.ts)
     - event_name        the event counted for this step; None for an API step
     - api_endpoint +    for stream='api' steps, matched against API_HIT's flat
       api_method        endpoint/method columns — NOT a dimension. api_endpoint
                         must be the Flask endpoint name (e.g. 'urls.create_url'),
                         NOT the URL pattern. Run `flask routes` or check
                         ENDPOINT_REGISTRY.md for the correct value. Exactly one
                         of (event_name) or (api_endpoint+api_method) must be set
     - dim_filter        optional per-step AND-filter (e.g. [("form","login")])
     - drop_breakdown    optional FlowStepBreakdown(event_name, dim_filter, group_by)
                         explaining the drop from the previous step (e.g.
                         UI_FORM_CANCEL grouped by "trigger", or a rejection
                         event grouped by "reason"). Each step carries at most
                         one drop_breakdown. If a transition has two independent
                         drop-off causes, either (a) track only the most
                         informative one, or (b) define two adjacent steps whose
                         breakdowns cover each cause independently.
   Every referenced event must already exist in `EventName` / `EVENT_REGISTRY`
   / `DIMENSION_MODELS`.
3. If you introduced a NEW event, do the 3-file authored change (events.py +
   event_registry.py + dimension_models.py) AND add a real `record_event(...)`
   emit in the service layer — a FlowDefinition reference alone does NOT satisfy
   the orphan check in audit.py.
4. Run `make generate-types` (regenerates metrics-flows.ts) and `make audit`;
   stage the regenerated frontend/types/ files in the same commit.

The frontend renders any flow generically from the `/flow` response — N rows
plus N-1 connectors driven by the response step list — so a new funnel needs no
TS changes beyond the regenerated metrics-flows.ts.

This file is intentionally kept out of audit.py's `_METRICS_INTERNAL_FILES` so
referencing an event here never masks a missing real emit.

Denominator note
----------------
`pct_of_top` is denominated against `steps[0].count`, which for most flows is a
browser-emitted (beacon-droppable) UI-open event that can silently undercount, so
conversion rates may be slightly overstated. The `min()` cap in the handler
prevents nonsensical >100% values when downstream steps exceed the denominator.
`API_HIT` for each flow's request step provides an independent server-side
lower-bound cross-check. `API_HIT` is NOT used as the denominator because it
counts non-UI (CLI/bot/test) traffic that inflates the step count relative to
genuine user intent. There is no `denominator_step_index` config field — the
first step is always the denominator.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator

from backend.metrics.events import EventName

__all__ = [
    "ALL_FLOW_IDS",
    "FLOWS",
    "FlowDefinition",
    "FlowFilterCondition",
    "FlowId",
    "FlowStep",
    "FlowStepBreakdown",
]

_FLOW_STEP_XOR_ERROR: str = (
    "A FlowStep must set exactly one of `event_name` or "
    "(`api_endpoint` + `api_method`)."
)
_FLOW_DEFINITION_MIN_STEPS_ERROR: str = (
    "A FlowDefinition must declare at least 2 steps."
)
_FILTER_FORMAT_ERROR: str = (
    "Each `filter` entry must be `dim:value` with a non-empty dim before the "
    "first colon."
)


class FlowId(StrEnum):
    CREATE_UTUB = "create_utub"
    ADD_URL_TO_UTUB = "add_url_to_utub"
    REGISTER = "register"
    LOGIN = "login"


# Module-level tuple of every FlowId value. Reused by `FlowIdLiteral` in the
# query schema and by `generate_flows_ts()` so the wire contract and the
# codegen surface stay aligned with this source of truth.
ALL_FLOW_IDS: tuple[str, ...] = tuple(member.value for member in FlowId)


def parse_flow_filter_condition(value: object) -> object:
    """Split one `dim:value` filter scalar into a `(dim, value)` tuple.

    Per DD-2, a colon-encoded filter scalar (`form:url_create`) is split on the
    FIRST colon so dim values may themselves contain colons (e.g. a URL
    pattern). A `BeforeValidator` runs this before Pydantic binds the field to
    `tuple[str, str]`. Already-tuple inputs (e.g. the in-code `FLOWS` registry
    entries) pass through unchanged so the type is usable outside any HTTP
    boundary.

    Examples:
        "form:url_create"        -> ("form", "url_create")
        "endpoint:urls.create"   -> ("endpoint", "urls.create")
        ("form", "url_create")   -> ("form", "url_create")
    """
    if isinstance(value, tuple):
        return value
    if not isinstance(value, str) or ":" not in value:
        raise ValueError(_FILTER_FORMAT_ERROR)
    dim_key, _, dim_value = value.partition(":")
    if not dim_key:
        raise ValueError(_FILTER_FORMAT_ERROR)
    return (dim_key, dim_value)


# A single parsed AND-filter predicate: `(dim, value)`. Bound from a
# `dim:value` scalar via the `BeforeValidator` above.
FlowFilterCondition = Annotated[
    tuple[str, str], BeforeValidator(parse_flow_filter_condition)
]


class FlowStepBreakdown(BaseModel):
    """Per-cause breakdown of WHY users dropped into the owning step.

    The `/flow` handler fans out one extra `grouped_count_by(group_by=...)` call
    per breakdown, then exposes the result as the step's `breakdown` rows
    (or `null` when the breakdown event has no rows in the window — DD-6).
    """

    model_config = ConfigDict(extra="forbid")

    event_name: EventName = Field(
        description="The event whose grouped counts explain the drop-off."
    )
    dim_filter: list[FlowFilterCondition] | None = Field(
        default=None,
        description="Optional AND-filter scoping the breakdown (e.g. form scope).",
    )
    group_by: str = Field(
        description="Dimension the breakdown is grouped by (e.g. 'trigger', 'reason')."
    )


class FlowStep(BaseModel):
    """One ordered step of a funnel.

    Exactly one of (`event_name`) or (`api_endpoint` + `api_method`) is set:
    UI/DOMAIN steps count an event by name; API steps match `API_HIT`'s flat
    promoted columns instead.
    """

    model_config = ConfigDict(extra="forbid")

    stream: Literal["ui", "api", "domain"] = Field(
        description="Metric stream — drives renderer coloring/category."
    )
    label: str = Field(description="Display label for this step.")
    event_name: EventName | None = Field(
        default=None,
        description="The event counted for this step; None for an API step.",
    )
    # Flask endpoint name as stored by the API_HIT middleware (e.g. 'urls.create_url');
    # NOT the URL pattern.
    api_endpoint: str | None = Field(
        default=None,
        description=(
            "Flask endpoint name matched against API_HIT's flat `endpoint` column "
            "for stream='api' steps; NOT a dimension and NOT the URL pattern."
        ),
    )
    api_method: str | None = Field(
        default=None,
        description="HTTP method matched against API_HIT's flat `method` column.",
    )
    dim_filter: list[FlowFilterCondition] | None = Field(
        default=None,
        description="Optional per-step AND-filter applied to this step's count.",
    )
    drop_breakdown: FlowStepBreakdown | None = Field(
        default=None,
        description=(
            "Optional per-cause breakdown of the drop-off between the PREVIOUS "
            "step and THIS step. None when this step has no drop-off explanation."
        ),
    )

    @model_validator(mode="after")
    def _check_event_xor_api(self) -> Self:
        has_event = self.event_name is not None
        has_api = self.api_endpoint is not None or self.api_method is not None
        if has_event == has_api:
            raise ValueError(_FLOW_STEP_XOR_ERROR)
        return self


class FlowDefinition(BaseModel):
    """A single funnel: an ordered list of 2..N steps under a display name."""

    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(description="Human-readable funnel name.")
    steps: list[FlowStep] = Field(
        description="Ordered funnel steps (2..N); steps[0] is the denominator top."
    )

    @model_validator(mode="after")
    def _check_min_steps(self) -> Self:
        if len(self.steps) < 2:
            raise ValueError(_FLOW_DEFINITION_MIN_STEPS_ERROR)
        return self


FLOWS: dict[FlowId, FlowDefinition] = {
    FlowId.CREATE_UTUB: FlowDefinition(
        display_name="Create UTub",
        steps=[
            FlowStep(
                stream="ui",
                label="Open UTub form",
                event_name=EventName.UI_UTUB_CREATE_OPEN,
            ),
            FlowStep(
                stream="ui",
                label="Submit",
                event_name=EventName.UI_FORM_SUBMIT,
                dim_filter=[("form", "utub_create")],
                drop_breakdown=FlowStepBreakdown(
                    event_name=EventName.UI_FORM_CANCEL,
                    dim_filter=[("form", "utub_create")],
                    group_by="trigger",
                ),
            ),
            FlowStep(
                stream="api",
                label="POST /utubs",
                api_endpoint="utubs.create_utub",
                api_method="POST",
            ),
            FlowStep(
                stream="domain",
                label="UTub created",
                event_name=EventName.UTUB_CREATED,
            ),
        ],
    ),
    FlowId.ADD_URL_TO_UTUB: FlowDefinition(
        display_name="Add URL to UTub",
        steps=[
            FlowStep(
                stream="ui",
                label="Open URL form",
                event_name=EventName.UI_URL_CREATE_OPEN,
            ),
            FlowStep(
                stream="ui",
                label="Submit",
                event_name=EventName.UI_FORM_SUBMIT,
                dim_filter=[("form", "url_create")],
                drop_breakdown=FlowStepBreakdown(
                    event_name=EventName.UI_FORM_CANCEL,
                    dim_filter=[("form", "url_create")],
                    group_by="trigger",
                ),
            ),
            FlowStep(
                stream="api",
                label="POST .../urls",
                api_endpoint="urls.create_url",
                api_method="POST",
            ),
            FlowStep(
                stream="domain",
                label="URL added",
                event_name=EventName.URL_ADDED_TO_UTUB,
                drop_breakdown=FlowStepBreakdown(
                    event_name=EventName.URL_CREATE_REJECTED,
                    group_by="reason",
                ),
            ),
        ],
    ),
    FlowId.REGISTER: FlowDefinition(
        display_name="Register",
        steps=[
            FlowStep(
                stream="ui",
                label="Open register form",
                event_name=EventName.UI_AUTH_MODAL_OPEN,
                dim_filter=[("form", "register")],
            ),
            FlowStep(
                stream="ui",
                label="Submit",
                event_name=EventName.UI_REGISTER_SUBMIT,
                drop_breakdown=FlowStepBreakdown(
                    event_name=EventName.UI_AUTH_CANCEL,
                    dim_filter=[("form", "register")],
                    group_by="trigger",
                ),
            ),
            FlowStep(
                stream="api",
                label="POST /register",
                api_endpoint="splash.register_user",
                api_method="POST",
            ),
            FlowStep(
                stream="domain",
                label="Registered",
                event_name=EventName.REGISTER_SUCCESS,
                drop_breakdown=FlowStepBreakdown(
                    event_name=EventName.REGISTER_REJECTED,
                    group_by="reason",
                ),
            ),
        ],
    ),
    FlowId.LOGIN: FlowDefinition(
        display_name="Login",
        steps=[
            FlowStep(
                stream="ui",
                label="Open login form",
                event_name=EventName.UI_AUTH_MODAL_OPEN,
                dim_filter=[("form", "login")],
            ),
            FlowStep(
                stream="ui",
                label="Submit",
                event_name=EventName.UI_LOGIN_SUBMIT,
                drop_breakdown=FlowStepBreakdown(
                    event_name=EventName.UI_AUTH_CANCEL,
                    dim_filter=[("form", "login")],
                    group_by="trigger",
                ),
            ),
            FlowStep(
                stream="api",
                label="POST /login",
                api_endpoint="splash.login",
                api_method="POST",
            ),
            FlowStep(
                stream="domain",
                label="Logged in",
                event_name=EventName.LOGIN_SUCCESS,
                drop_breakdown=FlowStepBreakdown(
                    event_name=EventName.LOGIN_FAILURE,
                    group_by="reason",
                ),
            ),
        ],
    ),
}
