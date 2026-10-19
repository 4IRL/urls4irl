"""Stub settings model for tests: the shipped sections are empty, so tests that
need a real setting patch the settings-model seam to this subclass."""

import pytest
from pydantic import Field

from backend.schemas import utub_settings
from backend.schemas.utub_settings import UrlsSettings, UtubSettings

STUB_KEY = "stub_flag"


class StubUrlsSettings(UrlsSettings):
    stub_flag: bool = False


class StubUtubSettings(UtubSettings):
    urls: StubUrlsSettings = Field(default_factory=StubUrlsSettings)


def patch_settings_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the single settings-model seam at ``StubUtubSettings``."""
    monkeypatch.setattr(utub_settings, "get_settings_model", lambda: StubUtubSettings)
