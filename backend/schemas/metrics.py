from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import AwareDatetime, Field, GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema

from backend.schemas.base import BaseSchema


class MetricsIngestResponseSchema(BaseSchema):
    """Response payload returned by `POST /api/metrics`.

    `accepted` is the number of events that the route handed off to
    `record_event(...)`. Because the writer is log-and-drop, individual events
    may have been silently dropped at the Redis layer; the field is informative
    but not authoritative.
    """

    accepted: int = Field(
        default=0,
        description="Count of events accepted by the metrics ingest endpoint",
    )


class TopEventRow(BaseSchema):
    """One row of the `top` query response — a single event aggregated over the window."""

    event_name: str = Field(description="EventName value (e.g. utub_opened)")
    category: str = Field(description="EventCategory value (api | domain | ui)")
    description: str = Field(
        description=(
            "Human-readable event description. For UI/domain rows this comes "
            "from EventRegistry; for API rows it comes from the route's "
            "`@api_route(description=...)` kwarg."
        ),
    )
    api_endpoint: str | None = Field(
        default=None,
        description=(
            "Raw Flask endpoint name (e.g. `utubs.get_single_utub`) — populated "
            "only for API-category rows so the dashboard can filter the "
            "timeseries chart by the exact column value stored in "
            "`AnonymousMetrics.endpoint`. Null for UI/domain rows."
        ),
    )
    total_count: int = Field(
        description="Sum of counts across all buckets in the window"
    )
    previous_count: int = Field(
        default=0,
        description=(
            "Sum of counts for the same event across the immediately-preceding "
            "window of equal length. Zero when the event did not appear in the "
            "previous window. Used by the admin dashboard to render per-event "
            "delta-vs-prev arrows."
        ),
    )

    @classmethod
    def __get_pydantic_json_schema__(
        cls,
        core_schema: CoreSchema,
        handler: GetJsonSchemaHandler,
    ) -> JsonSchemaValue:
        """Mark `api_endpoint` and `previous_count` as required in the JSON schema.

        Both fields carry Python-level defaults so the model can be constructed
        with `api_endpoint` omitted (UI/domain rows) or `previous_count` omitted
        (no previous-window data). The backend nevertheless always emits both
        keys, so downstream OpenAPI consumers should treat them as guaranteed-
        present.
        """
        json_schema: dict[str, Any] = handler(core_schema)
        required = list(json_schema.get("required", []))
        for guaranteed_field in ("api_endpoint", "previous_count"):
            if guaranteed_field not in required:
                required.append(guaranteed_field)
        json_schema["required"] = required
        return json_schema


class TopEventsResponseSchema(BaseSchema):
    """Envelope returned by `GET /api/metrics/query/top`."""

    window: str | None = Field(
        default=None,
        description=(
            "Window value as supplied by the client; null when the client "
            "supplied an absolute `start`/`end` range instead."
        ),
    )
    window_start: datetime = Field(description="Inclusive UTC start of the window")
    window_end: datetime = Field(description="Exclusive UTC end of the window")
    category: str | None = Field(
        default=None,
        description="EventCategory filter applied to the query, or null if none",
    )
    resource: str | None = Field(
        default=None,
        description=(
            "Resource filter applied to the query (utub | url | tag | member | "
            "auth | search | form | deck | nav | error | contact | admin | "
            "other), or null if none. Requires `category` to also be set."
        ),
    )
    events: list[TopEventRow] = Field(
        description="Top-N rows ordered by total_count descending",
    )


class TimeseriesBucketSchema(BaseSchema):
    """One bucket of the `timeseries` query response."""

    bucket: datetime = Field(
        description="Bucket start (UTC, date_trunc'd to resolution)"
    )
    count: int = Field(description="Sum of counts within this bucket")


class TimeseriesResponseSchema(BaseSchema):
    """Envelope returned by `GET /api/metrics/query/timeseries`."""

    event_name: str = Field(description="EventName the series is filtered to")
    window: str | None = Field(
        default=None,
        description=(
            "Window value as supplied by the client; null when the client "
            "supplied an absolute `start`/`end` range instead."
        ),
    )
    resolution: str = Field(description="date_trunc resolution (hour | day)")
    window_start: datetime = Field(description="Inclusive UTC start of the window")
    window_end: datetime = Field(description="Exclusive UTC end of the window")
    buckets: list[TimeseriesBucketSchema] = Field(
        description="Buckets in chronological order",
    )


