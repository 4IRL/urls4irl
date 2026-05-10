from __future__ import annotations

from datetime import timezone

import pytest

from backend.extensions.metrics.buckets import (
    compute_bucket_start_epoch,
    epoch_to_aware_datetime,
)

pytestmark = pytest.mark.unit


def test_bucket_start_truncates_to_bucket_seconds():
    """
    GIVEN an epoch in the middle of a bucket
    WHEN compute_bucket_start_epoch is called with bucket_seconds=3600
    THEN the result is truncated to the top of the hour.
    """
    assert compute_bucket_start_epoch(1735689660, 3600) == 1735689600


def test_bucket_start_handles_exact_boundary():
    """
    GIVEN an epoch exactly on a bucket boundary
    WHEN compute_bucket_start_epoch is called
    THEN the result equals the input (no rounding artifact).
    """
    assert compute_bucket_start_epoch(1735689600, 3600) == 1735689600


def test_bucket_start_minute_resolution():
    """
    GIVEN an epoch at a minute boundary
    WHEN compute_bucket_start_epoch is called with bucket_seconds=60
    THEN the same epoch is returned.
    """
    assert compute_bucket_start_epoch(1735689660, 60) == 1735689660


def test_epoch_to_aware_datetime_returns_utc():
    """
    GIVEN any epoch
    WHEN epoch_to_aware_datetime is called
    THEN the result is a timezone-aware datetime in UTC.
    """
    aware_datetime = epoch_to_aware_datetime(1735689600)
    assert aware_datetime.tzinfo == timezone.utc
