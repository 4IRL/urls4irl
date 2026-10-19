from __future__ import annotations

from typing import Any, Self
from unittest.mock import MagicMock

import pytest
from pydantic import Field

import backend.schemas.utub_settings as settings_module
from backend.schemas.utub_settings import (
    SettingsSection,
    UtubSettings,
    UtubSettingsPatchError,
    merge_utub_settings,
    resolve_utub_settings,
    utub_settings_overrides_changed,
)

pytestmark = pytest.mark.unit

SECTION_NAMES = ("utubs", "members", "tags", "urls")
RECORDED_PATCHED_KEYS: list[frozenset[str]] = []


class StubSection(SettingsSection):
    """Test section with a dependent key, a repairable and a rejected state."""

    mode: str = Field(default="a", description="Mode, 'a' or 'b'")
    limit: int = Field(default=0, ge=0, description="Positive limit needs enabled")
    enabled: bool = Field(default=False, description="Whether the feature is on")

    def normalize(self, patched_keys: frozenset[str]) -> Self:
        RECORDED_PATCHED_KEYS.append(patched_keys)
        if "enabled" in patched_keys and not self.enabled:
            self.limit = 0
        elif self.limit > 0 and not self.enabled:
            self.enabled = True
        if self.mode == "b" and self.limit == 0:
            raise ValueError("mode b requires a positive limit")
        return self


class StubSettings(UtubSettings):
    """UtubSettings whose `urls` section is the stub."""

    urls: StubSection = Field(default_factory=StubSection, description="Stub section")


