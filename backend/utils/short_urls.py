from __future__ import annotations

import requests
from redis.client import Redis

from backend.utils.strings.url_validation_strs import CUSTOM_SHORT_URLS, SHORT_URLS

_SHORT_URL_DOMAINS_LIST = (
    "https://raw.githubusercontent.com/PeterDaveHello/url-shorteners/master/list"
)
_HEADER_LINE_COUNT: int = 11


def sync_short_url_domains_to_redis(*, redis_client: Redis) -> int | None:
    """Fetch the short-URL domain list and add all domains to the Redis set.

    Fetches the canonical short-URL domain list from GitHub, strips the
    11-line header block, decodes each remaining line, appends the
    CUSTOM_SHORT_URLS, and bulk-adds every domain string to the SHORT_URLS
    Redis set key via SADD.

    Returns the count of newly added domains (0 when all domains already
    exist in the set) or None on fetch or parse failure.

    Examples:
        >>> # First call — domains not yet in Redis
        >>> sync_short_url_domains_to_redis(redis_client=rc)
        1234  # number of new domains added
        >>> # Subsequent call — all domains already present
        >>> sync_short_url_domains_to_redis(redis_client=rc)
        0
        >>> # Network failure
        >>> sync_short_url_domains_to_redis(redis_client=rc)
        None
    """
    try:
        response = requests.get(_SHORT_URL_DOMAINS_LIST, timeout=10)
        raw_content = response.content
        if not raw_content:
            return None

        lines = raw_content.splitlines()
        if not lines or len(lines) < _HEADER_LINE_COUNT:
            return None

        domain_lines = lines[_HEADER_LINE_COUNT:]
        domain_strings = [str(line.decode()) for line in domain_lines] + [
            custom_domain for custom_domain in CUSTOM_SHORT_URLS
        ]
        added = redis_client.sadd(SHORT_URLS, *domain_strings)
        return int(added)

    except requests.RequestException:
        return None
    except Exception:
        return None
