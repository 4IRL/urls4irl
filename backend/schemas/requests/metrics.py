from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    model_validator,
)

from backend.metrics.events import EVENT_CATEGORY, DeviceType, EventCategory, EventName
from backend.metrics.flow_ids import ALL_FLOW_IDS
from backend.metrics.resources import RESOURCE_BY_CATEGORY, Resource

_BOTH_WINDOW_AND_RANGE_ERROR: str = (
    "Provide either `window` or `start`+`end`, not both."
)
_PARTIAL_RANGE_ERROR: str = "Both `start` and `end` are required for an absolute range."
_MISSING_WINDOW_OR_RANGE_ERROR: str = "Provide `window` or both `start` and `end`."
_RANGE_ORDER_ERROR: str = "`start` must be strictly before `end`."
_RESOURCE_WITHOUT_CATEGORY_ERROR: str = (
    "`resource` requires `category` (api | domain | ui) so the filter "
    "knows which column to target."
)
_RESOURCE_INVALID_FOR_CATEGORY_ERROR_FMT: str = (
    "Resource `{resource}` is not valid for category `{category}`. "
    "Valid resources for `{category}`: {valid}."
)


def _validate_window_xor_range(
    window: str | None, start: datetime | None, end: datetime | None
) -> None:
    """Enforce: exactly one of (`window`) or (`start` AND `end`) is provided.

    Raises `ValueError` so Pydantic v2's `@model_validator(mode="after")`
    wraps it into a `ValidationError` that the metrics routes' shared
    `_parse_query_args` helper converts to a 400 envelope.
    """
    has_window = window is not None
    has_start = start is not None
    has_end = end is not None
    if has_start != has_end:
        raise ValueError(_PARTIAL_RANGE_ERROR)
    has_range = has_start and has_end
    if has_window and has_range:
        raise ValueError(_BOTH_WINDOW_AND_RANGE_ERROR)
    if not has_window and not has_range:
        raise ValueError(_MISSING_WINDOW_OR_RANGE_ERROR)
    if has_range and start >= end:
        raise ValueError(_RANGE_ORDER_ERROR)


def _validate_resource_for_category(category: str | None, resource: str | None) -> None:
    """Enforce: `resource` is paired with a `category` AND is a member of
    `RESOURCE_BY_CATEGORY[category]`.

    Resource-to-category coupling exists because the SQL filter targets
    different columns per category (`event_name` for UI/Domain,
    `endpoint` for API). Sending `resource` without `category` is therefore
    ambiguous and rejected at the schema layer.
    """
    if resource is None:
        return
    if category is None:
        raise ValueError(_RESOURCE_WITHOUT_CATEGORY_ERROR)
    category_enum = EventCategory(category)
    resource_enum = Resource(resource)
    valid_resources = RESOURCE_BY_CATEGORY[category_enum]
    if resource_enum not in valid_resources:
        raise ValueError(
            _RESOURCE_INVALID_FOR_CATEGORY_ERROR_FMT.format(
                resource=resource,
                category=category,
                valid=", ".join(member.value for member in valid_resources),
            )
        )


# Module-level tuple of every UI-category EventName value. Reused by:
#   * `MetricsIngestEvent.event_name` Literal definition (HTTP-boundary
#     restriction — the browser is the only legitimate UI emitter).
#   * Tests, to assert the schema's accepted values stay aligned with the
#     `EVENT_CATEGORY` source-of-truth without copy/pasting the list.
#   * OpenAPI generator readers, when documenting the union.
UI_EVENT_NAMES: tuple[str, ...] = tuple(
    member.value for member in EventName if EVENT_CATEGORY[member] is EventCategory.UI
)


# Python 3.11+ star-unpack into Literal (PEP 646). Verified at container
# startup — see Step 1 instructions in the plan. If support for 3.10 ever
# becomes required, build the union via `Literal[tuple_member_0, ...]`
# explicitly.
UIEventNameLiteral = Literal[*UI_EVENT_NAMES]  # type: ignore[valid-type]


