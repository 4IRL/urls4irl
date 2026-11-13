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
    "allow_short_links": True,
}

DEFAULT_SETTINGS_DICT: dict[str, dict[str, Any]] = {
    "utubs": {},
    "members": {
        "co_owners_can_remove": False,
        "members_can_add": False,
        "hide_member_list": False,
    },
    "tags": {"members_can_tag": True, "members_can_delete_tags": True},
    "urls": dict(URLS_DEFAULTS),
}


# The resolved ``memberSettings`` of a member with no stored overrides.
DEFAULT_MEMBER_SETTINGS_DICT: dict[str, dict[str, Any]] = {
    "urls": {
        "hide_copy_button": False,
        "hide_short_link_button": False,
        "hide_date_added": False,
        "sort": None,
        "view_mode": None,
        "density": None,
        "disable_swipe_delete": False,
    },
    "tags": {
        "tag_sort": None,
        "tag_match_mode": None,
        "tag_count_style": None,
        "show_tags_on_collapsed": None,
        "collapsed_tags_style": None,
        "tag_drop_opens_url": None,
    },
}

# The ``tagDisplayDefaults`` of a user with no stored preferences row.
DEFAULT_TAG_DISPLAY_DEFAULTS_DICT: dict[str, Any] = {
    "tagSort": "most_in_view",
    "tagMatchMode": "all",
    "tagCountStyle": "in_view_total",
    "showTagsOnCollapsed": False,
    "collapsedTagsStyle": "one_line",
    "tagDropOpensUrl": True,
}


class StubUrlsSettings(UrlsSettings):
    stub_flag: bool = False


class StubUtubSettings(UtubSettings):
    urls: StubUrlsSettings = Field(default_factory=StubUrlsSettings)


def patch_settings_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the single settings-model seam at ``StubUtubSettings``."""
    monkeypatch.setattr(utub_settings, "get_settings_model", lambda: StubUtubSettings)
