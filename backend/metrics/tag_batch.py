"""Batch-tag-apply metrics helpers.

Houses the closed-set `batch_size_bucket` dimension values and the bucketing
function for the `TAGS_APPLIED_BATCH` DOMAIN event. Kept in a dedicated module
so `backend/metrics/events.py` stays a pure enum/constants file, and so the
event registry, dimension model, and tag service can all import the single
`TAGS_BATCH_SIZE_BUCKETS` constant — guaranteeing the audit set-compare between
the registry tuple and the Pydantic `Literal[...]` can never drift.
"""

from __future__ import annotations

TAGS_BATCH_SIZE_BUCKETS: tuple[str, ...] = ("1", "2-5", "6-10", "11-15", "16-20")
URL_TAG_COUNT_BUCKETS: tuple[str, ...] = ("0", "1", "2-5", "6-10", "11-15", "16-20")
BULK_TAG_URL_BUCKETS: tuple[str, ...] = (
    "0",
    "1",
    "2-5",
    "6-10",
    "11-25",
    "26-50",
    "51+",
)


def bucket_tags_batch_size(applied_count: int) -> str:
    """Map a count of newly-applied tags to its closed-set size bucket.

    The buckets mirror `TAGS_BATCH_SIZE_BUCKETS` and span the valid range
    1..MAX_URL_TAGS (20). A batch always applies at least one tag, so callers
    never pass 0 (the do-not-emit guard handles the empty case upstream). The
    top of the range is split (11-15 / 16-20) so near-cap usage is visible —
    e.g. whether the MAX_URL_TAGS limit is approached in practice.

    Examples:
        bucket_tags_batch_size(1)  -> "1"
        bucket_tags_batch_size(4)  -> "2-5"
        bucket_tags_batch_size(9)  -> "6-10"
        bucket_tags_batch_size(13) -> "11-15"
        bucket_tags_batch_size(20) -> "16-20"
    """
    if applied_count <= 1:
        return "1"
    if applied_count <= 5:
        return "2-5"
    if applied_count <= 10:
        return "6-10"
    if applied_count <= 15:
        return "11-15"
    return "16-20"


def bucket_url_tag_count(count: int) -> str:
    """Map a URL's at-creation tag count to its closed-set size bucket.

    Mirrors `URL_TAG_COUNT_BUCKETS`. Unlike `bucket_tags_batch_size`, this
    bucketer carries an explicit "0" bucket because a URL is commonly created
    with no tags — the create flow always emits a bucket, so the empty case is a
    first-class value rather than a do-not-emit guard. Above 0, the buckets match
    `bucket_tags_batch_size` and span the valid 1..MAX_URL_TAGS (20) range, with
    the top split (11-15 / 16-20) so near-cap usage stays visible.

    Examples:
        bucket_url_tag_count(0)  -> "0"
        bucket_url_tag_count(1)  -> "1"
        bucket_url_tag_count(3)  -> "2-5"
        bucket_url_tag_count(7)  -> "6-10"
        bucket_url_tag_count(13) -> "11-15"
        bucket_url_tag_count(20) -> "16-20"
    """
    if count == 0:
        return "0"
    if count <= 1:
        return "1"
    if count <= 5:
        return "2-5"
    if count <= 10:
        return "6-10"
    if count <= 15:
        return "11-15"
    return "16-20"


def bucket_bulk_tag_url_count(count: int) -> str:
    """Map a count of URLs (applied-to or skipped) to its closed-set size bucket.

    Mirrors `BULK_TAG_URL_BUCKETS`. Backs both the `url_count_bucket` (URLs that
    gained ≥1 tag) and `skipped_count_bucket` (URLs skipped over-limit) dimensions
    of the `TAGS_APPLIED_MULTI_URL` DOMAIN event, so a single bucketer/tuple keeps
    the registry and the Pydantic `Literal[...]` from drifting. Carries an explicit
    "0" bucket because `skipped_count_bucket` is commonly 0 (a fully-successful
    batch), and the buckets widen toward the top ("11-25" / "26-50" / "51+") so a
    large Select-All multi-URL apply stays visible without unbounded cardinality.

    Examples:
        bucket_bulk_tag_url_count(0)   -> "0"
        bucket_bulk_tag_url_count(1)   -> "1"
        bucket_bulk_tag_url_count(4)   -> "2-5"
        bucket_bulk_tag_url_count(9)   -> "6-10"
        bucket_bulk_tag_url_count(20)  -> "11-25"
        bucket_bulk_tag_url_count(40)  -> "26-50"
        bucket_bulk_tag_url_count(200) -> "51+"
    """
    if count == 0:
        return "0"
    if count <= 1:
        return "1"
    if count <= 5:
        return "2-5"
    if count <= 10:
        return "6-10"
    if count <= 25:
        return "11-25"
    if count <= 50:
        return "26-50"
    return "51+"