class MetricsIngestEvent(BaseModel):
    """One UI metrics event submitted by the browser.

    Per-event dimension validation lives at the route layer
    (`validate_dimensions(...)`) — not in a `@model_validator` here. Pydantic
    v2 wraps `ValueError`/`AssertionError` raised inside validators, but a
    `ValidationError` raised inside a validator does NOT round-trip cleanly
    through that wrapper, so dimension shape checks happen post-decoration.
    """

    model_config = ConfigDict(extra="forbid")

    event_name: UIEventNameLiteral = Field(
        description="UI-category EventName value emitted by the browser",
    )
    dimensions: dict[str, str | int | bool] = Field(
        description=(
            "Per-event dimension dict; shape enforced server-side via the "
            "matching `_Dim<EventName>` Pydantic model. Auto-injected with "
            "`device_type` by the metrics-client for all UI events, so the "
            "dict is always non-empty when sent from the browser."
        ),
    )


class MetricsIngestRequest(BaseModel):
    """Top-level batch payload for `POST /api/metrics`."""

    model_config = ConfigDict(extra="forbid")

    # max_length=100 bounds worst-case worker-block time on the per-event Redis
    # write loop in routes.ingest (currently N sequential RTTs, see writer.record).
    # Frontend (Phase 5) must split larger flushes into multiple batches, each
    # with its own batch_id. Safe to raise once Redis writes are batched into
    # one pipeline and the new ceiling is bounded by validation/body-size cost.
    events: list[MetricsIngestEvent] = Field(
        min_length=1,
        max_length=100,
        description="Batch of UI-category metrics events to ingest (1-100 entries)",
    )
    batch_id: str | None = Field(
        default=None,
        max_length=128,
        description=(
            "Client-generated batch identifier; used server-side for SET NX EX "
            "idempotency on retries"
        ),
    )


class TransportQuerySchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transport: Literal["beacon"] | None = Field(
        default=None,
        description=(
            "Optional transport hint set by the metrics-client's `flushBeacon()` "
            "unload path; `flush()` omits the param. Reserved for future "
            "pipeline-health telemetry to distinguish fetch-vs-beacon transport "
            "volume in the `API_METRICS_INGEST_BATCH` event."
        ),
    )


# Module-level tuple of every EventName value (api + domain + ui). Used by the
# timeseries query schema, which accepts any event the registry tracks — not
# just the UI subset that the ingest endpoint admits.
ALL_EVENT_NAMES: tuple[str, ...] = tuple(member.value for member in EventName)


# Star-unpack into Literal mirrors the UIEventNameLiteral pattern above.
AllEventNameLiteral = Literal[*ALL_EVENT_NAMES]  # type: ignore[valid-type]


# Categories accepted by the `top` query endpoint's optional filter. Derived
# from `EventCategory` to stay in lockstep with the source of truth.
_ALL_EVENT_CATEGORIES: tuple[str, ...] = tuple(member.value for member in EventCategory)
CategoryLiteral = Literal[*_ALL_EVENT_CATEGORIES]  # type: ignore[valid-type]


# Resource taxonomy for the `top` query endpoint's optional filter. Derived
# from `Resource` to stay in lockstep with the source of truth.
_ALL_RESOURCES: tuple[str, ...] = tuple(member.value for member in Resource)
ResourceLiteral = Literal[*_ALL_RESOURCES]  # type: ignore[valid-type]


# `date_trunc` resolutions supported by the timeseries endpoint. Hour is the
# minimum useful resolution because writer.record floors bucket_start to the
# nearest METRICS_BUCKET_SECONDS=3600 boundary.
ResolutionLiteral = Literal["hour", "day"]


def _coerce_device_type_digit_string(value: object) -> object:
    """Coerce a digit-string device_type to its int form so DeviceType matches.

    Pydantic v2's IntEnum validator is strict and rejects `"1"` even in lax
    mode. Query params arrive via `request.args.to_dict()` as strings, so
    this `BeforeValidator` runs first to convert `"1"` -> `1` and `"2"` -> `2`.
    Non-matching inputs pass through unchanged for the enum validator to
    reject with its own error message.
    """
    if isinstance(value, str) and value.isdecimal():
        return int(value)
    return value


# `device_type` query-param boundary type. Binds directly to `DeviceType`
# (IntEnum: MOBILE=1, DESKTOP=2). Pydantic serialises the IntEnum as its
# integer value, so the wire contract and OpenAPI schema surface integer
# values (1, 2) while internal code uses the typed enum member.
DeviceTypeFilter = Annotated[
    DeviceType, BeforeValidator(_coerce_device_type_digit_string)
]


