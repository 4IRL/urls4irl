from flask import Flask
import pytest

from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.search.constants import MatchedField
from backend.search.services.cross_utub_search import (
    _group_sort_key,
    _hit_sort_key,
)

pytestmark = pytest.mark.unit

_TITLE_SCORE = 3
_URL_SCORE = 2
_TAG_SCORE = 1


def _make_hit(
    *,
    url_title: str | None,
    matched_fields: list[MatchedField],
    utub_name: str = "UTub",
) -> tuple[Utub_Urls, list[MatchedField]]:
    """Build a transient (Utub_Urls, matched_fields) hit for ranking tests.

    Only the attributes the sort keys read are populated: `url_title` on the
    association and `name` on its parent UTub. No session/DB is involved.
    """
    utub = Utubs(name=utub_name, utub_creator=1, utub_description="")
    utub_url = Utub_Urls()
    utub_url.url_title = url_title
    utub_url.utub = utub
    return (utub_url, matched_fields)


def test_hit_sort_key_scores_title_above_url_above_tag(app: Flask) -> None:
    """
    GIVEN single-field hits matching on title, url, and tag
    WHEN _hit_sort_key is computed for each
    THEN the negated score orders title (3) before url (2) before tag (1).
    """
    with app.app_context():
        title_hit = _make_hit(url_title="a", matched_fields=[MatchedField.URL_TITLE])
        url_hit = _make_hit(url_title="a", matched_fields=[MatchedField.URL_STRING])
        tag_hit = _make_hit(url_title="a", matched_fields=[MatchedField.TAG])

        assert _hit_sort_key(title_hit)[0] == -_TITLE_SCORE
        assert _hit_sort_key(url_hit)[0] == -_URL_SCORE
        assert _hit_sort_key(tag_hit)[0] == -_TAG_SCORE

        ranked = sorted([tag_hit, title_hit, url_hit], key=_hit_sort_key)
        assert ranked == [title_hit, url_hit, tag_hit]


def test_hit_sort_key_uses_best_field_when_multiple_match(app: Flask) -> None:
    """
    GIVEN a hit matching on both tag and title
    WHEN _hit_sort_key is computed
    THEN the score reflects the best (highest-weight) field, not the sum.
    """
    with app.app_context():
        multi_hit = _make_hit(
            url_title="a", matched_fields=[MatchedField.TAG, MatchedField.URL_TITLE]
        )
        assert _hit_sort_key(multi_hit)[0] == -_TITLE_SCORE


def test_hit_sort_key_breaks_ties_by_title_ascending_case_insensitive(
    app: Flask,
) -> None:
    """
    GIVEN two equal-score title hits with titles "Banana" and "apple"
    WHEN sorted by _hit_sort_key
    THEN they order case-insensitively ascending: "apple" before "Banana".
    """
    with app.app_context():
        banana = _make_hit(url_title="Banana", matched_fields=[MatchedField.URL_TITLE])
        apple = _make_hit(url_title="apple", matched_fields=[MatchedField.URL_TITLE])

        ranked = sorted([banana, apple], key=_hit_sort_key)
        assert ranked == [apple, banana]


def test_hit_sort_key_handles_empty_match_and_none_title(app: Flask) -> None:
    """
    GIVEN a hit with no matched fields and a None url_title
    WHEN _hit_sort_key is computed
    THEN score defaults to 0 and the None title collapses to an empty string.
    """
    with app.app_context():
        empty_hit = _make_hit(url_title=None, matched_fields=[])
        assert _hit_sort_key(empty_hit) == (0, "")


def test_group_sort_key_orders_by_best_score_then_count_then_name(app: Flask) -> None:
    """
    GIVEN one group with a title hit and another whose best is a tag hit
    WHEN _group_sort_key is computed
    THEN the title group's negated best-score outranks the tag group's.
    """
    with app.app_context():
        title_group = (
            1,
            [_make_hit(url_title="a", matched_fields=[MatchedField.URL_TITLE])],
        )
        tag_group = (2, [_make_hit(url_title="a", matched_fields=[MatchedField.TAG])])

        assert _group_sort_key(title_group)[0] == -_TITLE_SCORE
        assert _group_sort_key(tag_group)[0] == -_TAG_SCORE
        assert sorted([tag_group, title_group], key=_group_sort_key) == [
            title_group,
            tag_group,
        ]


