from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from urllib.parse import urlsplit

from sqlalchemy import func, select

from backend import db
from backend.invite_links.constants import INVITE_LINK_PREVIEW_MAX_URLS
from backend.invite_links.page_response import InvitePreview, InvitePreviewUrl
from backend.models.urls import Urls
from backend.models.utub_tags import Utub_Tags
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls

_WEB_SCHEMES = frozenset({"http", "https"})


def _is_web_url(url: str) -> bool:
    return urlsplit(url).scheme.lower() in _WEB_SCHEMES


def build_invite_preview(*, utub_id: int, available_until: datetime) -> InvitePreview:
    """Build the logged-out preview for a UTub: newest live URLs, capped, allowlisted.

    Selects columns only (title, URL string, tag strings), so no ids, adders, taggers
    or short links ever reach the page view.

    Args:
        utub_id (int): The UTub being previewed.
        available_until (datetime): The effective preview end (UTC).
    """
    available_until = available_until.astimezone(timezone.utc)
    live_url_filter = (Utub_Urls.utub_id == utub_id, Utub_Urls.deleted_at.is_(None))

    rows = db.session.execute(
        select(Utub_Urls.id, Utub_Urls.url_title, Urls.url_string)
        .join(Urls, Urls.id == Utub_Urls.url_id)
        .where(*live_url_filter)
        .order_by(Utub_Urls.added_at.desc(), Utub_Urls.id.desc())
        .limit(INVITE_LINK_PREVIEW_MAX_URLS)
    ).all()
    total_count: int = (
        db.session.scalar(select(func.count(Utub_Urls.id)).where(*live_url_filter)) or 0
    )

    tags_by_row: dict[int, list[str]] = defaultdict(list)
    if rows:
        tag_rows = db.session.execute(
            select(Utub_Url_Tags.utub_url_id, Utub_Tags.tag_string)
            .join(Utub_Tags, Utub_Tags.id == Utub_Url_Tags.utub_tag_id)
            .where(
                Utub_Url_Tags.utub_id == utub_id,
                Utub_Url_Tags.utub_url_id.in_([row.id for row in rows]),
            )
        ).all()
        for utub_url_id, tag_string in tag_rows:
            tags_by_row[utub_url_id].append(tag_string)

    urls = tuple(
        InvitePreviewUrl(
            title=row.url_title or "",
            url=row.url_string,
            is_web_url=_is_web_url(row.url_string),
            tags=tuple(sorted(tags_by_row[row.id], key=str.casefold)),
        )
        for row in rows
    )
    return InvitePreview(
        urls=urls,
        total_count=total_count,
        hidden_count=max(total_count - INVITE_LINK_PREVIEW_MAX_URLS, 0),
        available_until_iso=available_until.isoformat(),
        available_until_label=(
            f"{available_until:%b} {available_until.day}, {available_until.year}"
        ),
    )
