from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from dateutil.relativedelta import relativedelta

from backend.users.services.stats_service import _humanize_account_age

pytestmark = pytest.mark.unit

# A fixed "now" the humanizer measures against (patched in per-case below), so
# the parametrized offsets below produce deterministic phrases regardless of
# when the suite runs.
_FIXED_NOW = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "created_offset, expected_phrase",
    [
        (relativedelta(years=1), "1 year"),
        (relativedelta(years=2), "2 years"),
        (relativedelta(months=2), "2 months"),
        (relativedelta(months=1), "1 month"),
        (relativedelta(days=1), "1 day"),
        (relativedelta(days=3), "3 days"),
        (relativedelta(), "Joined today"),
        # One unit below a year rollover: still months, proving unit selection
        # rides relativedelta's own calendar rollover, not manual day-count math.
        (relativedelta(months=11, days=29), "11 months"),
    ],
)
def test_humanize_account_age(created_offset, expected_phrase):
    """
    GIVEN an account created a fixed relativedelta before a fixed "now"
    WHEN _humanize_account_age renders the age
    THEN it returns the largest-unit phrase with correct pluralization
    """
    created_at = _FIXED_NOW - created_offset
    with patch("backend.users.services.stats_service.utc_now", return_value=_FIXED_NOW):
        assert _humanize_account_age(created_at) == expected_phrase
