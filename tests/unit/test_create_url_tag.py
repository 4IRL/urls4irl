from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.tags.services.create_url_tag import apply_tags_core, get_tag_applied_counts
from backend.utils.constants import TAG_CONSTANTS

pytestmark = pytest.mark.unit


def _mock_query_returning(count_rows: list[tuple[int, int]]) -> MagicMock:
    """Builds a mock `db.session.query(...)` chain whose `.all()` yields rows.

    The chain mirrors the production access pattern
    `db.session.query(...).filter(...).group_by(...).all()`, so every
    intermediate call returns the same chainable mock and `.all()` returns the
    provided `(tag_id, count)` rows.

    Examples:
        >>> chain = _mock_query_returning([(7, 3)])
        >>> chain.filter().group_by().all()
        [(7, 3)]
    """
    chain = MagicMock()
    chain.filter.return_value = chain
    chain.group_by.return_value = chain
    chain.all.return_value = count_rows
    return chain


def test_get_tag_applied_counts_empty_tag_ids_returns_empty_dict():
    """An empty `tag_ids` list short-circuits to `{}` without querying."""
    with patch("backend.tags.services.create_url_tag.db") as mock_db:
        result = get_tag_applied_counts(utub_id=1, tag_ids=[])

    assert result == {}
    mock_db.session.query.assert_not_called()


def test_get_tag_applied_counts_single_tag_maps_id_to_count():
    """A single tag id with count 3 returns `{tag_id: 3}`."""
    with patch("backend.tags.services.create_url_tag.db") as mock_db:
        mock_db.session.query.return_value = _mock_query_returning([(7, 3)])
        result = get_tag_applied_counts(utub_id=1, tag_ids=[7])

    assert result == {7: 3}


def test_get_tag_applied_counts_multiple_tags_map_each_id_to_its_count():
    """Multiple tag ids each return their distinct per-id count."""
    with patch("backend.tags.services.create_url_tag.db") as mock_db:
        mock_db.session.query.return_value = _mock_query_returning([(7, 3), (9, 1)])
        result = get_tag_applied_counts(utub_id=1, tag_ids=[7, 9])

    assert result == {7: 3, 9: 1}


def test_apply_tags_core_over_limit_when_url_already_at_max_tags():
    """A URL already holding MAX_URL_TAGS tags reports over_limit for one more.

    The integration route cannot reach this branch for a brand-new URL (the
    schema rejects the oversized list first), so the limit pre-check inside
    `apply_tags_core` is exercised directly here against a URL whose
    `associated_tag_ids` is already saturated.
    """
    utub = MagicMock()
    utub.id = 1
    utub_url = MagicMock()
    utub_url.associated_tag_ids = list(range(TAG_CONSTANTS.MAX_URL_TAGS))

    existing_vocab_query = MagicMock()
    existing_vocab_query.filter.return_value = existing_vocab_query
    existing_vocab_query.all.return_value = []

    with patch(
        "backend.tags.services.create_url_tag.Utub_Tags"
    ) as mock_utub_tags_model:
        mock_utub_tags_model.query.filter.return_value.all.return_value = []
        result = apply_tags_core(["a-brand-new-tag"], utub, utub_url)

    assert result.over_limit
    assert result.to_apply == []
