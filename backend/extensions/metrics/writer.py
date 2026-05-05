from __future__ import annotations

from backend.metrics.events import EventName


def record_event(
    event: EventName,
    *,
    endpoint: str | None = None,
    method: str | None = None,
    status_code: int | None = None,
    dimensions: dict | None = None,
) -> None:
    """Phase 1 stub. No-op until Phase 2 ships the Redis writer.

    Keeping the signature stable lets Phase 3 (domain hooks) land
    record_event(...) calls before Phase 2's Redis client is wired up.
    The `EventName` parameter type makes typos a type-check error.
    """
    _ = (event, endpoint, method, status_code, dimensions)
    return None
