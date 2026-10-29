"""Per-member, per-UTub view settings model, resolver and merge.

Pure module: it must not import ``backend.models`` at top level, because
``backend.schemas`` loads before ``db.Model`` is ready. The Literal value sets
below mirror ``SortOrder``/``ViewMode``/``Density`` in
``backend/models/user_preferences.py`` (a unit test guards against drift).

Storage is sparse, like ``Utubs.settings``: ``UtubMembers.settings`` holds only
the keys that differ from their default, and ``None`` means "all defaults".
Wire keys are snake_case.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from backend.schemas.utub_settings import SettingsSection


class MemberUrlsSettings(SettingsSection):
    """A member's private view overrides for the URLs panel of one UTub."""

    hide_copy_button: bool = Field(
        default=False, description="Hide the Copy button on URL cards"
    )
    hide_short_link_button: bool = Field(
        default=False, description="Hide the Copy short link button on URL cards"
    )
    hide_date_added: bool = Field(
        default=False, description="Hide the date added on URL cards"
    )
    sort: Literal["newest", "oldest", "title_az"] | None = Field(
        default=None, description="URL sort override; null uses the account default"
    )
    view_mode: Literal["list", "title_line", "url_line", "cards"] | None = Field(
        default=None, description="Layout override; null uses the account default"
    )
    density: Literal["comfortable", "compact"] | None = Field(
        default=None, description="Density override; null uses the account default"
    )
    disable_swipe_delete: bool = Field(
        default=False, description="Turn off swipe to delete on touch screens"
    )


class UtubMemberSettings(BaseModel):
    """Resolved per-member settings for one UTub, one section per panel."""

    model_config = ConfigDict(extra="forbid")

    urls: MemberUrlsSettings = Field(
        default_factory=MemberUrlsSettings,
        description="The member's view overrides for the URLs panel",
    )


class UtubMemberSettingsPatchError(ValueError):
    """A member settings patch failed validation.

    ``errors`` maps dotted keys (``"<section>.<key>"``, or ``"<section>"`` for
    section-level errors) to messages.
    """

    def __init__(self, errors: dict[str, list[str]]) -> None:
        super().__init__(f"Invalid member settings patch: {sorted(errors)}")
        self.errors = errors


_SECTION_NAME = "urls"
_SECTION_CLS = MemberUrlsSettings


def _clean_stored_section(stored: Any) -> dict[str, Any]:
    """Known, individually valid stored overrides; anything else is dropped."""
    if not isinstance(stored, dict):
        return {}
    cleaned: dict[str, Any] = {}
    for key, value in stored.items():
        if key not in _SECTION_CLS.model_fields:
            continue
        try:
            _SECTION_CLS.model_validate({key: value}, strict=True)
        except ValidationError:
            continue
        cleaned[key] = value
    return cleaned


def resolve_member_settings(raw: dict | None) -> UtubMemberSettings:
    """Resolve stored overrides to full settings. Never raises (reads never 500)."""
    stored = raw.get(_SECTION_NAME) if isinstance(raw, dict) else None
    section = _SECTION_CLS.model_validate(_clean_stored_section(stored), strict=True)
    return UtubMemberSettings(urls=section)


def _is_nullable(key: str) -> bool:
    return _SECTION_CLS.model_fields[key].default is None


def merge_member_settings(raw: dict | None, patch: dict[str, Any]) -> dict | None:
    """Merge a per-section patch into stored overrides.

    Returns the new sparse overrides (``None`` when nothing remains). A key
    equal to its default is removed, and an explicit ``null`` on an enum key
    removes it. Raises ``UtubMemberSettingsPatchError`` for an unknown section
    or key, a ``null`` on a boolean key, or an invalid value.
    """
    raw_dict = raw if isinstance(raw, dict) else {}
    errors: dict[str, list[str]] = {}
    new_overrides: dict[str, Any] = dict(raw_dict)

    for name, patch_section in patch.items():
        if name != _SECTION_NAME:
            errors[name] = ["Unknown settings section"]
            continue
        if not isinstance(patch_section, dict):
            errors[name] = ["Settings section must be an object"]
            continue
        merged = _clean_stored_section(raw_dict.get(name))
        for key, value in patch_section.items():
            if key not in _SECTION_CLS.model_fields:
                errors.setdefault(f"{name}.{key}", []).append("Unknown setting")
            elif value is None and _is_nullable(key):
                merged.pop(key, None)
            elif value is None:
                errors.setdefault(f"{name}.{key}", []).append("Value cannot be null")
            else:
                merged[key] = value
        if errors:
            continue
        try:
            section = _SECTION_CLS.model_validate(merged, strict=True)
        except ValidationError as exc:
            for error in exc.errors():
                loc = error["loc"]
                key = f"{name}.{loc[0]}" if loc else name
                errors.setdefault(key, []).append(error["msg"])
            continue
        sparse = {
            key: value
            for key, value in section.model_dump(mode="json").items()
            if key in merged and value != _SECTION_CLS.model_fields[key].default
        }
        if sparse:
            new_overrides[name] = sparse
        else:
            new_overrides.pop(name, None)

    if errors:
        raise UtubMemberSettingsPatchError(errors)
    return new_overrides or None
