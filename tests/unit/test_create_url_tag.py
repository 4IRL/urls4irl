from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.tags.services.create_url_tag import get_tag_applied_counts

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