class GroupedTimeseriesBucket(BaseSchema):
    """One row of the `grouped-timeseries` response — a single bucket × dim-tuple."""

    bucket: AwareDatetime = Field(
        description="Bucket start (UTC, date_trunc'd to resolution)"
    )
    dimensions: dict[str, str | int] = Field(
        description=(
            "The dimension-tuple values for this row, keyed by the requested "
            "`group_by` fields. Closed-set values come from the per-event "
            "Literal dim model; typed loosely (`str | int`) for transport."
        ),
    )
    count: int = Field(description="Sum of counts within this (bucket, dim-tuple)")


class GroupedTimeseriesResponseSchema(BaseSchema):
    """Envelope returned by `GET /api/metrics/query/grouped-timeseries`.

    Unlike the single-series `timeseries` endpoint, the grouped variant does
    NOT zero-fill empty `(bucket, dim-tuple)` combinations. Cross-product
    expansion is expensive; the frontend renderer treats absent combos as
    "no segment for that bucket".
    """

    event_name: str = Field(description="EventName the series is filtered to")
    window: str | None = Field(
        default=None,
        description=(
            "Window value as supplied by the client; null when the client "
            "supplied an absolute `start`/`end` range instead."
        ),
    )
    resolution: Literal["hour", "day"] = Field(
        description="date_trunc resolution (hour | day)",
    )
    window_start: AwareDatetime = Field(
        description="Inclusive UTC start of the window",
    )
    window_end: AwareDatetime = Field(
        description="Exclusive UTC end of the window",
    )
    group_by: list[str] = Field(
        description="Dimension field names the series is grouped by",
    )
    buckets: list[GroupedTimeseriesBucket] = Field(
        description=(
            "Per-(bucket × dim tuple) rows, ordered chronologically and then "
            "alphabetically by dim values for deterministic output. NOT zero-"
            "filled — missing combinations are absent rather than zero-valued."
        ),
    )


class SummaryCategoryCount(BaseSchema):
    """Per-category current/previous totals for the `summary` query response.

    Returned as a list (not a dict) because `APIResponse` spreads payloads into
    the top-level JSON body — a dict-of-category-to-int would collide with the
    envelope's reserved keys.
    """

    category: str = Field(description="EventCategory value (api | domain | ui)")
    current: int = Field(description="Sum of counts in the current window")
    previous: int = Field(
        description="Sum of counts in the immediately-preceding window"
    )


class SummaryResponseSchema(BaseSchema):
    """Envelope returned by `GET /api/metrics/query/summary`."""

    window: str | None = Field(
        default=None,
        description=(
            "Window value as supplied by the client; null when the client "
            "supplied an absolute `start`/`end` range instead."
        ),
    )
    window_start: datetime = Field(description="Inclusive UTC start of the window")
    window_end: datetime = Field(description="Exclusive UTC end of the window")
    previous_window_start: datetime = Field(
        description="Inclusive UTC start of the immediately-preceding window",
    )
    previous_window_end: datetime = Field(
        description="Exclusive UTC end of the immediately-preceding window",
    )
    last_flush_at: AwareDatetime | None = Field(
        default=None,
        description=(
            "Flush worker's liveness sentinel — UTC timestamp parsed from the "
            "`metrics:flush:last_success_epoch` Redis key, which the worker "
            "stamps on every successful run (including empty flushes). "
            "Reflects worker cadence, NOT data freshness — advances every "
            "minute regardless of traffic. Null when metrics are disabled, "
            "the sentinel is absent, or Redis is unreachable."
        ),
    )
    last_event_at: AwareDatetime | None = Field(
        default=None,
        description=(
            "Wall-clock timestamp of the most recent AnonymousMetrics bucket "
            "(`MAX(bucketStart)`); null when the table is empty. Reflects "
            "when the last event was bucketed — advances only when traffic "
            "lands. Surfaced separately from `last_flush_at` so an admin can "
            "distinguish 'worker is dead' from 'nobody is using the app'."
        ),
    )
    by_category: list[SummaryCategoryCount] = Field(
        description="Per-category current vs. previous totals",
    )


