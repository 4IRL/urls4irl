from datetime import timedelta
from enum import IntEnum

from backend.models.short_links import SHORT_LINK_CODE_LENGTH

SHORT_LINK_TTL: timedelta = timedelta(days=7)
# Mint retries this many times on a ``code`` unique violation, then raises.
SHORT_LINK_MINT_MAX_ATTEMPTS: int = 5
# Per-user (per-IP for anonymous callers) budget for ``POST .../short-link``.
SHORT_LINK_MINT_RATE_LIMIT: str = "30 per minute"

# Per-IP budget for the public ``GET /s/<code>`` page (hits and misses both count).
SHORT_LINK_RESOLVE_RATE_LIMIT: str = "60 per minute"
# A code is checked against this before any DB access; ``\Z`` rejects a trailing newline.
SHORT_LINK_CODE_PATTERN: str = rf"^[A-Za-z0-9]{{{SHORT_LINK_CODE_LENGTH}}}\Z"
# Only these destination schemes are ever offered on the confirmation page.
SHORT_LINK_ALLOWED_SCHEMES: frozenset[str] = frozenset({"http", "https"})

# Names of the two ``ShortLinks`` unique constraints (see ``Short_Links.__table_args__``).
UNIQUE_SHORT_LINK_PER_UTUB_URL: str = "unique_short_link_per_utub_url"
UNIQUE_SHORT_LINK_CODE: str = "unique_short_link_code"


class ShortLinkErrorCodes(IntEnum):
    SHORT_LINK_NOT_FOUND = 1
