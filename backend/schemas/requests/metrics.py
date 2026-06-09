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

from backend.metrics.events import EVENT_CATEGORY, EventCategory, EventName
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
    """Coerce a digit-string device_type to its int form so Literal[1, 2] matches.

    Pydantic v2's `Literal[int]` is strict and rejects `"1"` even in lax mode.
    Query params arrive via `request.args.to_dict()` as strings, so this
    `BeforeValidator` runs first to convert `"1"` -> `1` and `"2"` -> `2`.
    Non-matching inputs pass through unchanged for the literal validator to
    reject with its own error message.
    """
    if isinstance(value, str) and value.isdecimal():
        return int(value)
    return value


# `device_type` query-param boundary type. `Literal[1, 2]` matches the
# `DeviceType` IntEnum (MOBILE=1, DESKTOP=2) but is exposed as a plain int
# literal so the wire contract is self-documenting in OpenAPI.
DeviceTypeFilter = Annotated[
    Literal[1, 2], BeforeValidator(_coerce_device_type_digit_string)
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