class FlowBreakdownRow(BaseSchema):
    """One per-cause row of a flow step's drop-off breakdown.

    `pct_of_step` normalizes WITHIN the breakdown (all rows sum to ~1.0) so
    cause-pill widths are self-consistent regardless of the step's absolute
    count. It is a `float` (never null): a breakdown with no rows collapses to
    `null` on the owning step (DD-6) before any row is constructed.
    """

    label: str = Field(
        description=(
            "Raw dimension value for this cause (e.g. 'escape_key', "
            "'invalid_url'); the renderer maps it to a human-readable label."
        ),
    )
    count: int = Field(description="Summed count for this cause in the window.")
    pct_of_step: float = Field(
        description=(
            "Fraction of the breakdown total this cause represents (0.0-1.0); "
            "all rows in one breakdown sum to ~1.0."
        ),
    )


class FlowStepSchema(BaseSchema):
    """One step of an assembled funnel returned by `GET /api/metrics/query/flow`."""

    stream: Literal["ui", "api", "domain"] = Field(
        description="Metric stream — drives renderer coloring/category.",
    )
    label: str = Field(description="Display label for this step.")
    event_name: str = Field(
        description=(
            "The underlying event name counted for this step; for API steps "
            "this carries the step's display label instead (the Flask endpoint "
            "name is an internal routing identifier, not display-suitable)."
        ),
    )
    count: int = Field(description="Summed count for this step in the window.")
    pct_of_top: float | None = Field(
        default=None,
        description=(
            "This step's count as a fraction of the funnel-top (steps[0]) "
            "count, capped at 1.0. Null when the top count is zero "
            "(division-by-zero guard, DD-6 graceful-degrade)."
        ),
    )
    breakdown: list[FlowBreakdownRow] | None = Field(
        default=None,
        description=(
            "Per-cause drop-off rows for the transition INTO this step; null "
            "when the step has no configured breakdown or the breakdown event "
            "has no rows in the window (DD-6 graceful-degrade)."
        ),
    )


class FlowResponseSchema(BaseSchema):
    """Envelope returned by `GET /api/metrics/query/flow`.

    A `steps` wrapper (not a bare list) is required because
    `APIResponse.to_response()` spreads the payload via `**data_dict`, which
    needs a `BaseModel`-derived schema; the wire payload is `{"steps": [...]}`.
    """

    steps: list[FlowStepSchema] = Field(
        description=(
            "Ordered funnel steps assembled server-side from the FLOWS "
            "registry; one entry per FlowDefinition step, in funnel order."
        ),
    )


class GaugeSampleSchema(BaseSchema):
    """One sampled point of a gauge's timeseries.

    COUNT/MAX gauges populate `value_int`; AVG gauges populate `value_float`
    (the other stays null). A k-anon-suppressed `max_*` sample has BOTH null —
    the renderer drops such points before charting.
    """

    sampled_at: datetime = Field(description="UTC instant this gauge was sampled")
    value_int: int | None = Field(
        default=None, description="Integer value for COUNT/MAX gauges; null otherwise"
    )
    value_float: float | None = Field(
        default=None, description="Fractional value for AVG gauges; null otherwise"
    )


class GaugeSeries(BaseSchema):
    """One gauge's full windowed series with its folded-in metadata.

    `kind`/`description` are folded into each series so the batched response is
    self-describing — the dashboard renders a card straight from the entry, with
    all gauge data sourced from this single batched endpoint.
    """

    gauge_name: str = Field(description="GaugeName value (e.g. max_urls_per_utub)")
    kind: str = Field(description="GaugeKind value (volume | distribution_max | ...)")
    description: str = Field(description="Human-readable gauge description")
    samples: list[GaugeSampleSchema] = Field(
        description="Window-filtered samples ordered by sampled_at",
    )


