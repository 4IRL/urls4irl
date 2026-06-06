from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.metrics.events import EVENT_CATEGORY, EventCategory, EventName

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


# `date_trunc` resolutions supported by the timeseries endpoint. Hour is the
# minimum useful resolution because writer.record floors bucket_start to the
# nearest METRICS_BUCKET_SECONDS=3600 boundary.
ResolutionLiteral = Literal["hour", "day"]


class TopEventsQuerySchema(BaseModel):
    """Query params for `GET /api/metrics/query/top`.

    `window` is a free-form string so the route can lean on
    `parse_window()`'s `ValueError → 400` plumbing for both named windows
    (`day`, `week`, ...) and `Nh`/`Nd` shorthand. Pydantic `Literal` cannot
    express both shapes simultaneously, so validation is route-level.
    """

    model_config = ConfigDict(extra="forbid")

    window: str = Field(
        description=(
            "Time window: day | week | month | year | Nh | Nd. "
            "Validated by parse_window() at the route layer."
        ),
    )
    category: CategoryLiteral | None = Field(
        default=None,
        description="Optional category filter (api | domain | ui).",
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of rows to return (1-100).",
    )


class TimeseriesQuerySchema(BaseModel):
    """Query params for `GET /api/metrics/query/timeseries`."""

    model_config = ConfigDict(extra="forbid")

    event_name: AllEventNameLiteral = Field(
        description="Any EventName value (api, domain, or ui).",
    )
    window: str = Field(
        description=(
            "Time window: day | week | month | year | Nh | Nd. "
            "Validated by parse_window() at the route layer."
        ),
    )
    resolution: ResolutionLiteral = Field(
        default="hour",
        description="date_trunc resolution: hour (default) or day.",
    )


class SummaryQuerySchema(BaseModel):
    """Query params for `GET /api/metrics/query/summary`."""

    model_config = ConfigDict(extra="forbid")

    window: str = Field(
        description=(
            "Time window: day | week | month | year | Nh | Nd. "
            "Validated by parse_window() at the route layer."
        ),
    )
