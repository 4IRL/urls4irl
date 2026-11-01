"""Closed-set size and age buckets for UTub metrics dimensions.

Pure leaf module (standard library only) so the registry, dimension models and
services can import it without cycles. `"suppressed"` is output-only and is
deliberately not a member of either tuple.

`UTUB_SIZE_BUCKETS` means "live (non-trashed) URLs in the UTub"; it is not the
same set as `BULK_TAG_URL_BUCKETS` (URLs affected by an action).
"""

from __future__ import annotations

from datetime import datetime, timezone

UTUB_SIZE_BUCKETS: tuple[str, ...] = ("0", "1-5", "6-20", "21-50", "51+")
UTUB_AGE_BUCKETS: tuple[str, ...] = ("0-6d", "7-29d", "30-89d", "90-364d", "365d+")


def bucket_utub_size(url_count: int) -> str:
    """Return the size bucket for a count of live URLs (`<= 0` is `"0"`)."""
    if url_count <= 0:
        return "0"
    if url_count <= 5:
        return "1-5"
    if url_count <= 20:
        return "6-20"
    if url_count <= 50:
        return "21-50"
    return "51+"


def _as_utc(value: datetime) -> datetime:
    """Treat a naive datetime as UTC; convert aware ones to UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def bucket_utub_age(created_at: datetime, *, now: datetime) -> str:
    """Return the age bucket from whole elapsed days between `created_at` and `now`.

    Naive inputs are taken as UTC. Negative ages (clock skew) fall in `"0-6d"`.
    """
    days = (_as_utc(now) - _as_utc(created_at)).days
    if days < 7:
        return "0-6d"
    if days < 30:
        return "7-29d"
    if days < 90:
        return "30-89d"
    if days < 365:
        return "90-364d"
    return "365d+"
