from typing import Any
from unittest.mock import MagicMock

import pytest

import backend.schemas.utub_settings as settings_module
from backend.models.utubs import Utubs
from backend.tags.services.tag_permissions import can_delete_tags, can_tag

pytestmark = pytest.mark.unit

CORRUPT_VALUES = ["garbage", 2, None, [True]]


@pytest.fixture(autouse=True)
def warning_log_mock(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Corrupt settings log a warning that needs an app context; capture it."""
    mock = MagicMock()
    monkeypatch.setattr(settings_module, "warning_log", mock)
    return mock


def _utub_with_settings(settings: Any) -> Utubs:
    utub = Utubs(name="Tag perms", utub_creator=1, utub_description="")
    utub.settings = settings
    return utub


@pytest.mark.parametrize(
    "tags, expected_tag, expected_delete",
    [
        pytest.param(None, True, True, id="unconfigured"),
        pytest.param({}, True, True, id="empty_section"),
        pytest.param({"members_can_tag": True}, True, True, id="tag_on"),
        pytest.param({"members_can_tag": False}, False, False, id="tag_off"),
        pytest.param({"members_can_delete_tags": False}, True, False, id="delete_off"),
        pytest.param(
            {"members_can_tag": False, "members_can_delete_tags": True},
            False,
            False,
            id="tag_off_delete_stored_on",
        ),
        pytest.param(
            {"members_can_tag": False, "members_can_delete_tags": False},
            False,
            False,
            id="both_off",
        ),
        pytest.param(
            {"members_can_tag": True, "members_can_delete_tags": False},
            True,
            False,
            id="tag_on_delete_off",
        ),
    ],
)
def test_plain_member_switch_combinations(
    tags: dict[str, bool] | None, expected_tag: bool, expected_delete: bool
) -> None:
    """
    GIVEN a UTub with a stored tags section and a plain member
    WHEN can_tag and can_delete_tags are evaluated
    THEN delete is allowed only while tagging is also on
    """
    settings = None if tags is None else {"tags": tags}
    utub = _utub_with_settings(settings)
    assert can_tag(utub, is_manager=False) is expected_tag
    assert can_delete_tags(utub, is_manager=False) is expected_delete


@pytest.mark.parametrize(
    "tags",
    [
        {"members_can_tag": False, "members_can_delete_tags": False},
        {"members_can_tag": False},
        {"members_can_delete_tags": False},
    ],
)
def test_manager_is_never_gated(tags: dict[str, bool]) -> None:
    """
    GIVEN a UTub with tagging and deleting switched off
    WHEN a manager is evaluated
    THEN the manager is always allowed
    """
    utub = _utub_with_settings({"tags": tags})
    assert can_tag(utub, is_manager=True) is True
    assert can_delete_tags(utub, is_manager=True) is True


@pytest.mark.parametrize("value", CORRUPT_VALUES)
@pytest.mark.parametrize("key", ["members_can_tag", "members_can_delete_tags"])
def test_corrupt_value_resolves_to_defaults(key: str, value: Any) -> None:
    """
    GIVEN a stored tags value that is not a bool
    WHEN a plain member is evaluated
    THEN the section resolves to the (true) defaults and the member is allowed
    """
    utub = _utub_with_settings({"tags": {key: value}})
    assert can_tag(utub, is_manager=False) is True
    assert can_delete_tags(utub, is_manager=False) is True


@pytest.mark.parametrize("section", ["garbage", 2, None, [True]])
def test_corrupt_section_resolves_to_defaults(section: Any) -> None:
    """
    GIVEN a stored tags section that is not a dict
    WHEN a plain member is evaluated
    THEN it resolves to the defaults and the member is allowed
    """
    utub = _utub_with_settings({"tags": section})
    assert can_tag(utub, is_manager=False) is True
    assert can_delete_tags(utub, is_manager=False) is True


@pytest.mark.parametrize("settings", [None, {}, {"tags": None}])
def test_missing_settings_resolve_to_defaults(settings: Any) -> None:
    """
    GIVEN a UTub whose stored settings are missing
    WHEN a plain member is evaluated
    THEN the resolver defaults apply (both true), so the member is allowed, and a
        non-manager flag is never bypassed
    """
    utub = _utub_with_settings(settings)
    assert can_tag(utub, is_manager=False) is True
    assert can_delete_tags(utub, is_manager=False) is True


def test_mixed_corrupt_invalidates_whole_section() -> None:
    """
    GIVEN tagging stored off and a corrupt delete value
    WHEN a plain member is evaluated
    THEN the whole section resolves to the defaults and the member is allowed
    """
    utub = _utub_with_settings(
        {"tags": {"members_can_tag": False, "members_can_delete_tags": "garbage"}}
    )
    assert can_tag(utub, is_manager=False) is True
    assert can_delete_tags(utub, is_manager=False) is True