@pytest.fixture
def warning_log_mock(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    mock = MagicMock()
    monkeypatch.setattr(settings_module, "warning_log", mock)
    return mock


@pytest.fixture
def stub_model(monkeypatch: pytest.MonkeyPatch) -> None:
    RECORDED_PATCHED_KEYS.clear()
    monkeypatch.setattr(settings_module, "get_settings_model", lambda: StubSettings)


def test_resolve_none_equals_defaults(warning_log_mock: MagicMock) -> None:
    assert resolve_utub_settings(None) == UtubSettings()
    warning_log_mock.assert_not_called()


def test_resolve_partial_dict_fills_defaults(
    stub_model: None, warning_log_mock: MagicMock
) -> None:
    resolved = resolve_utub_settings({"urls": {"limit": 2}})
    assert resolved.urls.limit == 2
    assert resolved.urls.mode == "a"
    assert resolved.utubs == UtubSettings().utubs
    warning_log_mock.assert_not_called()


@pytest.mark.parametrize("raw", [[], "x", 5])
def test_resolve_non_dict_top_level(raw: Any, warning_log_mock: MagicMock) -> None:
    assert resolve_utub_settings(raw) == UtubSettings()
    assert warning_log_mock.call_count == 1


def test_resolve_non_dict_section(warning_log_mock: MagicMock) -> None:
    assert resolve_utub_settings({"utubs": "x"}) == UtubSettings()
    assert warning_log_mock.call_count == 1
    assert "utubs" in warning_log_mock.call_args.args[0]


def test_resolve_unknown_key_dropped(
    stub_model: None, warning_log_mock: MagicMock
) -> None:
    resolved = resolve_utub_settings({"urls": {"limit": 2, "legacy": 1}})
    assert resolved.urls.limit == 2
    assert warning_log_mock.call_count == 1
    assert "urls" in warning_log_mock.call_args.args[0]


def test_resolve_invalid_section_falls_back_to_defaults(
    stub_model: None, warning_log_mock: MagicMock
) -> None:
    resolved = resolve_utub_settings({"urls": {"limit": -1}})
    assert resolved.urls == StubSection()
    assert warning_log_mock.call_count == 1
    assert "urls" in warning_log_mock.call_args.args[0]


def test_merge_leaves_unpatched_sections_verbatim(stub_model: None) -> None:
    raw = {"members": {"legacy": 1}, "tags": {}, "urls": {"limit": 1}}
    resolved, new = merge_utub_settings(raw, {"urls": {"limit": 2}})
    assert new == {
        "members": {"legacy": 1},
        "tags": {},
        "urls": {"limit": 2, "enabled": True},
    }
    assert resolved.urls.limit == 2


def test_merge_strips_legacy_key_in_patched_section(stub_model: None) -> None:
    _, new = merge_utub_settings(
        {"urls": {"limit": 1, "legacy": 1}}, {"urls": {"mode": "a"}}
    )
    assert new is not None
    assert "legacy" not in new["urls"]
    assert new["urls"]["limit"] == 1


def test_merge_repair_then_valid(stub_model: None) -> None:
    # limit > 0 with enabled False violates the invariant until normalize repairs it.
    _, new = merge_utub_settings({"urls": {"limit": 2}}, {"urls": {"mode": "a"}})
    assert new == {"urls": {"limit": 2, "mode": "a", "enabled": True}}


def test_merge_normalize_dependent_key_persisted(stub_model: None) -> None:
    _, new = merge_utub_settings(None, {"urls": {"limit": 3}})
    assert new == {"urls": {"limit": 3, "enabled": True}}
    _, new = merge_utub_settings(new, {"urls": {"enabled": False}})
    assert new == {"urls": {"limit": 0, "enabled": False}}


def test_merge_normalize_gets_merged_state_and_patched_keys(stub_model: None) -> None:
    # stored limit=2 plus patched mode=b is valid only when normalize sees the merged limit.
    resolved, new = merge_utub_settings({"urls": {"limit": 2}}, {"urls": {"mode": "b"}})
    assert resolved.urls.mode == "b"
    assert new is not None
    assert new["urls"]["limit"] == 2
    assert RECORDED_PATCHED_KEYS[-1] == frozenset({"mode"})


def test_merge_empty_patch_returns_overrides_equal_to_raw(stub_model: None) -> None:
    raw = {"members": {"legacy": 1}, "urls": {"limit": 1, "enabled": True}}
    _, new = merge_utub_settings(raw, {})
    assert new == raw
    assert not utub_settings_overrides_changed(raw, new)


def test_merge_resetting_stored_value_with_legacy_key_is_no_change(
    stub_model: None,
) -> None:
    raw = {"members": {"legacy": 1}, "urls": {"limit": 1, "enabled": True}}
    _, new = merge_utub_settings(raw, {"urls": {"limit": 1}})
    assert not utub_settings_overrides_changed(raw, new)


def test_merge_unpatched_empty_section_survives(stub_model: None) -> None:
    raw = {"tags": {}}
    _, new = merge_utub_settings(raw, {})
    assert new == {"tags": {}}
    assert not utub_settings_overrides_changed(raw, new)


def test_merge_empty_section_patch_on_clean_section_is_no_change(
    stub_model: None,
) -> None:
    raw = {"urls": {"limit": 1, "enabled": True}}
    _, new = merge_utub_settings(raw, {"urls": {}})
    assert new == raw
    assert not utub_settings_overrides_changed(raw, new)
    assert not utub_settings_overrides_changed(
        {"urls": {}}, merge_utub_settings({"urls": {}}, {"urls": {}})[1]
    )


@pytest.mark.parametrize("stored", [{"limit": -1}, "x", ["y"]])
def test_merge_empty_section_patch_cleans_bad_section(
    stub_model: None, stored: Any
) -> None:
    raw = {"urls": stored}
    _, new = merge_utub_settings(raw, {"urls": {}})
    assert new is None
    assert utub_settings_overrides_changed(raw, new)


def test_merge_no_overrides_is_none() -> None:
    _, new = merge_utub_settings(None, {})
    assert new is None
    assert not utub_settings_overrides_changed(None, new)
    assert not utub_settings_overrides_changed({}, new)


def test_merge_explicit_default_value_is_pinned(stub_model: None) -> None:
    _, new = merge_utub_settings(None, {"urls": {"mode": "a"}})
    assert new == {"urls": {"mode": "a"}}
    assert utub_settings_overrides_changed(None, new)


def test_merge_unknown_key_in_patched_section_raises_dotted_key() -> None:
    with pytest.raises(UtubSettingsPatchError) as exc_info:
        merge_utub_settings(None, {"urls": {"nope": 1}})
    assert list(exc_info.value.errors) == ["urls.nope"]


def test_merge_invalid_value_raises_dotted_key(stub_model: None) -> None:
    with pytest.raises(UtubSettingsPatchError) as exc_info:
        merge_utub_settings(None, {"urls": {"limit": -1}})
    assert list(exc_info.value.errors) == ["urls.limit"]


def test_merge_two_invalid_sections_one_error(stub_model: None) -> None:
    with pytest.raises(UtubSettingsPatchError) as exc_info:
        merge_utub_settings(None, {"urls": {"limit": -1}, "tags": {"nope": 1}})
    assert set(exc_info.value.errors) == {"urls.limit", "tags.nope"}


def test_merge_normalize_value_error_keyed_by_section(stub_model: None) -> None:
    with pytest.raises(UtubSettingsPatchError) as exc_info:
        merge_utub_settings(None, {"urls": {"mode": "b"}})
    assert list(exc_info.value.errors) == ["urls"]


def test_merge_invalid_patch_does_not_mutate_raw(stub_model: None) -> None:
    raw = {"urls": {"limit": 1, "enabled": True}}
    with pytest.raises(UtubSettingsPatchError):
        merge_utub_settings(raw, {"urls": {"limit": -1}})
    assert raw == {"urls": {"limit": 1, "enabled": True}}


def test_merge_unknown_section_raises() -> None:
    with pytest.raises(UtubSettingsPatchError) as exc_info:
        merge_utub_settings(None, {"bogus": {}})
    assert list(exc_info.value.errors) == ["bogus"]


def test_wire_keys_are_snake_case() -> None:
    assert tuple(UtubSettings().model_dump(by_alias=True)) == SECTION_NAMES
    assert tuple(StubSettings().urls.model_dump(by_alias=True)) == (
        "mode",
        "limit",
        "enabled",
    )
