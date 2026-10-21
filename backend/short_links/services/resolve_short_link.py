import re
from dataclasses import dataclass
from urllib.parse import urlparse

from backend import db
from backend.models.short_links import Short_Links
from backend.models.urls import Urls
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.short_links.constants import (
    SHORT_LINK_ALLOWED_SCHEMES,
    SHORT_LINK_CODE_PATTERN,
)
from backend.utils.datetime_utils import utc_now

_CODE_REGEX = re.compile(SHORT_LINK_CODE_PATTERN)


@dataclass(frozen=True)
class ShortLinkDestination:
    """The only facts the public confirmation page may show about a live link."""

    destination_url: str
    destination_host: str


def find_live_destination(code: str) -> ShortLinkDestination | None:
    """Return where a short link goes, or None when it must show the dead-link page.

    A link is live only when ``code`` is well formed (checked before any DB access), a
    row exists, it has not expired, the UTub URL and its UTub are not trashed, the UTub
    is not admin-locked, and the stored destination is an ``http``/``https`` URL with a
    host. Read-only: nothing is written.

    Args:
        code (str): The raw ``<code>`` path segment.

    Returns:
        ShortLinkDestination | None: The destination to confirm, or None for every
        dead case (the caller renders one identical 404 for all of them).
    """
    if _CODE_REGEX.match(code) is None:
        return None

    url_string: str | None = (
        db.session.query(Urls.url_string)
        .select_from(Short_Links)
        .join(Utub_Urls, Utub_Urls.id == Short_Links.utub_url_id)
        .join(Utubs, Utubs.id == Utub_Urls.utub_id)
        .join(Urls, Urls.id == Utub_Urls.url_id)
        .filter(
            Short_Links.code == code,
            Short_Links.expires_at > utc_now(),
            Utub_Urls.deleted_at.is_(None),
            Utubs.deleted_at.is_(None),
            Utubs.is_locked.is_(False),
        )
        .scalar()
    )
    if url_string is None:
        return None

    # A backslash, whitespace or control character is parsed differently by browsers
    # than by urlparse, so the displayed host could differ from where Continue goes.
    if any(
        char == "\\" or char.isspace() or not char.isprintable() for char in url_string
    ):
        return None

    try:
        parsed = urlparse(url_string)
        host: str | None = parsed.hostname
    except ValueError:
        return None
    if parsed.scheme.lower() not in SHORT_LINK_ALLOWED_SCHEMES or not host:
        return None
    return ShortLinkDestination(destination_url=url_string, destination_host=host)
