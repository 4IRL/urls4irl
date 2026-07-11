from __future__ import annotations

import requests
from redis.client import Redis

from backend.utils.strings.url_validation_strs import CUSTOM_SHORT_URLS, SHORT_URLS

_SHORT_URL_DOMAINS_LIST = (
    "https://raw.githubusercontent.com/PeterDaveHello/url-shorteners/master/list"
)
_HEADER_LINE_COUNT: int = 11

FETCH_FAILED_DETAIL: str = "Unable to perform request to get short URL domains."
EMPTY_CONTENT_DETAIL: str = "Unable to parse content of response."
TOO_FEW_LINES_DETAIL: str = (
    "No content found with splitlines when parsing short URL domains."
)
UNKNOWN_FAILURE_DETAIL: str = "Unknown exception when generating short URL domain list."


class ShortUrlSyncError(Exception):
    """Raised when the short-URL domain list cannot be fetched, parsed, or
    written to Redis. The message carries the specific failure detail so both
    the CLI (print) and the admin action (audit metadata) surface it."""


def sync_short_url_domains_to_redis(*, redis_client: Redis) -> int:
    """Fetch the short-URL domain list and add all domains to the Redis set.

    Fetches the canonical short-URL domain list from GitHub, strips the
    11-line header block, decodes each remaining line, appends the
    CUSTOM_SHORT_URLS, and bulk-adds every domain string to the SHORT_URLS
    Redis set key via SADD.

    Returns the count of newly added domains (0 when all domains already
    exist in the set). Raises ShortUrlSyncError with a specific detail
    message on fetch, parse, or Redis failure.

    Examples:
        >>> # First call — domains not yet in Redis
        >>> sync_short_url_domains_to_redis(redis_client=rc)
        1234  # number of new domains added
        >>> # Subsequent call — all domains already present
        >>> sync_short_url_domains_to_redis(redis_client=rc)
        0
        >>> # Network failure
        >>> sync_short_url_domains_to_redis(redis_client=rc)
        Traceback (most recent call last):
        ShortUrlSyncError: Unable to perform request to get short URL domains.
    """
    try:
        response = requests.get(_SHORT_URL_DOMAINS_LIST, timeout=10)
    except requests.RequestException as request_error:
        raise ShortUrlSyncError(FETCH_FAILED_DETAIL) from request_error

    raw_content = response.content
    if not raw_content:
        raise ShortUrlSyncError(EMPTY_CONTENT_DETAIL)

    lines = raw_content.splitlines()
    if not lines or len(lines) < _HEADER_LINE_COUNT:
        raise ShortUrlSyncError(TOO_FEW_LINES_DETAIL)

    try:
        domain_lines = lines[_HEADER_LINE_COUNT:]
        domain_strings = [str(line.decode()) for line in domain_lines] + [
            custom_domain for custom_domain in CUSTOM_SHORT_URLS
        ]
        added = redis_client.sadd(SHORT_URLS, *domain_strings)
        return int(added)
    except Exception as sync_error:
        raise ShortUrlSyncError(
            f"{UNKNOWN_FAILURE_DETAIL} {sync_error}"
        ) from sync_error
