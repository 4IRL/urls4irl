from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

WINDOW_NAMED: tuple[str, ...] = ("day", "week", "month", "year")
WINDOW_NAMED_DELTAS: dict[str, timedelta] = {
    "day": timedelta(days=1),
    "week": timedelta(days=7),
    "month": timedelta(days=30),
    "year": timedelta(days=365),
}
_WINDOW_SHORTHAND_RE: re.Pattern = re.compile(r"^(\d+)([hd])$")
_WINDOW_PARSE_ERROR_FMT: str = (
    "Invalid window: {value!r}. Expected one of {names} or NhNd shorthand "
    "(e.g. 24h, 7d)."
)


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


def parse_window(value: str, now: datetime) -> tuple[datetime, datetime]:
    """Convert a window spec to a `(start, end)` UTC-aware datetime tuple.

    Accepts named windows (`day` | `week` | `month` | `year`) and `Nh` / `Nd`
    shorthand. `month` and `year` are intentionally fixed-length (30 days and
    365 days) — calendar-month and leap-year math are deferred until a concrete
    need.

    Raises:
        ValueError: when `value` is not a recognized window string. The message
            uses `_WINDOW_PARSE_ERROR_FMT` so callers (including tests) can
            assert against the exact text.
    """
    named_delta = WINDOW_NAMED_DELTAS.get(value)
    if named_delta is not None:
        return (now - named_delta, now)

    shorthand_match = _WINDOW_SHORTHAND_RE.match(value)
    if shorthand_match is not None:
        magnitude = int(shorthand_match.group(1))
        unit = shorthand_match.group(2)
        if magnitude <= 0:
            raise ValueError(
                _WINDOW_PARSE_ERROR_FMT.format(value=value, names=WINDOW_NAMED)
            )
        delta = timedelta(hours=magnitude) if unit == "h" else timedelta(days=magnitude)
        return (now - delta, now)

    raise ValueError(_WINDOW_PARSE_ERROR_FMT.format(value=value, names=WINDOW_NAMED))


def previous_window(window_value: str, now: datetime) -> tuple[datetime, datetime]:
    """Return the interval of equal length immediately preceding the current one.

    Used by the summary endpoint to compute period-over-period deltas. For
    `window_value="day"` and `now=t`, returns `(t - 2*day, t - day)`.
    """
    current_start, current_end = parse_window(window_value, now)
    interval_length = current_end - current_start
    return (current_start - interval_length, current_start)
