from __future__ import annotations

import calendar
import re
from datetime import datetime, timedelta, timezone

WINDOW_NAMED: tuple[str, ...] = ("day", "week", "month", "year")
_WINDOW_NAMED_DELTAS: dict[str, timedelta] = {
    "day": timedelta(days=1),
    "week": timedelta(days=7),
}
_WINDOW_SHORTHAND_RE: re.Pattern = re.compile(r"^(\d+)([hd])$")
_WINDOW_PARSE_ERROR_FMT: str = (
    "Invalid window: {value!r}. Expected one of {names} or NhNd shorthand "
    "(e.g. 24h, 7d)."
)
_RANGE_ORDER_ERROR: str = "`start` must be strictly before `end`."
_MISSING_WINDOW_ERROR: str = "Provide `window` or both `start` and `end`."


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


def _shift_calendar_month(reference: datetime, months: int) -> datetime:
    """Shift `reference` back by `months` calendar months.

    Clamps the day to the last valid day of the target month so callers like
    `parse_window("month", 2026-03-31)` resolve to `2026-02-28` (or `2026-02-29`
    in a leap year) rather than raising `ValueError`. Used by the `month` and
    `year` (months=12) named-window branches.

    Examples:
        Common case — shift back one month on a normal day:
        >>> _shift_calendar_month(datetime(2026, 4, 15, tzinfo=timezone.utc), 1)
        datetime.datetime(2026, 3, 15, 0, 0, tzinfo=datetime.timezone.utc)

        End-of-month clamping — Mar 31 minus 1 month clamps to Feb 28 (non-leap):
        >>> _shift_calendar_month(datetime(2026, 3, 31, tzinfo=timezone.utc), 1)
        datetime.datetime(2026, 2, 28, 0, 0, tzinfo=datetime.timezone.utc)

        Leap-year clamping — Feb 29 2024 minus 12 months clamps to Feb 28 2023:
        >>> _shift_calendar_month(datetime(2024, 2, 29, tzinfo=timezone.utc), 12)
        datetime.datetime(2023, 2, 28, 0, 0, tzinfo=datetime.timezone.utc)

        Leap year — Mar 31 2024 minus 1 month resolves to Feb 29 (leap year):
        >>> _shift_calendar_month(datetime(2024, 3, 31, tzinfo=timezone.utc), 1)
        datetime.datetime(2024, 2, 29, 0, 0, tzinfo=datetime.timezone.utc)
    """
    zero_indexed_month = reference.month - 1 - months
    target_year = reference.year + zero_indexed_month // 12
    target_month = zero_indexed_month % 12 + 1
    last_day_of_target_month = calendar.monthrange(target_year, target_month)[1]
    return reference.replace(
        year=target_year,
        month=target_month,
        day=min(reference.day, last_day_of_target_month),
    )


def _named_window_start(name: str, now: datetime) -> datetime | None:
    """Return the start datetime for a named window, or None if unrecognized.

    `month` and `year` use calendar-aware arithmetic via `_shift_calendar_month`
    (Feb 29 + 1 year → Feb 28; Mar 31 - 1 month → Feb 28/29). `day` and `week`
    stay on fixed `timedelta` deltas because their semantics are unambiguous.

    Examples:
        "day" returns exactly 24 hours before `now`:
        >>> _named_window_start("day", datetime(2026, 6, 5, 12, 0, tzinfo=timezone.utc))
        datetime.datetime(2026, 6, 4, 12, 0, tzinfo=datetime.timezone.utc)

        "week" returns exactly 7 days before `now`:
        >>> _named_window_start("week", datetime(2026, 6, 5, 12, 0, tzinfo=timezone.utc))
        datetime.datetime(2026, 5, 29, 12, 0, tzinfo=datetime.timezone.utc)

        "month" uses calendar arithmetic, clamping if needed (Mar 31 → Feb 28):
        >>> _named_window_start("month", datetime(2026, 3, 31, tzinfo=timezone.utc))
        datetime.datetime(2026, 2, 28, 0, 0, tzinfo=datetime.timezone.utc)

        "year" shifts back 12 calendar months (Feb 29 2024 → Feb 28 2023):
        >>> _named_window_start("year", datetime(2024, 2, 29, tzinfo=timezone.utc))
        datetime.datetime(2023, 2, 28, 0, 0, tzinfo=datetime.timezone.utc)

        Unrecognized name returns None:
        >>> _named_window_start("quarter", datetime(2026, 6, 5, tzinfo=timezone.utc)) is None
        True
    """
    fixed_delta = _WINDOW_NAMED_DELTAS.get(name)
    if fixed_delta is not None:
        return now - fixed_delta
    if name == "month":
        return _shift_calendar_month(now, 1)
    if name == "year":
        return _shift_calendar_month(now, 12)
    return None