_WINDOW_FIELD_DESCRIPTION: str = (
    "Relative time window: day | week | month | year | Nh | Nd. "
    "Validated by parse_window() at the route layer. Mutually exclusive "
    "with `start`+`end`."
)
_START_FIELD_DESCRIPTION: str = (
    "Inclusive start of an absolute range (ISO-8601 with timezone — e.g., "
    "`2026-06-06T00:00:00Z` or `2026-06-06T00:00:00+05:00`). Naive "
    "datetimes are rejected at the schema layer via `AwareDatetime`. "
    "Must be paired with `end` and is mutually exclusive with `window`."
)
_END_FIELD_DESCRIPTION: str = (
    "Exclusive end of an absolute range (ISO-8601 with timezone — same "
    "format as `start`). Must be paired with `start` and is mutually "
    "exclusive with `window`."
)


class TopEventsQuerySchema(BaseModel):
    """Query params for `GET /api/metrics/query/top`.

    Accepts either a relative `window` (named or `Nh`/`Nd` shorthand,
    validated route-side by `parse_window()`) or an absolute `(start, end)`
    range. Pydantic `Literal` cannot express the named/shorthand union, so
    window validation stays at the route layer; the XOR between window and
    range is enforced by `_validate_window_xor_range` here.
    """

    model_config = ConfigDict(extra="forbid")

    window: str | None = Field(default=None, description=_WINDOW_FIELD_DESCRIPTION)
    start: AwareDatetime | None = Field(
        default=None, description=_START_FIELD_DESCRIPTION
    )
    end: AwareDatetime | None = Field(default=None, description=_END_FIELD_DESCRIPTION)
    category: CategoryLiteral | None = Field(
        default=None,
        description="Optional category filter (api | domain | ui).",
    )
    resource: ResourceLiteral | None = Field(
        default=None,
        description=(
            "Optional resource filter (utub | url | tag | member | auth | "
            "search | form | deck | nav | error | contact | admin | other). "
            "Requires `category`; the resource must appear in "
            "`RESOURCE_BY_CATEGORY[category]`."
        ),
    )
    device_type: DeviceTypeFilter | None = Field(
        default=None,
        description="Optional device-type filter (1=mobile, 2=desktop).",
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of rows to return (1-100).",
    )

    @model_validator(mode="after")
    def _check_window_xor_range(self) -> Self:
        _validate_window_xor_range(self.window, self.start, self.end)
        return self

    @model_validator(mode="after")
    def _check_resource_for_category(self) -> Self:
        _validate_resource_for_category(self.category, self.resource)
        return self


class TimeseriesQuerySchema(BaseModel):
    """Query params for `GET /api/metrics/query/timeseries`."""

    model_config = ConfigDict(extra="forbid")

    event_name: AllEventNameLiteral = Field(
        description="Any EventName value (api, domain, or ui).",
    )
    window: str | None = Field(default=None, description=_WINDOW_FIELD_DESCRIPTION)
    start: AwareDatetime | None = Field(
        default=None, description=_START_FIELD_DESCRIPTION
    )
    end: AwareDatetime | None = Field(default=None, description=_END_FIELD_DESCRIPTION)
    resolution: ResolutionLiteral = Field(
        default="hour",
        description="date_trunc resolution: hour (default) or day.",
    )
    endpoint: str | None = Field(
        default=None,
        description=(
            "Optional Flask endpoint name (e.g. utubs.get_single_utub). When "
            "supplied alongside event_name=api_hit, filters the series to only "
            "rows matching this endpoint — used by the admin dashboard's API "
            "tab to chart per-endpoint timeseries."
        ),
        max_length=255,
    )
    method: str | None = Field(
        default=None,
        description=(
            "Optional HTTP method (GET, POST, etc.). When supplied alongside "
            "event_name=api_hit, narrows the series to one (endpoint, method) "
            "pair so two methods on the same endpoint stay separate."
        ),
        max_length=10,
    )
    device_type: DeviceTypeFilter | None = Field(
        default=None,
        description="Optional device-type filter (1=mobile, 2=desktop).",
    )

    @model_validator(mode="after")
    def _check_window_xor_range(self) -> Self:
        _validate_window_xor_range(self.window, self.start, self.end)
        return self


