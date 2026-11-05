from __future__ import annotations

from typing import Any, get_args

import pytest

from backend.models.user_preferences import (
    CollapsedTagsStyle,
    Density,
    SortOrder,
    TagCountStyle,
    TagMatchMode,
    TagSort,
    ViewMode,
)
from backend.schemas.utub_member_settings import (
    MemberTagsSettings,
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


TAGS_DEFAULTS: dict[str, Any] = {
    "tag_sort": None,
    "tag_match_mode": None,
    "tag_count_style": None,
    "show_tags_on_collapsed": None,
    "collapsed_tags_style": None,
    "tag_drop_opens_url": None,
}
ALL_DEFAULTS: dict[str, Any] = {"urls": URLS_DEFAULTS, "tags": TAGS_DEFAULTS}


def _literal_values(
    field_name: str, section_cls: type = MemberUrlsSettings
) -> set[str]:
    annotation = section_cls.model_fields[field_name].annotation
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
    for field_name, enum_cls in (
        ("tag_sort", TagSort),
        ("tag_match_mode", TagMatchMode),
        ("tag_count_style", TagCountStyle),
        ("collapsed_tags_style", CollapsedTagsStyle),
    ):
        assert _literal_values(field_name, MemberTagsSettings) == {
            member.value for member in enum_cls
        }


@pytest.mark.parametrize(
    "raw",
    [
        None,
        {},
        {"urls": {}},
        {"urls": None},
        {"tags": None},
        {"tags": "junk"},
        {"tags": []},
        "junk",
        [],
    ],
)
def test_resolve_defaults(raw: Any):
    assert resolve_member_settings(raw).model_dump() == ALL_DEFAULTS


def test_resolve_tags_applies_valid_and_drops_invalid_or_unknown():
    resolved = resolve_member_settings(
        {
            "tags": {
                "tag_sort": "newest",
                "tag_match_mode": "bogus",
                "tag_drop_opens_url": False,
                "retired": 1,
            }
        }
    )
    assert resolved.tags.model_dump() == {
        **TAGS_DEFAULTS,
        "tag_sort": "newest",
        "tag_drop_opens_url": False,
    }


def test_resolve_stored_row_without_tags_is_all_null():
    resolved = resolve_member_settings({"urls": {"sort": "oldest"}})
    assert resolved.tags.model_dump() == TAGS_DEFAULTS


def test_merge_tags_patch_leaves_urls_untouched():
    result = merge_member_settings(
        {"urls": {"sort": "oldest"}}, {"tags": {"tag_sort": "newest"}}
    )
    assert result == {"urls": {"sort": "oldest"}, "tags": {"tag_sort": "newest"}}


def test_merge_urls_patch_leaves_tags_untouched():
    result = merge_member_settings(
        {"tags": {"tag_sort": "newest"}}, {"urls": {"sort": "oldest"}}
    )
    assert result == {"urls": {"sort": "oldest"}, "tags": {"tag_sort": "newest"}}


def test_merge_tags_false_boolean_is_kept_and_null_clears_it():
    stored = merge_member_settings(None, {"tags": {"tag_drop_opens_url": False}})
    assert stored == {"tags": {"tag_drop_opens_url": False}}
    assert merge_member_settings(stored, {"tags": {"tag_drop_opens_url": None}}) is None


def test_merge_tags_rejects_invalid_value():
    with pytest.raises(UtubMemberSettingsPatchError) as exc_info:
        merge_member_settings(None, {"tags": {"tag_sort": "bogus"}})
    assert set(exc_info.value.errors) == {"tags.tag_sort"}


def test_merge_tags_rejects_unknown_key():
    with pytest.raises(UtubMemberSettingsPatchError) as exc_info:
        merge_member_settings(None, {"tags": {"nope": 1}})
    assert set(exc_info.value.errors) == {"tags.nope"}


def test_resolve_applies_stored_overrides():
    resolved = resolve_member_settings(
        {"urls": {"sort": "title_az", "hide_date_added": True}}
    )
    assert resolved.urls.sort == "title_az"
    assert resolved.urls.hide_date_added is True
    assert resolved.urls.hide_copy_button is False


@pytest.mark.parametrize("view_mode", ["list", "title_line", "url_line", "cards"])
def test_resolve_accepts_valid_view_modes(view_mode: str):
    resolved = resolve_member_settings({"urls": {"view_mode": view_mode}})
    assert resolved.urls.view_mode == view_mode


def test_resolve_drops_retired_compact_view_mode():
    resolved = resolve_member_settings({"urls": {"view_mode": "compact"}})
    assert resolved.urls.view_mode is None


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
        ("view_mode", "compact"),
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
        merge_member_settings(None, {"urls": {"bogus": True}, "utubs": {"x": 1}})
    assert set(exc_info.value.errors) == {"urls.bogus", "utubs"}


def test_merge_rejects_non_object_section():
    with pytest.raises(UtubMemberSettingsPatchError) as exc_info:
        merge_member_settings(None, {"urls": True})
    assert set(exc_info.value.errors) == {"urls"}


def test_merge_drops_unknown_stored_keys_when_section_is_patched():
    result = merge_member_settings(
        {"urls": {"retired_key": 1, "sort": "oldest"}}, {"urls": {"density": "compact"}}
    )
    assert result == {"urls": {"sort": "oldest", "density": "compact"}}
