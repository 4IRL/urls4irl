from __future__ import annotations

from datetime import datetime

from pydantic import AwareDatetime, Field

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
