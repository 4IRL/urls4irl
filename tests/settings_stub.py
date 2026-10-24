"""Stub settings model for tests: most shipped sections are empty, so tests that
need an extra setting patch the settings-model seam to this subclass."""

from typing import Any

import pytest
from pydantic import Field

from backend.schemas import utub_settings
from backend.schemas.utub_settings import UrlsSettings, UtubSettings

STUB_KEY = "stub_flag"

# The resolved settings of a UTub with no stored overrides (only urls has keys).
URLS_DEFAULTS: dict[str, Any] = {
    "default_url_scheme": "https",
    "hide_scheme_selector": False,
}

DEFAULT_SETTINGS_DICT: dict[str, dict[str, Any]] = {
    "utubs": {},
    "members": {},
    "tags": {},
    "urls": dict(URLS_DEFAULTS),
}


class StubUrlsSettings(UrlsSettings):
    stub_flag: bool = False


class StubUtubSettings(UtubSettings):
    urls: StubUrlsSettings = Field(default_factory=StubUrlsSettings)


def patch_settings_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the single settings-model seam at ``StubUtubSettings``."""
    monkeypatch.setattr(utub_settings, "get_settings_model", lambda: StubUtubSettings)
