from __future__ import annotations

from pydantic import Field

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
