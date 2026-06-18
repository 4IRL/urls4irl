from __future__ import annotations

import itertools
from collections.abc import Sequence
from enum import IntEnum, StrEnum


class SearchErrorCodes(IntEnum):
    INVALID_QUERY_PARAM = 1


class SearchFailureMessages:
    INVALID_QUERY = "Invalid search query."


class MatchedField(StrEnum):
    URL_STRING = "url"
    URL_TITLE = "title"
    TAG = "tag"


DEFAULT_SEARCH_FIELDS: tuple[MatchedField, ...] = (
    MatchedField.URL_STRING,
    MatchedField.URL_TITLE,
    MatchedField.TAG,
)


def field_order_metric_value(fields: Sequence[MatchedField]) -> str:
    """Serialize an ordered field list to its `field_order` metric dim value.

    The value encodes both membership (which fields) and ranking priority
    (left-to-right, first = highest) so the metrics dashboard can show how
    users prioritize title/url/tag.

    Examples::

        field_order_metric_value((URL_STRING, URL_TITLE, TAG))  # "url>title>tag"
        field_order_metric_value((TAG,))                        # "tag"
    """
    return ">".join(field.value for field in fields)


# Closed set of every ordered, non-empty, duplicate-free subset of MatchedField
# (3 single + 6 pair + 6 triple = 15 values). `SearchQuerySchema` guarantees the
# emitted `effective_fields` is always one of these, so this is the exhaustive
# value list for the `field_order` metric dimension. Computed once here as the
# single source of truth for both `EVENT_REGISTRY` and the `_DimCrossUtub
# SearchPerformed` Literal (the metrics audit set-compares the two).
SEARCH_FIELD_ORDER_VALUES: tuple[str, ...] = tuple(
    field_order_metric_value(ordering)
    for length in range(1, len(MatchedField) + 1)
    for ordering in itertools.permutations(MatchedField, length)
)
