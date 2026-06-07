from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.extensions.metrics.buckets import (
    _MISSING_WINDOW_ERROR,
    _RANGE_ORDER_ERROR,
    _WINDOW_PARSE_ERROR_FMT,
    WINDOW_NAMED,
    _named_window_start,
    _shift_calendar_month,
    parse_window,
    previous_window,
    resolve_query_window,
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

    def test_month_shifts_one_calendar_month(self):
        """`month` is calendar-aware: Jan 15 → Dec 15 of prior year."""
        window_start, window_end = parse_window("month", FIXED_NOW)
        assert window_end == FIXED_NOW
        assert window_start == datetime(2025, 12, 15, 14, 30, 0, tzinfo=timezone.utc)

    def test_year_shifts_one_calendar_year(self):
        """`year` is calendar-aware: Jan 15 2026 → Jan 15 2025."""
        window_start, window_end = parse_window("year", FIXED_NOW)
        assert window_end == FIXED_NOW
        assert window_start == datetime(2025, 1, 15, 14, 30, 0, tzinfo=timezone.utc)


class TestParseWindowCalendarEdgeCases:
    """Calendar arithmetic must clamp the day to the target month's last day."""

    def test_month_from_mar_31_clamps_to_feb_28(self):
        """Mar 31 - 1 month → Feb 28 (non-leap year clamp)."""
        now = datetime(2026, 3, 31, 0, 0, 0, tzinfo=timezone.utc)
        window_start, _ = parse_window("month", now)
        assert window_start == datetime(2026, 2, 28, 0, 0, 0, tzinfo=timezone.utc)

    def test_month_from_mar_31_clamps_to_feb_29_in_leap_year(self):
        """Mar 31 2024 - 1 month → Feb 29 2024 (leap-year clamp)."""
        now = datetime(2024, 3, 31, 0, 0, 0, tzinfo=timezone.utc)
        window_start, _ = parse_window("month", now)
        assert window_start == datetime(2024, 2, 29, 0, 0, 0, tzinfo=timezone.utc)

    def test_month_from_may_31_lands_on_apr_30(self):
        """May 31 - 1 month → Apr 30 (30-day month clamp)."""
        now = datetime(2026, 5, 31, 12, 0, 0, tzinfo=timezone.utc)
        window_start, _ = parse_window("month", now)
        assert window_start == datetime(2026, 4, 30, 12, 0, 0, tzinfo=timezone.utc)

    def test_year_from_leap_day_clamps_to_feb_28(self):
        """Feb 29 2024 - 1 year → Feb 28 2023 (non-leap clamp)."""
        now = datetime(2024, 2, 29, 9, 15, 0, tzinfo=timezone.utc)
        window_start, _ = parse_window("year", now)
        assert window_start == datetime(2023, 2, 28, 9, 15, 0, tzinfo=timezone.utc)


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
    """previous_window returns the equal-length interval preceding `(start, end)`."""

    def test_previous_window_day_relative(self):
        """
        GIVEN parse_window("day", FIXED_NOW) → (now - 1d, now)
        WHEN previous_window(start, end) is called
        THEN it returns (now - 2d, now - 1d).
        """
        current_start, current_end = parse_window("day", FIXED_NOW)
        prev_start, prev_end = previous_window(current_start, current_end)
        assert prev_end == current_start
        assert prev_start < current_start
        assert prev_end - prev_start == timedelta(days=1)
        assert prev_start == FIXED_NOW - timedelta(days=2)

    def test_previous_window_24h_shorthand(self):
        current_start, current_end = parse_window("24h", FIXED_NOW)
        prev_start, prev_end = previous_window(current_start, current_end)
        assert prev_end == current_start
        assert prev_end - prev_start == timedelta(hours=24)

    def test_previous_window_week_equal_length(self):
        current_start, current_end = parse_window("week", FIXED_NOW)
        prev_start, prev_end = previous_window(current_start, current_end)
        assert prev_end == current_start
        assert prev_end - prev_start == timedelta(days=7)

    def test_previous_window_absolute_range(self):
        """An admin-supplied 3-day absolute range gets a 3-day prior interval."""
        start = datetime(2026, 4, 1, 0, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 4, 4, 0, 0, 0, tzinfo=timezone.utc)
        prev_start, prev_end = previous_window(start, end)
        assert prev_end == start
        assert prev_end - prev_start == timedelta(days=3)
        assert prev_start == datetime(2026, 3, 29, 0, 0, 0, tzinfo=timezone.utc)


class TestResolveQueryWindowRelative:
    """`window` alone delegates to `parse_window` and ignores `now` defaults."""

    def test_relative_window_delegates_to_parse_window(self):
        start, end = resolve_query_window(
            window="day", start=None, end=None, now=FIXED_NOW
        )
        assert end == FIXED_NOW
        assert start == FIXED_NOW - timedelta(days=1)

    def test_relative_window_propagates_parse_error(self):
        with pytest.raises(ValueError) as exc_info:
            resolve_query_window(window="bogus", start=None, end=None, now=FIXED_NOW)
        assert exc_info.value.args[0].startswith("Invalid window:")


class TestResolveQueryWindowAbsolute:
    """An absolute `(start, end)` tuple bypasses `now` and returns verbatim."""

    def test_absolute_range_returns_supplied_bounds(self):
        absolute_start = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        absolute_end = datetime(2026, 2, 1, 0, 0, 0, tzinfo=timezone.utc)
        start, end = resolve_query_window(
            window=None, start=absolute_start, end=absolute_end, now=FIXED_NOW
        )
        assert start == absolute_start
        assert end == absolute_end

    def test_absolute_range_rejects_start_equal_to_end(self):
        same_instant = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        with pytest.raises(ValueError) as exc_info:
            resolve_query_window(
                window=None, start=same_instant, end=same_instant, now=FIXED_NOW
            )
        assert exc_info.value.args[0] == _RANGE_ORDER_ERROR

    def test_absolute_range_rejects_start_after_end(self):
        absolute_start = datetime(2026, 2, 1, 0, 0, 0, tzinfo=timezone.utc)
        absolute_end = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        with pytest.raises(ValueError) as exc_info:
            resolve_query_window(
                window=None,
                start=absolute_start,
                end=absolute_end,
                now=FIXED_NOW,
            )
        assert exc_info.value.args[0] == _RANGE_ORDER_ERROR


class TestResolveQueryWindowMissing:
    """Neither `window` nor a full `(start, end)` is a defense-in-depth error."""

    def test_no_spec_raises_missing_window_error(self):
        """Pydantic catches this first, but the helper still guards directly."""
        with pytest.raises(ValueError) as exc_info:
            resolve_query_window(window=None, start=None, end=None, now=FIXED_NOW)
        assert exc_info.value.args[0] == _MISSING_WINDOW_ERROR


class TestShiftCalendarMonth:
    """Direct coverage for `_shift_calendar_month` — calendar-aware month arithmetic."""

    def test_normal_mid_month_shift(self):
        """Mid-month dates shift back cleanly without any day clamping."""
        reference = datetime(2026, 4, 15, 10, 0, 0, tzinfo=timezone.utc)
        result = _shift_calendar_month(reference, 1)
        assert result == datetime(2026, 3, 15, 10, 0, 0, tzinfo=timezone.utc)

    def test_end_of_month_clamps_in_non_leap_year(self):
        """Mar 31 - 1 month → Feb 28 (February has no 29th in a non-leap year)."""
        reference = datetime(2026, 3, 31, 0, 0, 0, tzinfo=timezone.utc)
        result = _shift_calendar_month(reference, 1)
        assert result == datetime(2026, 2, 28, 0, 0, 0, tzinfo=timezone.utc)

    def test_end_of_month_resolves_leap_year_feb_29(self):
        """Mar 31 2024 - 1 month → Feb 29 2024 (2024 is a leap year)."""
        reference = datetime(2024, 3, 31, 0, 0, 0, tzinfo=timezone.utc)
        result = _shift_calendar_month(reference, 1)
        assert result == datetime(2024, 2, 29, 0, 0, 0, tzinfo=timezone.utc)

    def test_leap_day_clamped_across_non_leap_target_year(self):
        """Feb 29 2024 - 12 months → Feb 28 2023 (2023 has no Feb 29)."""
        reference = datetime(2024, 2, 29, 9, 15, 0, tzinfo=timezone.utc)
        result = _shift_calendar_month(reference, 12)
        assert result == datetime(2023, 2, 28, 9, 15, 0, tzinfo=timezone.utc)

    def test_cross_year_boundary_backward(self):
        """Jan 31 - 1 month crosses the year boundary back to Dec 31 of prior year."""
        reference = datetime(2026, 1, 31, 0, 0, 0, tzinfo=timezone.utc)
        result = _shift_calendar_month(reference, 1)
        assert result == datetime(2025, 12, 31, 0, 0, 0, tzinfo=timezone.utc)

    def test_cross_year_boundary_multiple_months(self):
        """Mar 15 2026 - 15 months crosses back to Dec 15 2024."""
        reference = datetime(2026, 3, 15, 0, 0, 0, tzinfo=timezone.utc)
        result = _shift_calendar_month(reference, 15)
        assert result == datetime(2024, 12, 15, 0, 0, 0, tzinfo=timezone.utc)


class TestNamedWindowStart:
    """Direct coverage for `_named_window_start` — recognized names and edge cases."""

    STABLE_NOW = datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc)

    @pytest.mark.parametrize(
        "name,expected_start",
        [
            (
                "day",
                datetime(2026, 3, 14, 12, 0, 0, tzinfo=timezone.utc),
            ),
            (
                "week",
                datetime(2026, 3, 8, 12, 0, 0, tzinfo=timezone.utc),
            ),
            (
                "month",
                datetime(2026, 2, 15, 12, 0, 0, tzinfo=timezone.utc),
            ),
            (
                "year",
                datetime(2025, 3, 15, 12, 0, 0, tzinfo=timezone.utc),
            ),
        ],
    )
    def test_recognized_names_return_correct_start(
        self, name: str, expected_start: datetime
    ):
        """Each recognized window name returns the expected start relative to STABLE_NOW."""
        result = _named_window_start(name, self.STABLE_NOW)
        assert result == expected_start

    def test_month_end_of_month_clamping(self):
        """'month' at Mar 31 clamps the result to Feb 28 (non-leap year)."""
        now = datetime(2026, 3, 31, 0, 0, 0, tzinfo=timezone.utc)
        result = _named_window_start("month", now)
        assert result == datetime(2026, 2, 28, 0, 0, 0, tzinfo=timezone.utc)

    def test_year_leap_day_clamping(self):
        """'year' at Feb 29 2024 clamps back to Feb 28 2023 (non-leap target year)."""
        now = datetime(2024, 2, 29, 0, 0, 0, tzinfo=timezone.utc)
        result = _named_window_start("year", now)
        assert result == datetime(2023, 2, 28, 0, 0, 0, tzinfo=timezone.utc)

    def test_unrecognized_name_returns_none(self):
        """Any name not in WINDOW_NAMED returns None."""
        result = _named_window_start("quarter", self.STABLE_NOW)
        assert result is None

    def test_empty_string_returns_none(self):
        """An empty string is not a recognized window name."""
        result = _named_window_start("", self.STABLE_NOW)
        assert result is None
