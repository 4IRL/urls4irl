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
    dimensions: dict[str, str | int | bool] | None = Field(
        default=None,
        description=(
            "Optional per-event dimension dict; shape enforced server-side via "
            "the matching `_Dim<EventName>` Pydantic model"
        ),
    )


class MetricsIngestRequest(BaseModel):
    """Top-level batch payload for `POST /api/metrics`."""

    model_config = ConfigDict(extra="forbid")

    events: list[MetricsIngestEvent] = Field(
        min_length=1,
        max_length=100,
        description="Batch of UI-category metrics events to ingest (1-100 entries)",
    )
    batch_id: str | None = Field(
        default=None,
        description=(
            "Client-generated batch identifier; used server-side for SET NX EX "
            "idempotency on retries"
        ),
    )
    csrf_token: str | None = Field(
        default=None,
        description=(
            "Optional CSRF token in the JSON body for navigator.sendBeacon "
            "callers that cannot set headers"
        ),
    )
