from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest

from backend.models.utub_urls import Utub_Urls
from backend.urls.services import trashed_url_tags
from backend.urls.services.trashed_url_tags import (
    build_tag_name_snapshot,
    build_tag_name_snapshot_from_ids,
    count_lost_trashed_tags,
    list_lost_trashed_tag_names,
)
from backend.utils.strings.model_strs import MODELS

pytestmark = pytest.mark.unit


def _trashed_row(
    *,
    trashed_tag_ids: list[int] | None,
    trashed_tag_names: dict[str, str] | None,
    surviving_tag_ids: list[int],
) -> Utub_Urls:
    # A plain stand-in: the helpers only read these attributes, and a real or spec'd
    # Utub_Urls would need an application context.
    return cast(
        Utub_Urls,
        SimpleNamespace(
            trashed_tag_ids=trashed_tag_ids,
            trashed_tag_names=trashed_tag_names,
            associated_tag_ids=surviving_tag_ids,
        ),
    )


def test_list_lost_trashed_tag_names_returns_names_of_lost_ids_only():
    """
    GIVEN a snapshot of tags 1-3 with names, of which only tag 2 survives
    WHEN the lost tag names are listed
    THEN only the names of tags 1 and 3 are returned, and the count agrees
    """
    row = _trashed_row(
        trashed_tag_ids=[1, 2, 3],
        trashed_tag_names={"1": "Tool", "2": "Kept", "3": "Art"},
        surviving_tag_ids=[2],
    )

    assert list_lost_trashed_tag_names(row) == ["Art", "Tool"]
    assert count_lost_trashed_tags(row) == 2


def test_list_lost_trashed_tag_names_sorts_case_insensitively_and_deterministically():
    """
    GIVEN lost tags whose names differ in case and one pair that differs only by case
    WHEN the lost tag names are listed
    THEN they sort alphabetically ignoring case, with exact-string order breaking ties
    """
    row = _trashed_row(
        trashed_tag_ids=[1, 2, 3, 4],
        trashed_tag_names={"1": "banana", "2": "Apple", "3": "cherry", "4": "apple"},
        surviving_tag_ids=[],
    )

    assert list_lost_trashed_tag_names(row) == ["Apple", "apple", "banana", "cherry"]


def test_list_lost_trashed_tag_names_is_empty_when_nothing_was_lost():
    """
    GIVEN every snapshotted tag still associated
    WHEN the lost tag names are listed
    THEN the list is empty
    """
    row = _trashed_row(
        trashed_tag_ids=[1, 2],
        trashed_tag_names={"1": "Tool", "2": "Art"},
        surviving_tag_ids=[1, 2],
    )

    assert list_lost_trashed_tag_names(row) == []
    assert count_lost_trashed_tags(row) == 0


def test_legacy_row_without_saved_names_counts_lost_tags_but_names_none():
    """
    GIVEN a row trashed before names were saved (trashed_tag_names is NULL)
    WHEN lost tags are counted and listed
    THEN the count is still correct and the name list is empty
    """
    row = _trashed_row(
        trashed_tag_ids=[1, 2],
        trashed_tag_names=None,
        surviving_tag_ids=[1],
    )

    assert count_lost_trashed_tags(row) == 1
    assert list_lost_trashed_tag_names(row) == []


def test_lost_id_missing_from_saved_names_is_omitted_from_names_not_count():
    """
    GIVEN a lost tag id that has no entry in the saved names
    WHEN lost tags are counted and listed
    THEN the id is counted but contributes no name
    """
    row = _trashed_row(
        trashed_tag_ids=[1, 2],
        trashed_tag_names={"1": "Tool"},
        surviving_tag_ids=[],
    )

    assert count_lost_trashed_tags(row) == 2
    assert list_lost_trashed_tag_names(row) == ["Tool"]


def test_row_without_snapshot_has_no_lost_tags():
    """
    GIVEN a row with no snapshot at all
    WHEN lost tags are counted and listed
    THEN there are none
    """
    row = _trashed_row(
        trashed_tag_ids=None, trashed_tag_names=None, surviving_tag_ids=[5]
    )

    assert count_lost_trashed_tags(row) == 0
    assert list_lost_trashed_tag_names(row) == []


def test_build_tag_name_snapshot_maps_string_ids_to_tag_strings():
    """
    GIVEN a live row with two associated tags
    WHEN its tag name snapshot is built
    THEN it maps each tag id (as a string, for JSONB) to its tag string
    """
    row = cast(
        Utub_Urls,
        SimpleNamespace(
            associated_tags=[
                {MODELS.UTUB_TAG_ID: 7, MODELS.TAG_STRING: "Tool"},
                {MODELS.UTUB_TAG_ID: 9, MODELS.TAG_STRING: "Art"},
            ]
        ),
    )

    assert build_tag_name_snapshot(row) == {"7": "Tool", "9": "Art"}


class _FakeTagQuery:
    def __init__(self, tags: list[SimpleNamespace]):
        self._tags = tags
        self.filter_calls = 0

    def filter(self, *_criteria: object) -> _FakeTagQuery:
        self.filter_calls += 1
        return self

    def all(self) -> list[SimpleNamespace]:
        return self._tags


def _patch_utub_tags(
    monkeypatch: pytest.MonkeyPatch, existing_tags: list[SimpleNamespace]
) -> _FakeTagQuery:
    # Stand-in for the Utub_Tags model: a real query needs an application context.
    fake_query = _FakeTagQuery(existing_tags)
    fake_model = SimpleNamespace(
        query=fake_query, id=SimpleNamespace(in_=lambda ids: ids)
    )
    monkeypatch.setattr(trashed_url_tags, "Utub_Tags", fake_model)
    return fake_query


def test_build_tag_name_snapshot_from_ids_is_empty_without_querying_for_no_ids(
    monkeypatch: pytest.MonkeyPatch,
):
    """
    GIVEN an empty iterable of tag ids
    WHEN the snapshot is built from ids
    THEN it is an empty dict and the database is never queried
    """
    fake_query = _patch_utub_tags(monkeypatch, [])

    assert build_tag_name_snapshot_from_ids([]) == {}
    assert fake_query.filter_calls == 0


def test_build_tag_name_snapshot_from_ids_omits_nonexistent_tag_ids(
    monkeypatch: pytest.MonkeyPatch,
):
    """
    GIVEN tag ids 7 and 99 where only tag 7 still exists
    WHEN the snapshot is built from ids
    THEN only tag 7 is mapped, keyed by its string id
    """
    _patch_utub_tags(monkeypatch, [SimpleNamespace(id=7, tag_string="Tool")])

    assert build_tag_name_snapshot_from_ids([7, 99]) == {"7": "Tool"}
