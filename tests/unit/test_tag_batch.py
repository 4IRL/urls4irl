from __future__ import annotations

import pytest

from backend.metrics.tag_batch import bucket_tags_batch_size

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "applied_count, expected_bucket",
    [
        (1, "1"),
        (2, "2-5"),
        (5, "2-5"),
        (6, "6-10"),
        (10, "6-10"),
        (11, "11-15"),
        (15, "11-15"),
        (16, "16-20"),
        (20, "16-20"),
    ],
)
def test_bucket_tags_batch_size_boundary_cases(
    applied_count: int, expected_bucket: str
):
    """`bucket_tags_batch_size` maps applied_count to its closed-set label across every boundary.

    Covers the lower and upper edge of each bucket in `TAGS_BATCH_SIZE_BUCKETS`
    spanning the valid 1..MAX_URL_TAGS (20) range.
    """
    assert bucket_tags_batch_size(applied_count) == expected_bucket