def test_group_sort_key_breaks_score_ties_by_match_count_descending(app: Flask) -> None:
    """
    GIVEN two groups with equal best-score but different hit counts
    WHEN sorted by _group_sort_key
    THEN the group with more matching URLs ranks first.
    """
    with app.app_context():
        two_hits = (
            1,
            [
                _make_hit(url_title="a", matched_fields=[MatchedField.URL_TITLE]),
                _make_hit(url_title="b", matched_fields=[MatchedField.URL_TITLE]),
            ],
        )
        one_hit = (
            2,
            [_make_hit(url_title="a", matched_fields=[MatchedField.URL_TITLE])],
        )

        assert sorted([one_hit, two_hits], key=_group_sort_key) == [two_hits, one_hit]


def test_group_sort_key_breaks_score_and_count_ties_by_name_ascending(
    app: Flask,
) -> None:
    """
    GIVEN two groups with equal best-score and equal count, named "Bravo" and "alpha"
    WHEN sorted by _group_sort_key
    THEN they order case-insensitively ascending by utub name: "alpha" before "Bravo".
    """
    with app.app_context():
        bravo = (
            1,
            [
                _make_hit(
                    url_title="a",
                    matched_fields=[MatchedField.URL_TITLE],
                    utub_name="Bravo",
                )
            ],
        )
        alpha = (
            2,
            [
                _make_hit(
                    url_title="a",
                    matched_fields=[MatchedField.URL_TITLE],
                    utub_name="alpha",
                )
            ],
        )

        assert sorted([bravo, alpha], key=_group_sort_key) == [alpha, bravo]


def test_hit_sort_key_honors_reordered_weights(app: Flask) -> None:
    """
    GIVEN an explicit weights map prioritizing tag over title over url
    WHEN _hit_sort_key is computed with that weights argument
    THEN scores follow the supplied map and sorting flips accordingly.
    """
    with app.app_context():
        reordered_weights = {
            MatchedField.TAG: 3,
            MatchedField.URL_TITLE: 2,
            MatchedField.URL_STRING: 1,
        }
        title_hit = _make_hit(url_title="a", matched_fields=[MatchedField.URL_TITLE])
        url_hit = _make_hit(url_title="a", matched_fields=[MatchedField.URL_STRING])
        tag_hit = _make_hit(url_title="a", matched_fields=[MatchedField.TAG])

        assert _hit_sort_key(tag_hit, weights=reordered_weights)[0] == -3
        assert _hit_sort_key(title_hit, weights=reordered_weights)[0] == -2
        assert _hit_sort_key(url_hit, weights=reordered_weights)[0] == -1

        ranked = sorted(
            [url_hit, title_hit, tag_hit],
            key=lambda hit: _hit_sort_key(hit, weights=reordered_weights),
        )
        assert ranked == [tag_hit, title_hit, url_hit]


def test_group_sort_key_honors_reordered_weights(app: Flask) -> None:
    """
    GIVEN an explicit weights map prioritizing tag over title
    WHEN _group_sort_key is computed with that weights argument
    THEN the tag group's negated best-score outranks the title group's.
    """
    with app.app_context():
        reordered_weights = {
            MatchedField.TAG: 3,
            MatchedField.URL_TITLE: 2,
            MatchedField.URL_STRING: 1,
        }
        title_group = (
            1,
            [_make_hit(url_title="a", matched_fields=[MatchedField.URL_TITLE])],
        )
        tag_group = (2, [_make_hit(url_title="a", matched_fields=[MatchedField.TAG])])

        assert _group_sort_key(tag_group, weights=reordered_weights)[0] == -3
        assert _group_sort_key(title_group, weights=reordered_weights)[0] == -2

        ranked = sorted(
            [title_group, tag_group],
            key=lambda group: _group_sort_key(group, weights=reordered_weights),
        )
        assert ranked == [tag_group, title_group]
