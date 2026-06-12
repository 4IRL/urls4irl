from __future__ import annotations

import pytest

from backend.metrics.routes import _bucket_batch_size

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "event_count, expected_bucket",
    [
        (0, "1"),
        (1, "1"),
        (2, "2-5"),
        (5, "2-5"),
        (6, "6-25"),
        (25, "6-25"),
        (26, "26-100"),
        (100, "26-100"),
        (101, "26-100"),
    ],
)
def test_bucket_batch_size_boundary_cases(event_count: int, expected_bucket: str):
    """`_bucket_batch_size` maps event_count to its closed-set label across every boundary.

    The schema's max batch size is 100, but 101 is included to confirm the
    defensive `> 25` clamp keeps oversize values in "26-100" rather than
    raising or returning an out-of-set label.
    """
    assert _bucket_batch_size(event_count) == expected_bucket
