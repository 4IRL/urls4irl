"""Tests for the invite-link preview effective-window helper and the stored columns."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from flask import Flask
from sqlalchemy.exc import IntegrityError

from backend import db
from backend.invite_links.constants import InviteState
from backend.invite_links.preview import (
    EffectivePreview,
    apply_preview_change,
    compute_effective_preview,
)
from backend.models.utub_invite_links import Utub_Invite_Links
from tests.utils_for_test import add_invite_link

pytestmark = pytest.mark.invite_links

NOW: datetime = datetime(2026, 11, 13, 12, 0, 0, tzinfo=timezone.utc)
_UTC_NOW_PATH: str = "backend.invite_links.preview.utc_now"


def _row(
    *,
    enabled: bool = False,
    window_days: int = 3,
    ends_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> Utub_Invite_Links:
    invite = Utub_Invite_Links(
        utub_id=1,
        token="T" * 22,
        created_by=1,
        expires_at=expires_at or NOW + timedelta(days=30),
    )
    invite.preview_enabled = enabled
    invite.preview_window_days = window_days
    invite.preview_ends_at = ends_at
    return invite


def _effective(invite: Utub_Invite_Links, state: InviteState = InviteState.LIVE):
    with patch(_UTC_NOW_PATH, return_value=NOW):
        return compute_effective_preview(invite, state=state)


def test_stored_off_is_off() -> None:
    """
    GIVEN a row with preview stored off
    WHEN the effective preview is computed
    THEN it is off with no end
    """
    assert _effective(_row()) == EffectivePreview(enabled=False, ends_at=None)


def test_stored_on_with_null_end_fails_closed() -> None:
    """
    GIVEN a row stored on with a NULL end
    WHEN the effective preview is computed
    THEN it is off with no end
    """
    assert _effective(_row(enabled=True)) == EffectivePreview(False, None)


def test_window_end_before_expiry_is_the_end() -> None:
    """
    GIVEN a stored end earlier than the link expiry
    WHEN the effective preview is computed
    THEN it is on and ends at the stored end
    """
    ends_at = NOW + timedelta(days=1)
    result = _effective(_row(enabled=True, ends_at=ends_at))
    assert result == EffectivePreview(enabled=True, ends_at=ends_at)


def test_expiry_before_window_end_caps_the_end() -> None:
    """
    GIVEN a link expiring before the stored preview end
    WHEN the effective preview is computed
    THEN the end is capped at expires_at
    """
    expires_at = NOW + timedelta(hours=5)
    invite = _row(enabled=True, ends_at=NOW + timedelta(days=3), expires_at=expires_at)
    result = _effective(invite)
    assert result == EffectivePreview(enabled=True, ends_at=expires_at)


def test_end_exactly_now_is_off() -> None:
    """
    GIVEN an effective end exactly at now
    WHEN the effective preview is computed
    THEN it is off (strict less-than) and still reports the end
    """
    result = _effective(_row(enabled=True, ends_at=NOW))
    assert result == EffectivePreview(enabled=False, ends_at=NOW)


@pytest.mark.parametrize(
    "state",
    [state for state in InviteState if state is not InviteState.LIVE],
)
def test_non_live_state_is_off_but_reports_end(state: InviteState) -> None:
    """
    GIVEN a stored-on, unexpired preview on a link in a non-LIVE state
    WHEN the effective preview is computed
    THEN it is off while the end is still reported
    """
    ends_at = NOW + timedelta(days=1)
    result = _effective(_row(enabled=True, ends_at=ends_at), state)
    assert result == EffectivePreview(enabled=False, ends_at=ends_at)


def _apply(
    invite: Utub_Invite_Links, *, enabled: bool | None, window_days: int | None
) -> None:
    with patch(_UTC_NOW_PATH, return_value=NOW):
        apply_preview_change(invite, enabled=enabled, window_days=window_days)


def test_apply_on_from_off_anchors_now_plus_days() -> None:
    """
    GIVEN a stored-off row with window 3
    WHEN preview is enabled
    THEN it is on and ends at now + 3 days
    """
    invite = _row()
    _apply(invite, enabled=True, window_days=None)
    assert invite.preview_enabled is True
    assert invite.preview_ends_at == NOW + timedelta(days=3)


def test_apply_window_change_while_on_reanchors() -> None:
    """
    GIVEN a live stored-on row
    WHEN a different window is sent
    THEN the days are stored and the end is re-anchored
    """
    invite = _row(enabled=True, window_days=3, ends_at=NOW + timedelta(hours=1))
    _apply(invite, enabled=None, window_days=7)
    assert invite.preview_window_days == 7
    assert invite.preview_ends_at == NOW + timedelta(days=7)


def test_apply_same_window_while_on_restarts_window() -> None:
    """
    GIVEN a live stored-on row
    WHEN the same window value is resent
    THEN the end is re-anchored to now + days
    """
    invite = _row(enabled=True, window_days=3, ends_at=NOW + timedelta(hours=1))
    _apply(invite, enabled=None, window_days=3)
    assert invite.preview_ends_at == NOW + timedelta(days=3)


def test_apply_window_change_while_off_stores_days_only() -> None:
    """
    GIVEN a stored-off row
    WHEN a window is sent alone
    THEN the days are stored and the end stays NULL
    """
    invite = _row()
    _apply(invite, enabled=None, window_days=7)
    assert invite.preview_enabled is False
    assert invite.preview_window_days == 7
    assert invite.preview_ends_at is None


def test_apply_off_clears_end_and_keeps_days() -> None:
    """
    GIVEN a stored-on row with window 7
    WHEN preview is disabled
    THEN it is off, the end is NULL and the days are kept
    """
    invite = _row(enabled=True, window_days=7, ends_at=NOW + timedelta(days=2))
    _apply(invite, enabled=False, window_days=None)
    assert invite.preview_enabled is False
    assert invite.preview_ends_at is None
    assert invite.preview_window_days == 7


def test_apply_on_while_on_is_noop() -> None:
    """
    GIVEN a live stored-on row within its end
    WHEN preview is enabled again with no window
    THEN the end is unchanged
    """
    ends_at = NOW + timedelta(hours=2)
    invite = _row(enabled=True, ends_at=ends_at)
    _apply(invite, enabled=True, window_days=None)
    assert invite.preview_ends_at == ends_at


def test_apply_on_for_lapsed_row_reanchors() -> None:
    """
    GIVEN a stored-on row whose end has passed
    WHEN preview is enabled
    THEN it is re-anchored to now + days and no longer lapsed
    """
    invite = _row(enabled=True, window_days=3, ends_at=NOW - timedelta(days=1))
    _apply(invite, enabled=True, window_days=None)
    assert invite.preview_ends_at == NOW + timedelta(days=3)
    assert _effective(invite).enabled is True


def test_apply_window_on_lapsed_row_reanchors() -> None:
    """
    GIVEN a stored-on row whose end has passed
    WHEN a window is sent
    THEN the days are stored and the end is re-anchored
    """
    invite = _row(enabled=True, window_days=3, ends_at=NOW - timedelta(days=1))
    _apply(invite, enabled=None, window_days=1)
    assert invite.preview_window_days == 1
    assert invite.preview_ends_at == NOW + timedelta(days=1)


def test_apply_both_fields_anchors_once_with_new_days() -> None:
    """
    GIVEN a stored-off row
    WHEN enabled and a window are sent together
    THEN the end is now + the new days
    """
    invite = _row()
    _apply(invite, enabled=True, window_days=7)
    assert invite.preview_enabled is True
    assert invite.preview_ends_at == NOW + timedelta(days=7)


def test_apply_none_none_is_noop() -> None:
    """
    GIVEN a stored-on row
    WHEN neither field is sent
    THEN nothing changes
    """
    ends_at = NOW + timedelta(hours=2)
    invite = _row(enabled=True, window_days=7, ends_at=ends_at)
    _apply(invite, enabled=None, window_days=None)
    assert invite.preview_enabled is True
    assert invite.preview_window_days == 7
    assert invite.preview_ends_at == ends_at


def test_new_row_defaults_to_preview_off(
    app: Flask, every_user_makes_a_unique_utub
) -> None:
    """
    GIVEN a link created without preview kwargs
    WHEN it is read back
    THEN preview is off, window 3 and no end
    """
    invite_id = add_invite_link(app, 1, 1)
    with app.app_context():
        invite = db.session.get(Utub_Invite_Links, invite_id)
        assert invite.preview_enabled is False
        assert invite.preview_window_days == 3
        assert invite.preview_ends_at is None


def test_enabled_without_end_is_rejected(
    app: Flask, every_user_makes_a_unique_utub
) -> None:
    """
    GIVEN a link row
    WHEN it is inserted with preview enabled and no end
    THEN the CHECK constraint raises IntegrityError
    """
    with pytest.raises(IntegrityError):
        add_invite_link(app, 1, 1, preview_enabled=True, preview_ends_at=None)
