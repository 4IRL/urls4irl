from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.metrics.suppression import SUPPRESSED_DIM_VALUE
from backend.metrics.utub_buckets import (
    UTUB_AGE_BUCKETS,
    UTUB_SIZE_BUCKETS,
    bucket_utub_age,
    bucket_utub_size,
)

pytestmark = pytest.mark.unit

NOW = datetime(2026, 11, 1, 12, 0, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "url_count, expected_bucket",
    [
        (-1, "0"),
        (0, "0"),
        (1, "1-5"),
        (5, "1-5"),
        (6, "6-20"),
        (20, "6-20"),
        (21, "21-50"),
        (50, "21-50"),
        (51, "51+"),
        (10_000_000, "51+"),
    ],
)
def test_bucket_utub_size_boundary_cases(url_count: int, expected_bucket: str):
    """`bucket_utub_size` maps a live URL count to its bucket at every edge."""
    assert bucket_utub_size(url_count) == expected_bucket


@pytest.mark.parametrize(
    "age, expected_bucket",
    [
        (timedelta(0), "0-6d"),
        (timedelta(days=6, hours=23, minutes=59), "0-6d"),
        (timedelta(days=7), "7-29d"),
        (timedelta(days=29, hours=23, minutes=59), "7-29d"),
        (timedelta(days=30), "30-89d"),
        (timedelta(days=89, hours=23, minutes=59), "30-89d"),
        (timedelta(days=90), "90-364d"),
        (timedelta(days=364, hours=23, minutes=59), "90-364d"),
        (timedelta(days=365), "365d+"),
        (timedelta(days=5000), "365d+"),
        (timedelta(days=-3), "0-6d"),
    ],
)
def test_bucket_utub_age_boundary_cases(age: timedelta, expected_bucket: str):
    """`bucket_utub_age` uses whole elapsed days; clock skew lands in the first bucket."""
    assert bucket_utub_age(NOW - age, now=NOW) == expected_bucket


def test_bucket_utub_age_naive_inputs_taken_as_utc():
    """Naive datetimes (either or both) are treated as UTC and never raise."""
    naive_now = NOW.replace(tzinfo=None)
    naive_created = naive_now - timedelta(days=7)
    assert bucket_utub_age(naive_created, now=naive_now) == "7-29d"
    assert bucket_utub_age(naive_created, now=NOW) == "7-29d"
    assert bucket_utub_age(NOW - timedelta(days=30), now=naive_now) == "30-89d"


def test_classifier_outputs_are_closed_set_members():
    """Every classifier output is a member of its tuple."""
    for count in (-5, 0, 1, 5, 6, 20, 21, 50, 51, 999):
        assert bucket_utub_size(count) in UTUB_SIZE_BUCKETS
    for days in (-10, 0, 6, 7, 29, 30, 89, 90, 364, 365, 4000):
        assert bucket_utub_age(NOW - timedelta(days=days), now=NOW) in UTUB_AGE_BUCKETS


def test_suppressed_value_not_in_bucket_tuples():
    """`SUPPRESSED_DIM_VALUE` is output-only and never a bucket."""
    assert SUPPRESSED_DIM_VALUE not in UTUB_SIZE_BUCKETS
    assert SUPPRESSED_DIM_VALUE not in UTUB_AGE_BUCKETS
