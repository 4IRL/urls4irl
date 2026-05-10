from __future__ import annotations

from datetime import datetime, timezone


def compute_bucket_start_epoch(now_epoch_seconds: int, bucket_seconds: int) -> int:
    """Truncate an epoch second value down to the start of its bucket.

    Shared by `MetricsWriter` (writes Redis counter keys) and the Phase 2
    flush worker (parses bucket from key) so both agree on bucket boundaries
    even if `METRICS_BUCKET_SECONDS` changes.
    """
    return (now_epoch_seconds // bucket_seconds) * bucket_seconds


def epoch_to_aware_datetime(epoch_seconds: int) -> datetime:
    """Convert an epoch second value to a timezone-aware UTC datetime.

    Uses `datetime.fromtimestamp(..., tz=timezone.utc)` since
    `datetime.utcfromtimestamp` is deprecated as of Python 3.12.
    """
    return datetime.fromtimestamp(epoch_seconds, tz=timezone.utc)
