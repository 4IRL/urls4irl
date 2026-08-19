from __future__ import annotations

import pytest

from backend.metrics.tag_batch import (
    bucket_bulk_tag_url_count,
    bucket_tags_batch_size,
    bucket_url_tag_count,
)

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


@pytest.mark.parametrize(
    "tag_count, expected_bucket",
    [
        (0, "0"),
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
def test_bucket_url_tag_count_boundary_cases(tag_count: int, expected_bucket: str):
    """`bucket_url_tag_count` maps an at-creation tag count to its closed-set label.

    Unlike `bucket_tags_batch_size`, this bucketer carries an explicit "0" bucket
    because a URL is commonly created with no tags. Covers the dedicated 0 case
    plus a representative point in each upper bucket spanning the 0..MAX_URL_TAGS
    (20) range.
    """
    assert bucket_url_tag_count(tag_count) == expected_bucket


@pytest.mark.parametrize(
    "url_count, expected_bucket",
    [
        (0, "0"),
        (1, "1"),
        (2, "2-5"),
        (5, "2-5"),
        (6, "6-10"),
        (10, "6-10"),
        (11, "11-25"),
        (25, "11-25"),
        (26, "26-50"),
        (50, "26-50"),
        (51, "51+"),
        (200, "51+"),
    ],
)
def test_bucket_bulk_tag_url_count_boundary_cases(url_count: int, expected_bucket: str):
    """`bucket_bulk_tag_url_count` maps a URL count to its closed-set label across every boundary.

    Backs both `url_count_bucket` and `skipped_count_bucket` on the
    `TAGS_APPLIED_MULTI_URL` DOMAIN event. Covers the dedicated "0" bucket
    (a fully-successful batch skips nothing) plus both edges of every upper
    bucket in `BULK_TAG_URL_BUCKETS`, up through the unbounded "51+" tail that
    keeps a large Select-All apply visible without unbounded cardinality.
    """
    assert bucket_bulk_tag_url_count(url_count) == expected_bucket
