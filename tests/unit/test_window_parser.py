from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.extensions.metrics.buckets import (
    _WINDOW_PARSE_ERROR_FMT,
    WINDOW_NAMED,
    parse_window,
    previous_window,
)

pytestmark = pytest.mark.unit


FIXED_NOW = datetime(2026, 1, 15, 14, 30, 0, tzinfo=timezone.utc)


class TestParseWindowNamed:
    """Named windows return `(now - delta, now)` for the documented deltas."""

    def test_day_returns_one_day_delta(self):
        """
        GIVEN now=2026-01-15 14:30 UTC
        WHEN parse_window("day", now) is called
        THEN the result is (2026-01-14 14:30 UTC, 2026-01-15 14:30 UTC).
        """
        window_start, window_end = parse_window("day", FIXED_NOW)
        assert window_end == FIXED_NOW
        assert window_start == FIXED_NOW - timedelta(days=1)

    def test_week_returns_seven_day_delta(self):
        window_start, window_end = parse_window("week", FIXED_NOW)
        assert window_end == FIXED_NOW
        assert window_end - window_start == timedelta(days=7)

    def test_month_returns_thirty_day_delta(self):
        """Calendar-month math is intentionally deferred; 30 days is the contract."""
        window_start, window_end = parse_window("month", FIXED_NOW)
        assert window_end == FIXED_NOW
        assert window_end - window_start == timedelta(days=30)

    def test_year_returns_three_sixty_five_day_delta(self):
        """Leap-year math is intentionally deferred; 365 days is the contract."""
        window_start, window_end = parse_window("year", FIXED_NOW)
        assert window_end == FIXED_NOW
        assert window_end - window_start == timedelta(days=365)


class TestParseWindowShorthand:
    """`Nh` and `Nd` shorthand round-trip exactly to N hours / N days."""

    def test_twenty_four_hour_shorthand(self):
        window_start, window_end = parse_window("24h", FIXED_NOW)
        assert window_end == FIXED_NOW
        assert window_end - window_start == timedelta(hours=24)

    def test_seven_day_shorthand(self):
        window_start, window_end = parse_window("7d", FIXED_NOW)
        assert window_end == FIXED_NOW
        assert window_end - window_start == timedelta(days=7)

    def test_one_hour_shorthand(self):
        window_start, window_end = parse_window("1h", FIXED_NOW)
        assert window_end - window_start == timedelta(hours=1)

    def test_large_day_shorthand(self):
        window_start, window_end = parse_window("365d", FIXED_NOW)
        assert window_end - window_start == timedelta(days=365)


class TestParseWindowInvalidInputs:
    """Invalid inputs raise ValueError with a verbatim-formatted message."""

    @pytest.mark.parametrize(
        "bad_value",
        [
            "bogus",
            "",
            "1m",  # ambiguous between minute and month
            "-1h",  # negative
            "0h",  # zero is not a valid window
            "0d",
            "h",
            "d",
            "12",  # no unit
            "1.5h",  # non-integer
        ],
    )
    def test_invalid_value_raises_value_error(self, bad_value: str):
        with pytest.raises(ValueError) as exc_info:
            parse_window(bad_value, FIXED_NOW)
        expected_message = _WINDOW_PARSE_ERROR_FMT.format(
            value=bad_value, names=WINDOW_NAMED
        )
        assert exc_info.value.args[0] == expected_message


class TestPreviousWindow:
    """previous_window returns the immediately-preceding interval of equal length."""

    def test_previous_window_named_day(self):
        """
        GIVEN now=FIXED_NOW
        WHEN previous_window("day", now) is called
        THEN it returns (now - 2 days, now - 1 day) — the interval before parse_window's.
        """
        prev_start, prev_end = previous_window("day", FIXED_NOW)
        current_start, _ = parse_window("day", FIXED_NOW)
        assert prev_end == current_start
        assert prev_start < current_start
        assert prev_end - prev_start == timedelta(days=1)
        assert prev_start == FIXED_NOW - timedelta(days=2)

    def test_previous_window_shorthand_24h(self):
        prev_start, prev_end = previous_window("24h", FIXED_NOW)
        current_start, _ = parse_window("24h", FIXED_NOW)
        assert prev_end == current_start
        assert prev_start < current_start
        assert prev_end - prev_start == timedelta(hours=24)

    def test_previous_window_week_equal_length(self):
        prev_start, prev_end = previous_window("week", FIXED_NOW)
        current_start, _ = parse_window("week", FIXED_NOW)
        assert prev_end == current_start
        assert prev_end - prev_start == timedelta(days=7)

    def test_previous_window_invalid_raises(self):
        with pytest.raises(ValueError):
            previous_window("bogus", FIXED_NOW)
