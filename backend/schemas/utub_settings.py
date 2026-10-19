"""Per-UTub settings model, resolver and merge.

Pure module: it must not import ``backend.models`` at top level, because
``backend.schemas`` loads before ``db.Model`` is ready.

Wire keys are snake_case everywhere (section names, setting keys, dotted
error keys). Storage is sparse: ``Utubs.settings`` holds only the keys a
caller explicitly set (or a section's ``normalize`` set), so changing a
default later reaches every UTub that never overrode it.
"""

from __future__ import annotations

from typing import Any, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    ValidationInfo,
    model_validator,
)

from backend.app_logger import warning_log

_NO_PATCHED_KEYS: frozenset[str] = frozenset()


class SettingsSection(BaseModel):
    """Base class of one namespaced settings section."""

    model_config = ConfigDict(extra="forbid")

    def normalize(self, patched_keys: frozenset[str]) -> Self:
        """Adjust dependent keys after field validation.

        ``patched_keys`` are the keys the caller explicitly set in this
        request (empty on reads), as opposed to keys merely stored. May assign
        fields; raise ``ValueError`` for a state it cannot fix.
        """
        return self

    @model_validator(mode="after")
    def _run_normalize(self, info: ValidationInfo) -> Self:
        context = info.context or {}
        return self.normalize(context.get("patched_keys", _NO_PATCHED_KEYS))


class UtubsSettings(SettingsSection):
    """Settings for the UTub panel (no settings yet)."""


class MembersSettings(SettingsSection):
    """Settings for the members panel (no settings yet)."""


class TagsSettings(SettingsSection):
    """Settings for the tags panel (no settings yet)."""


class UrlsSettings(SettingsSection):
    """Settings for the URLs panel (no settings yet)."""


class UtubSettings(BaseModel):
    """Resolved per-UTub settings, one namespaced section per panel."""

    model_config = ConfigDict(extra="forbid")

    utubs: UtubsSettings = Field(
        default_factory=UtubsSettings, description="Settings for the UTub panel"
    )
    members: MembersSettings = Field(
        default_factory=MembersSettings, description="Settings for the members panel"
    )
    tags: TagsSettings = Field(
        default_factory=TagsSettings, description="Settings for the tags panel"
    )
    urls: UrlsSettings = Field(
        default_factory=UrlsSettings, description="Settings for the URLs panel"
    )


class UtubSettingsPatchError(ValueError):
    """A settings patch failed validation.

    ``errors`` maps dotted keys (``"<section>.<key>"``, or ``"<section>"`` for
    section-level errors) to messages.
    """

    def __init__(self, errors: dict[str, list[str]]) -> None:
        super().__init__(f"Invalid UTub settings patch: {sorted(errors)}")
        self.errors = errors


def get_settings_model() -> type[UtubSettings]:
    """The single seam for the settings model.

    Resolve, merge (and, later, the schema fields) all go through here, so one
    monkeypatch to a ``UtubSettings`` subclass drives every path.
    """
    return UtubSettings


def _section_class(model: type[UtubSettings], name: str) -> type[SettingsSection]:
    annotation = model.model_fields[name].annotation
    assert isinstance(annotation, type) and issubclass(annotation, SettingsSection)
    return annotation


def _clean_stored_section(
    section_name: str,
    section_cls: type[SettingsSection],
    stored: Any,
    *,
    warn: bool,
) -> dict[str, Any]:
    """Known, valid stored overrides of a section; invalid or non-dict -> {}."""
    if not isinstance(stored, dict):
        if warn:
            warning_log(f"UTub settings section '{section_name}' is not an object")
        return {}
    known = {
        key: value for key, value in stored.items() if key in section_cls.model_fields
    }
    if warn and len(known) != len(stored):
        warning_log(f"UTub settings section '{section_name}' had unknown keys dropped")
    try:
        section_cls.model_validate(known, context={"patched_keys": _NO_PATCHED_KEYS})
    except ValidationError:
        if warn:
            warning_log(
                f"UTub settings section '{section_name}' is invalid, using defaults"
            )
        return {}
    return known


def _resolve_sections(raw: Any, *, warn: bool) -> dict[str, SettingsSection]:
    model = get_settings_model()
    raw_dict = raw if isinstance(raw, dict) else {}
    if raw is not None and not isinstance(raw, dict) and warn:
        warning_log("UTub settings value is not an object, using defaults")
    sections: dict[str, SettingsSection] = {}
    for name in model.model_fields:
        section_cls = _section_class(model, name)
        if name not in raw_dict:
            sections[name] = section_cls()
            continue
        cleaned = _clean_stored_section(name, section_cls, raw_dict[name], warn=warn)
        sections[name] = section_cls.model_validate(
            cleaned, context={"patched_keys": _NO_PATCHED_KEYS}
        )
    return sections


def resolve_utub_settings(raw: dict | None) -> UtubSettings:
    """Resolve stored overrides to full settings. Never raises (reads never 500)."""
    # model_construct: the sections are already validated; passing instances to
    # the constructor would re-run each section's normalize hook.
    return get_settings_model().model_construct(**_resolve_sections(raw, warn=True))


def merge_utub_settings(
    raw: dict | None, patch: dict[str, dict[str, Any]]
) -> tuple[UtubSettings, dict | None]:
    """Merge a per-section patch into stored overrides.

    Returns the full resolved settings and the new sparse overrides (``None``
    when nothing remains). Unpatched sections are copied verbatim from ``raw``;
    only patched sections are re-dumped. Raises ``UtubSettingsPatchError``
    (all sections' errors aggregated) when a patched section is invalid.
    """
    model = get_settings_model()
    raw_dict = raw if isinstance(raw, dict) else {}
    sections = _resolve_sections(raw_dict, warn=False)
    new_overrides: dict[str, Any] = dict(raw_dict)
    errors: dict[str, list[str]] = {}

    for name, patch_section in patch.items():
        if name not in model.model_fields:
            errors[name] = ["Unknown settings section"]
            continue
        section_cls = _section_class(model, name)
        stored = _clean_stored_section(
            name, section_cls, raw_dict.get(name), warn=False
        )
        merged = {**stored, **patch_section}
        try:
            section = section_cls.model_validate(
                merged, context={"patched_keys": frozenset(patch_section)}
            )
        except ValidationError as exc:
            for error in exc.errors():
                loc = error["loc"]
                key = f"{name}.{loc[0]}" if loc else name
                errors.setdefault(key, []).append(error["msg"])
            continue
        sections[name] = section
        dumped = section.model_dump(mode="json", exclude_unset=True)
        if dumped:
            new_overrides[name] = dumped
        else:
            new_overrides.pop(name, None)

    if errors:
        raise UtubSettingsPatchError(errors)
    return model.model_construct(**sections), (new_overrides or None)


def _canonical_overrides(overrides: Any) -> dict[str, Any]:
    if not isinstance(overrides, dict):
        return {} if overrides is None else {"": overrides}
    return {
        key: value
        for key, value in overrides.items()
        if not (isinstance(value, dict) and not value)
    }


def utub_settings_overrides_changed(
    raw: dict | None, new_overrides: dict | None
) -> bool:
    """Whether new overrides differ from the raw stored value.

    ``None`` equals ``{}`` and empty section dicts are dropped on both sides.
    """
    return _canonical_overrides(raw) != _canonical_overrides(new_overrides)
