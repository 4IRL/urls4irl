from __future__ import annotations

from sqlalchemy import or_
from sqlalchemy.orm import joinedload, subqueryload

from backend import db
from backend.extensions.metrics.writer import record_event
from backend.metrics.events import EventName
from backend.models.urls import Urls
from backend.models.utub_members import Utub_Members
from backend.models.utub_tags import Utub_Tags
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.schemas.search import (
    SearchResultsSchema,
    SearchUtubGroupSchema,
)
from backend.search.constants import MatchedField

_FIELD_WEIGHTS: dict[MatchedField, int] = {
    MatchedField.URL_TITLE: 3,
    MatchedField.URL_STRING: 2,
    MatchedField.TAG: 1,
}


def _escape_ilike(term: str) -> str:
    """Escape ILIKE wildcard characters so user input matches literally.

    Backslash is escaped first so the subsequent `%`/`_` escapes are not
    double-escaped.

    Example:
        _escape_ilike("50% off")  -> "50\\% off"
        _escape_ilike("foo_bar")  -> "foo\\_bar"
    """
    term = term.replace("\\", "\\\\")
    term = term.replace("%", "\\%")
    term = term.replace("_", "\\_")
    return term


def _compute_matched_fields(
    utub_url: Utub_Urls, query_lower: str
) -> list[MatchedField]:
    """Determine which fields a lowercased query matched on an already-loaded row.

    Re-tests the query against eager-loaded data in Python (no extra SQL). The
    returned order is stable: title, then url, then tag.

    Example:
        title contains "py", url does not, a tag contains "py"
        -> [MatchedField.URL_TITLE, MatchedField.TAG]
    """
    matched: list[MatchedField] = []
    if query_lower in (utub_url.url_title or "").lower():
        matched.append(MatchedField.URL_TITLE)
    if query_lower in utub_url.standalone_url.url_string.lower():
        matched.append(MatchedField.URL_STRING)
    if any(
        query_lower in tag.utub_tag_item.tag_string.lower() for tag in utub_url.url_tags
    ):
        matched.append(MatchedField.TAG)
    return matched


def search_across_user_utubs(*, query: str, user_id: int) -> SearchResultsSchema:
    """Search every UTub the user is a member of, grouped and ranked best-first.

    Matches the case-insensitive query against URL string, per-UTub URL title,
    and tag text. Results are grouped by source UTub; within a group hits are
    ranked by best matched-field score (title > url > tag) then url_title ASC;
    groups are ranked by max hit score, then match count DESC, then utub_name ASC.
    """
    escaped = _escape_ilike(query)
    query_lower = query.lower()
    member_utub_ids = db.session.query(Utub_Members.utub_id).filter(
        Utub_Members.user_id == user_id
    )
    tag_matched_utub_url_ids = (
        db.session.query(Utub_Url_Tags.utub_url_id)
        .join(Utub_Tags, Utub_Url_Tags.utub_tag_id == Utub_Tags.id)
        .filter(Utub_Tags.tag_string.ilike(f"%{escaped}%", escape="\\"))
    )
    matching_urls: list[Utub_Urls] = (
        Utub_Urls.query.join(Urls, Utub_Urls.url_id == Urls.id)
        .options(
            joinedload(Utub_Urls.utub),
            joinedload(Utub_Urls.standalone_url),
            subqueryload(Utub_Urls.url_tags).joinedload(Utub_Url_Tags.utub_tag_item),
        )
        .filter(Utub_Urls.utub_id.in_(member_utub_ids))
        .filter(
            or_(
                Urls.url_string.ilike(f"%{escaped}%", escape="\\"),
                Utub_Urls.url_title.ilike(f"%{escaped}%", escape="\\"),
                Utub_Urls.id.in_(tag_matched_utub_url_ids),
            )
        )
        .all()
    )

    hits_with_fields: list[tuple[Utub_Urls, list[MatchedField]]] = [
        (utub_url, _compute_matched_fields(utub_url, query_lower))
        for utub_url in matching_urls
    ]

    grouped: dict[int, list[tuple[Utub_Urls, list[MatchedField]]]] = {}
    for utub_url, matched_fields in hits_with_fields:
        grouped.setdefault(utub_url.utub_id, []).append((utub_url, matched_fields))

    def _hit_sort_key(
        hit: tuple[Utub_Urls, list[MatchedField]],
    ) -> tuple[int, str]:
        utub_url, matched_fields = hit
        score = max((_FIELD_WEIGHTS[field] for field in matched_fields), default=0)
        return (-score, (utub_url.url_title or "").lower())

    for hit_list in grouped.values():
        hit_list.sort(key=_hit_sort_key)

    def _group_sort_key(
        group_item: tuple[int, list[tuple[Utub_Urls, list[MatchedField]]]],
    ) -> tuple[int, int, str]:
        _group_utub_id, hit_list = group_item
        max_score = max(
            (
                _FIELD_WEIGHTS[field]
                for _utub_url, matched_fields in hit_list
                for field in matched_fields
            ),
            default=0,
        )
        utub_name = hit_list[0][0].utub.name
        return (-max_score, -len(hit_list), utub_name.lower())

    sorted_groups = sorted(grouped.items(), key=_group_sort_key)
    results = [
        SearchUtubGroupSchema.from_utub_urls(hit_list[0][0].utub, hit_list)
        for _group_utub_id, hit_list in sorted_groups
    ]
    record_event(
        EventName.CROSS_UTUB_SEARCH_PERFORMED,
        dimensions={"has_results": "true" if results else "false"},
    )
    return SearchResultsSchema(results=results)
