from __future__ import annotations

import json


def canonicalize_dimensions(dimensions: dict) -> str:
    """Produce a stable, key-order-insensitive Redis-key suffix for a
    dimensions dict.

    Used by Phase 2's Redis writer and the Phase 2 flush worker so two
    events with the same logical dimensions produce the same Redis key
    regardless of key insertion order.

    Canonicalization is Redis-internal only. Postgres JSONB equality
    handles key-order natively, so the canonical form never reaches the
    DB.
    """
    return json.dumps(
        dimensions,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