class SummaryQuerySchema(BaseModel):
    """Query params for `GET /api/metrics/query/summary`."""

    model_config = ConfigDict(extra="forbid")

    window: str | None = Field(default=None, description=_WINDOW_FIELD_DESCRIPTION)
    start: AwareDatetime | None = Field(
        default=None, description=_START_FIELD_DESCRIPTION
    )
    end: AwareDatetime | None = Field(default=None, description=_END_FIELD_DESCRIPTION)

    @model_validator(mode="after")
    def _check_window_xor_range(self) -> Self:
        _validate_window_xor_range(self.window, self.start, self.end)
        return self


# Bounds on a single `filter` query entry, shared by the parser and the
# `@model_validator` so the wire contract and the error messages stay aligned.
_MAX_FILTER_ENTRIES: int = 8
_MAX_FILTER_KEY_LENGTH: int = 64
_MAX_FILTER_VALUE_LENGTH: int = 255

_FILTER_FORMAT_ERROR: str = (
    "Each `filter` entry must be `dim:value` with a non-empty dim before the "
    "first colon."
)
_FILTER_TOO_MANY_ERROR: str = (
    f"At most {_MAX_FILTER_ENTRIES} `filter` entries are allowed."
)
_FILTER_KEY_TOO_LONG_ERROR: str = (
    f"Each `filter` dim must be a non-empty string ≤{_MAX_FILTER_KEY_LENGTH} chars."
)
_FILTER_VALUE_TOO_LONG_ERROR: str = (
    f"Each `filter` value must be ≤{_MAX_FILTER_VALUE_LENGTH} chars."
)