def parse_window(value: str, now: datetime) -> tuple[datetime, datetime]:
    """Convert a window spec to a `(start, end)` UTC-aware datetime tuple.

    Accepts named windows (`day` | `week` | `month` | `year`) and `Nh` / `Nd`
    shorthand. `month` and `year` use calendar-aware arithmetic — the day is
    clamped to the last valid day of the target month so Feb 29 - 1 year and
    Mar 31 - 1 month resolve correctly without raising.

    Raises:
        ValueError: when `value` is not a recognized window string. The message
            uses `_WINDOW_PARSE_ERROR_FMT` so callers (including tests) can
            assert against the exact text.

    Examples:
        Named window "day" — returns (now - 24h, now):
        >>> now = datetime(2026, 6, 5, 12, 0, tzinfo=timezone.utc)
        >>> parse_window("day", now)
        (datetime.datetime(2026, 6, 4, 12, 0, tzinfo=datetime.timezone.utc), datetime.datetime(2026, 6, 5, 12, 0, tzinfo=datetime.timezone.utc))

        Shorthand "24h" — identical result to "day":
        >>> parse_window("24h", now)
        (datetime.datetime(2026, 6, 4, 12, 0, tzinfo=datetime.timezone.utc), datetime.datetime(2026, 6, 5, 12, 0, tzinfo=datetime.timezone.utc))

        Shorthand "7d" — returns (now - 7 days, now):
        >>> parse_window("7d", now)
        (datetime.datetime(2026, 5, 29, 12, 0, tzinfo=datetime.timezone.utc), datetime.datetime(2026, 6, 5, 12, 0, tzinfo=datetime.timezone.utc))

        Named window "month" on Mar 31 — clamps to Feb 28 (non-leap year):
        >>> parse_window("month", datetime(2026, 3, 31, tzinfo=timezone.utc))
        (datetime.datetime(2026, 2, 28, 0, 0, tzinfo=datetime.timezone.utc), datetime.datetime(2026, 3, 31, 0, 0, tzinfo=datetime.timezone.utc))

        Named window "year" on leap day — clamps Feb 29 2024 back to Feb 28 2023:
        >>> parse_window("year", datetime(2024, 2, 29, tzinfo=timezone.utc))
        (datetime.datetime(2023, 2, 28, 0, 0, tzinfo=datetime.timezone.utc), datetime.datetime(2024, 2, 29, 0, 0, tzinfo=datetime.timezone.utc))

        Invalid spec raises ValueError:
        >>> parse_window("quarter", now)
        Traceback (most recent call last):
            ...
        ValueError: Invalid window: 'quarter'. Expected one of ...
    """
    named_start = _named_window_start(value, now)
    if named_start is not None:
        return (named_start, now)

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


def resolve_query_window(
    *,
    window: str | None,
    start: datetime | None,
    end: datetime | None,
    now: datetime,
) -> tuple[datetime, datetime]:
    """Resolve a query-schema window specification to a `(start, end)` tuple.

    Accepts either a relative `window` string (delegates to `parse_window`)
    or an absolute `(start, end)` range. Pydantic-level XOR validation in
    each query schema guarantees exactly one shape arrives here, so the
    `ValueError` branches act as a defense-in-depth invariant check.

    Raises:
        ValueError: when neither a window nor a full range is provided, or
            when `start >= end`. Window parsing errors propagate verbatim
            from `parse_window`.
    """
    if start is not None and end is not None:
        if start >= end:
            raise ValueError(_RANGE_ORDER_ERROR)
        return (start, end)
    if window is not None:
        return parse_window(window, now)
    raise ValueError(_MISSING_WINDOW_ERROR)


def previous_window(
    window_start: datetime, window_end: datetime
) -> tuple[datetime, datetime]:
    """Return the interval of equal length immediately preceding `(start, end)`.

    Used by the summary endpoint to compute period-over-period deltas. For a
    24-hour window ending at `t`, returns `(t - 48h, t - 24h)`. Works for any
    interval — relative `parse_window` output or an absolute admin range —
    because it operates on the resolved tuple, not the original spec.
    """
    interval_length = window_end - window_start
    return (window_start - interval_length, window_start)
