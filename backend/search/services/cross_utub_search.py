from __future__ import annotations

import functools
from collections.abc import Sequence

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
from backend.search.constants import (
    DEFAULT_SEARCH_FIELDS,
    MatchedField,
    field_order_metric_value,
)


def weights_from_fields(
    fields: Sequence[MatchedField],
) -> dict[MatchedField, int]:
    """Map an ordered field list to ranking weights (first field = highest).

    Absolute magnitudes are irrelevant; only the relative order matters. The
    first field gets the largest weight, decreasing by one per position.

    Example:
        weights_from_fields((URL_STRING, URL_TITLE, TAG))
        -> {URL_STRING: 3, URL_TITLE: 2, TAG: 1}
    """
    return {field: len(fields) - index for index, field in enumerate(fields)}


_FIELD_WEIGHTS: dict[MatchedField, int] = weights_from_fields(DEFAULT_SEARCH_FIELDS)


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
    utub_url: Utub_Urls,
    query_lower: str,
    selected_fields: set[MatchedField],
) -> list[MatchedField]:
    """Determine which selected fields a lowercased query matched on a loaded row.

    Re-tests the query against eager-loaded data in Python (no extra SQL), but
    only for fields in `selected_fields` — a field excluded from the search must
    never appear in the result. The returned order is stable: title, then url,
    then tag, among the selected fields.

    Example:
        title contains "py", url does not, a tag contains "py",
        selected_fields={URL_TITLE, TAG}
        -> [MatchedField.URL_TITLE, MatchedField.TAG]
    """
    matched: list[MatchedField] = []
    if (
        MatchedField.URL_TITLE in selected_fields
        and query_lower in (utub_url.url_title or "").lower()
    ):
        matched.append(MatchedField.URL_TITLE)
    if (
        MatchedField.URL_STRING in selected_fields
        and query_lower in utub_url.standalone_url.url_string.lower()
    ):
        matched.append(MatchedField.URL_STRING)
    if MatchedField.TAG in selected_fields and any(
        query_lower in tag.utub_tag_item.tag_string.lower() for tag in utub_url.url_tags
    ):
        matched.append(MatchedField.TAG)
    return matched


def hit_sort_key(
    hit: tuple[Utub_Urls, list[MatchedField]],
    *,
    weights: dict[MatchedField, int] = _FIELD_WEIGHTS,
) -> tuple[int, str]:
    """Rank a single hit best-first within its UTub group.

    Orders by best matched-field score descending (per `weights`, default
    url=3 > title=2 > tag=1), then by url_title ascending (case-insensitive) as
    a stable tiebreak.

    Example:
        a url match (score 3) sorts before a tag-only match (score 1);
        two equal-score matches sort by url_title A->Z.
    """
    utub_url, matched_fields = hit
    score = max((weights[field] for field in matched_fields), default=0)
    return (-score, (utub_url.url_title or "").lower())


def group_sort_key(
    group_item: tuple[int, list[tuple[Utub_Urls, list[MatchedField]]]],
    *,
    weights: dict[MatchedField, int] = _FIELD_WEIGHTS,
) -> tuple[int, int, str]:
    """Rank a UTub group best-first across all groups.

    Orders by the group's best hit score descending (per `weights`), then by
    match count descending, then by utub_name ascending (case-insensitive) as a
    final tiebreak.

    Example:
        a group with a title match outranks a group whose best is a tag match;
        on equal best-score, the group with more matching URLs ranks first;
        on equal score and count, "Alpha" outranks "Bravo".
    """
    _group_utub_id, hit_list = group_item
    max_score = max(
        (
            weights[field]
            for _utub_url, matched_fields in hit_list
            for field in matched_fields
        ),
        default=0,
    )
    utub_name = hit_list[0][0].utub.name
    return (-max_score, -len(hit_list), utub_name.lower())


def search_across_user_utubs(
    *, query: str, user_id: int, fields: list[MatchedField] | None = None
) -> SearchResultsSchema:
    """Search every UTub the user is a member of, grouped and ranked best-first.

    Matches the case-insensitive query against the selected `fields` only —
    membership restricts which of URL string / URL title / tag text are searched,
    and order sets ranking priority (first = highest). Omitting `fields` searches
    all three in the default priority (url > title > tag). Results are grouped by
    source UTub; within a group hits are ranked by best matched-field score then
    url_title ASC; groups are ranked by max hit score, then match count DESC, then
    utub_name ASC.
    """
    effective_fields = list(fields) if fields else list(DEFAULT_SEARCH_FIELDS)
    selected_fields = set(effective_fields)
    weights = weights_from_fields(effective_fields)

    escaped = _escape_ilike(query)
    query_lower = query.lower()
    member_utub_ids = db.session.query(Utub_Members.utub_id).filter(
        Utub_Members.user_id == user_id
    )

    predicates = []
    if MatchedField.URL_STRING in selected_fields:
        predicates.append(Urls.url_string.ilike(f"%{escaped}%", escape="\\"))
    if MatchedField.URL_TITLE in selected_fields:
        predicates.append(Utub_Urls.url_title.ilike(f"%{escaped}%", escape="\\"))
    if MatchedField.TAG in selected_fields:
        tag_matched_utub_url_ids = (
            db.session.query(Utub_Url_Tags.utub_url_id)
            .join(Utub_Tags, Utub_Url_Tags.utub_tag_id == Utub_Tags.id)
            .filter(Utub_Tags.tag_string.ilike(f"%{escaped}%", escape="\\"))
        )
        predicates.append(Utub_Urls.id.in_(tag_matched_utub_url_ids))

    matching_urls: list[Utub_Urls] = (
        Utub_Urls.query.join(Urls, Utub_Urls.url_id == Urls.id)
        .options(
            joinedload(Utub_Urls.utub),
            joinedload(Utub_Urls.standalone_url),
            subqueryload(Utub_Urls.url_tags).joinedload(Utub_Url_Tags.utub_tag_item),
        )
        .filter(Utub_Urls.utub_id.in_(member_utub_ids))
        .filter(or_(*predicates))
        .all()
    )

    hits_with_fields: list[tuple[Utub_Urls, list[MatchedField]]] = [
        (utub_url, _compute_matched_fields(utub_url, query_lower, selected_fields))
        for utub_url in matching_urls
    ]

    grouped: dict[int, list[tuple[Utub_Urls, list[MatchedField]]]] = {}
    for utub_url, matched_fields in hits_with_fields:
        grouped.setdefault(utub_url.utub_id, []).append((utub_url, matched_fields))

    for hit_list in grouped.values():
        hit_list.sort(key=functools.partial(hit_sort_key, weights=weights))

    sorted_groups = sorted(
        grouped.items(), key=functools.partial(group_sort_key, weights=weights)
    )
    results = [
        SearchUtubGroupSchema.from_utub_urls(hit_list[0][0].utub, hit_list)
        for _group_utub_id, hit_list in sorted_groups
    ]
    record_event(
        EventName.CROSS_UTUB_SEARCH_PERFORMED,
        dimensions={
            "has_results": "true" if results else "false",
            "field_order": field_order_metric_value(effective_fields),
        },
    )
    return SearchResultsSchema(results=results)