def _parse_flow_filter_condition(value: object) -> object:
    """Split one `dim:value` filter scalar into a `(dim, value)` tuple.

    Per DD-2, the `filter` query param arrives as repeated colon-encoded
    scalars (`?filter=form:url_create&filter=trigger:escape_key`). Each scalar
    is split on the FIRST colon so dim values may themselves contain colons
    (e.g. a URL pattern). A `BeforeValidator` runs this before Pydantic binds
    the field to `tuple[str, str]`. Already-tuple inputs (e.g. constructed
    in-code) pass through unchanged so the schema is usable outside the HTTP
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
# `dim:value` query scalar via the `BeforeValidator` above.
FlowFilterCondition = Annotated[
    tuple[str, str], BeforeValidator(_parse_flow_filter_condition)
]


def _validate_flow_filter_entries(filter_conditions: list[tuple[str, str]]) -> None:
    """Bound the entry count and per-entry key/value lengths of a `filter` list.

    Mirrors `GroupedTimeseriesQuerySchema`'s `_check_group_by_entry_shape`
    entry validator: raises `ValueError` so Pydantic wraps it into a
    `ValidationError` the route layer maps to a 400.
    """
    if len(filter_conditions) > _MAX_FILTER_ENTRIES:
        raise ValueError(_FILTER_TOO_MANY_ERROR)
    for dim_key, dim_value in filter_conditions:
        if not dim_key or len(dim_key) > _MAX_FILTER_KEY_LENGTH:
            raise ValueError(_FILTER_KEY_TOO_LONG_ERROR)
        if len(dim_value) > _MAX_FILTER_VALUE_LENGTH:
            raise ValueError(_FILTER_VALUE_TOO_LONG_ERROR)


class FlowFilterParamsSchema(BaseModel):
    """Reusable `filter` + `group_by` query-param carrier for flow slicing.

    Defines the dim-slicing primitives consumed by `grouped_counts`:
      * `filter` — an AND-joined list of `(dim, value)` predicates, each parsed
        from a `dim:value` query scalar (DD-2). Repeated `?filter=...` keys are
        promoted to a list by the route's
        `_parse_query_args(..., multi_value_keys=frozenset({"filter"}))`.
      * `group_by` — a single dim name to group the aggregate by.

    Step 3's `FlowQuerySchema` carries `flow_id` + window and the per-flow
    slicing is configured server-side in the `FLOWS` registry, so this schema
    holds only the reusable slicing fields for direct/ad-hoc use and tests.
    """

    model_config = ConfigDict(extra="forbid")

    filter: list[FlowFilterCondition] | None = Field(
        default=None,
        description=(
            "List of AND-joined `dim:value` filter predicates. Each entry is "
            "parsed from a colon-encoded query scalar; repeated `filter` keys "
            "build the list. Bounded to "
            f"{_MAX_FILTER_ENTRIES} entries, dims ≤{_MAX_FILTER_KEY_LENGTH} "
            f"chars, values ≤{_MAX_FILTER_VALUE_LENGTH} chars."
        ),
    )
    group_by: str | None = Field(
        default=None,
        max_length=_MAX_FILTER_KEY_LENGTH,
        description=(
            "Optional single dimension name to group the flat aggregate by. "
            "When omitted, `grouped_counts` returns a scalar total."
        ),
    )

    @model_validator(mode="after")
    def _check_filter_entry_shape(self) -> Self:
        if self.filter is not None:
            _validate_flow_filter_entries(self.filter)
        return self


# Module-level tuple of every FlowId value, mirroring `ALL_EVENT_NAMES`. Built
# from the `flows` registry's `FlowId` StrEnum so the query schema's accepted
# flow ids stay in lockstep with the source of truth.
FlowIdLiteral = Literal[*ALL_FLOW_IDS]  # type: ignore[valid-type]


class FlowQuerySchema(BaseModel):
    """Query params for `GET /api/metrics/query/flow`.

    Carries the funnel selector (`flow_id`) plus the same window/range XOR all
    other window-bearing query schemas use. The per-step `filter`/`group_by`
    slicing is configured server-side in the `FLOWS` registry — the caller only
    names the flow and the time window.
    """

    model_config = ConfigDict(extra="forbid")

    flow_id: FlowIdLiteral = Field(
        description="Which funnel to assemble (create_utub | add_url_to_utub | "
        "register | login).",
    )
    window: str | None = Field(default=None, description=_WINDOW_FIELD_DESCRIPTION)
    start: AwareDatetime | None = Field(
        default=None, description=_START_FIELD_DESCRIPTION
    )
    end: AwareDatetime | None = Field(default=None, description=_END_FIELD_DESCRIPTION)

    @model_validator(mode="after")
    def _check_window_xor_range(self) -> Self:
        _validate_window_xor_range(self.window, self.start, self.end)
        return self


class GroupedTimeseriesQuerySchema(BaseModel):
    """Query params for `GET /api/metrics/query/grouped-timeseries`.

    Returns one row per `(bucket × dim tuple)` instead of the single per-bucket
    series produced by `timeseries`. Each `group_by` entry must be a dimension
    field declared on `DIMENSION_MODELS[event_name]` — validated at the route
    layer (the schema cannot bind to a per-event Literal because the valid set
    depends on the requested event).

    `group_by` arrives as repeated query-string keys
    (`?group_by=transport&group_by=device_type`); the metrics-routes shared
    `_parse_query_args(..., multi_value_keys=frozenset({"group_by"}))` helper
    promotes those occurrences from a flat string to a list before validation.
    """

    model_config = ConfigDict(extra="forbid")

    event_name: AllEventNameLiteral = Field(
        description="Any EventName value (api, domain, or ui).",
    )
    group_by: list[str] = Field(
        min_length=1,
        max_length=3,
        description=(
            "List of dimension field names to group the timeseries by. Each "
            "entry must be a field of `DIMENSION_MODELS[event_name]` (validated "
            "at the route layer); shape is bounded at the schema layer to "
            "1-3 non-empty entries ≤64 chars each."
        ),
    )
    window: str | None = Field(default=None, description=_WINDOW_FIELD_DESCRIPTION)
    start: AwareDatetime | None = Field(
        default=None, description=_START_FIELD_DESCRIPTION
    )
    end: AwareDatetime | None = Field(default=None, description=_END_FIELD_DESCRIPTION)
    resolution: ResolutionLiteral = Field(
        default="hour",
        description="date_trunc resolution: hour (default) or day.",
    )

    @model_validator(mode="after")
    def _check_window_xor_range(self) -> Self:
        _validate_window_xor_range(self.window, self.start, self.end)
        return self

    @model_validator(mode="after")
    def _check_group_by_entry_shape(self) -> Self:
        for entry in self.group_by:
            if not entry or len(entry) > 64:
                raise ValueError(
                    "Each `group_by` entry must be a non-empty string ≤64 chars."
                )
        return self
