from __future__ import annotations

from typing import Any, get_args

import pytest

from backend.models.user_preferences import Density, SortOrder, ViewMode
from backend.schemas.utub_member_settings import (
    MemberUrlsSettings,
    UtubMemberSettings,
    UtubMemberSettingsPatchError,
    merge_member_settings,
    resolve_member_settings,
)

pytestmark = pytest.mark.unit

URLS_DEFAULTS: dict[str, Any] = {
    "hide_copy_button": False,
    "hide_short_link_button": False,
    "hide_date_added": False,
    "sort": None,
    "view_mode": None,
    "density": None,
    "disable_swipe_delete": False,
}


def _literal_values(field_name: str) -> set[str]:
    annotation = MemberUrlsSettings.model_fields[field_name].annotation
    return {
        value
        for union_member in get_args(annotation)
        for value in get_args(union_member)
    }


def test_literal_value_sets_match_preference_enums():
    """The Literal sets mirror the preference enums (drift guard)."""
    assert _literal_values("sort") == {member.value for member in SortOrder}
    assert _literal_values("view_mode") == {member.value for member in ViewMode}
    assert _literal_values("density") == {member.value for member in Density}


@pytest.mark.parametrize("raw", [None, {}, {"urls": {}}, {"urls": None}, "junk", []])
def test_resolve_defaults(raw: Any):
    assert resolve_member_settings(raw).model_dump() == {"urls": URLS_DEFAULTS}


def test_resolve_applies_stored_overrides():
    resolved = resolve_member_settings(
        {"urls": {"sort": "title_az", "hide_date_added": True}}
    )
    assert resolved.urls.sort == "title_az"
    assert resolved.urls.hide_date_added is True
    assert resolved.urls.hide_copy_button is False


def test_resolve_ignores_unknown_and_invalid_stored_keys():
    resolved = resolve_member_settings(
        {
            "urls": {"retired_key": 1, "sort": "bogus", "density": "compact"},
            "other": {"x": 1},
        }
    )
    assert resolved.urls.sort is None
    assert resolved.urls.density == "compact"


def test_resolved_model_is_utub_member_settings():
    assert isinstance(resolve_member_settings(None), UtubMemberSettings)


def test_merge_sets_keys_sparsely():
    result = merge_member_settings(None, {"urls": {"sort": "oldest"}})
    assert result == {"urls": {"sort": "oldest"}}


def test_merge_preserves_existing_overrides():
    result = merge_member_settings(
        {"urls": {"hide_copy_button": True}}, {"urls": {"density": "compact"}}
    )
    assert result == {"urls": {"hide_copy_button": True, "density": "compact"}}


def test_merge_removes_key_equal_to_default():
    result = merge_member_settings(
        {"urls": {"hide_copy_button": True, "sort": "oldest"}},
        {"urls": {"hide_copy_button": False}},
    )
    assert result == {"urls": {"sort": "oldest"}}


def test_merge_all_default_result_is_none():
    assert (
        merge_member_settings(
            {"urls": {"hide_copy_button": True}}, {"urls": {"hide_copy_button": False}}
        )
        is None
    )


@pytest.mark.parametrize(
    "key, stored_value",
    [("sort", "oldest"), ("view_mode", "list"), ("density", "compact")],
)
def test_merge_null_clears_enum_key(key: str, stored_value: str):
    result = merge_member_settings(
        {"urls": {key: stored_value, "hide_date_added": True}},
        {"urls": {key: None}},
    )
    assert result == {"urls": {"hide_date_added": True}}


@pytest.mark.parametrize(
    "key",
    [
        "hide_copy_button",
        "hide_short_link_button",
        "hide_date_added",
        "disable_swipe_delete",
    ],
)
def test_merge_null_on_boolean_key_is_rejected(key: str):
    with pytest.raises(UtubMemberSettingsPatchError) as exc_info:
        merge_member_settings(None, {"urls": {key: None}})
    assert set(exc_info.value.errors) == {f"urls.{key}"}


@pytest.mark.parametrize(
    "key, value",
    [
        ("sort", "bogus"),
        ("view_mode", "grid"),
        ("density", "tight"),
        ("hide_copy_button", "yes"),
        ("hide_date_added", 1),
    ],
)
def test_merge_rejects_invalid_values(key: str, value: Any):
    with pytest.raises(UtubMemberSettingsPatchError) as exc_info:
        merge_member_settings(None, {"urls": {key: value}})
    assert f"urls.{key}" in exc_info.value.errors


def test_merge_rejects_unknown_key_and_section():
    with pytest.raises(UtubMemberSettingsPatchError) as exc_info:
        merge_member_settings(None, {"urls": {"bogus": True}, "tags": {"x": 1}})
    assert set(exc_info.value.errors) == {"urls.bogus", "tags"}


def test_merge_rejects_non_object_section():
    with pytest.raises(UtubMemberSettingsPatchError) as exc_info:
        merge_member_settings(None, {"urls": True})
    assert set(exc_info.value.errors) == {"urls"}


def test_merge_drops_unknown_stored_keys_when_section_is_patched():
    result = merge_member_settings(
        {"urls": {"retired_key": 1, "sort": "oldest"}}, {"urls": {"density": "compact"}}
    )
    assert result == {"urls": {"sort": "oldest", "density": "compact"}}