class GaugesTimeseriesResponseSchema(BaseSchema):
    """Batched envelope returned by `GET /api/metrics/query/gauges/timeseries`.

    Carries every gauge's windowed series in one response (mirrors
    `GroupedTimeseriesResponseSchema`'s envelope shape). A gauge with no rows in
    the window is absent from `gauges` rather than zero-filled.
    """

    window: str | None = Field(
        default=None,
        description=(
            "Window value as supplied by the client; null when the client "
            "supplied an absolute `start`/`end` range instead."
        ),
    )
    window_start: datetime = Field(description="Inclusive UTC start of the window")
    window_end: datetime = Field(description="Exclusive UTC end of the window")
    gauges: list[GaugeSeries] = Field(
        description="One series per gauge that has samples in the window",
    )


class LatencyPercentileRow(BaseSchema):
    """One row of the `latency` query response — per-(endpoint, method) percentiles.

    `p50`/`p95`/`p99` are exact percentiles computed via Postgres
    `percentile_cont` over the raw `durationMs` samples in the window. They are
    null only for a degenerate empty group (no samples), which the query never
    returns — so in practice each row carries three floats plus a count.
    """

    endpoint: str | None = Field(
        default=None,
        description="Flask endpoint name the samples were attributed to (e.g. utubs.get_utub).",
    )
    method: str | None = Field(
        default=None, description="HTTP method (GET, POST, etc.)."
    )
    p50: float | None = Field(
        default=None, description="Median request duration in ms; null when no samples."
    )
    p95: float | None = Field(
        default=None,
        description="95th-percentile request duration in ms; null when no samples.",
    )
    p99: float | None = Field(
        default=None,
        description="99th-percentile request duration in ms; null when no samples.",
    )
    sample_count: int = Field(
        description="Number of raw samples aggregated into this row's percentiles."
    )


class LatencyPercentilesResponseSchema(BaseSchema):
    """Envelope returned by `GET /api/metrics/query/latency`."""

    window: str | None = Field(
        default=None,
        description=(
            "Window value as supplied by the client; null when the client "
            "supplied an absolute `start`/`end` range instead."
        ),
    )
    window_start: datetime = Field(description="Inclusive UTC start of the window")
    window_end: datetime = Field(description="Exclusive UTC end of the window")
    rows: list[LatencyPercentileRow] = Field(
        description="Per-(endpoint, method) percentile rows ordered by p95 descending.",
    )
    approximate: bool = Field(
        default=False,
        description=(
            "True when the window reaches beyond the raw-sample retention "
            "horizon and the summary percentiles are sample-count-weighted "
            "averages of daily rollups (approximate). False when served exactly "
            "from raw samples. The per-day timeseries stays exact regardless."
        ),
    )


class LatencyTimeseriesBucket(BaseSchema):
    """One bucket of the `latency/timeseries` query response.

    A zero-fill bucket (no samples in that interval) carries
    `p50 = p95 = p99 = None` and `sample_count = 0`; the renderer breaks the
    polyline at null buckets rather than charting a zero-latency point.
    """

    bucket: datetime = Field(
        description="Bucket start (UTC, date_trunc'd to resolution)."
    )
    p50: float | None = Field(
        default=None,
        description="Median duration in ms for this bucket; null when empty.",
    )
    p95: float | None = Field(
        default=None,
        description="95th-percentile duration in ms for this bucket; null when empty.",
    )
    p99: float | None = Field(
        default=None,
        description="99th-percentile duration in ms for this bucket; null when empty.",
    )
    sample_count: int = Field(description="Number of samples in this bucket.")


class LatencyTimeseriesResponseSchema(BaseSchema):
    """Envelope returned by `GET /api/metrics/query/latency/timeseries`."""

    window: str | None = Field(
        default=None,
        description=(
            "Window value as supplied by the client; null when the client "
            "supplied an absolute `start`/`end` range instead."
        ),
    )
    window_start: datetime = Field(description="Inclusive UTC start of the window")
    window_end: datetime = Field(description="Exclusive UTC end of the window")
    endpoint: str | None = Field(
        default=None,
        description="Flask endpoint name the series is filtered to.",
    )
    method: str | None = Field(
        default=None, description="HTTP method the series is filtered to, if any."
    )
    buckets: list[LatencyTimeseriesBucket] = Field(
        description="Zero-filled per-bucket percentile series in chronological order.",
    )
