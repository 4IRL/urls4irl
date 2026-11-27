from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from backend.invite_links.constants import InviteState
from backend.models.utub_invite_links import Utub_Invite_Links
from backend.utils.datetime_utils import utc_now


@dataclass(frozen=True)
class EffectivePreview:
    """The read-time preview values: whether it is on right now, and its capped end."""

    enabled: bool
    ends_at: datetime | None


def compute_effective_preview(
    invite: Utub_Invite_Links, *, state: InviteState
) -> EffectivePreview:
    """Derive the effective preview from the stored columns, the expiry and the state.

    Fails closed: a row that is not stored-enabled, or has no stored end, is off with
    no end. Otherwise the end is ``min(preview_ends_at, expires_at)`` and the preview
    is on only for a ``LIVE`` link strictly before that end.
    """
    if not invite.preview_enabled or invite.preview_ends_at is None:
        return EffectivePreview(enabled=False, ends_at=None)
    ends_at = min(invite.preview_ends_at, invite.expires_at)
    enabled = state == InviteState.LIVE and utc_now() < ends_at
    return EffectivePreview(enabled=enabled, ends_at=ends_at)


def preview_is_on(invite: Utub_Invite_Links, *, now: datetime) -> bool:
    """Whether the preview is stored-enabled with an end still in the future.

    A stored-enabled preview whose window already lapsed counts as off.
    """
    return bool(
        invite.preview_enabled
        and invite.preview_ends_at is not None
        and invite.preview_ends_at > now
    )


def apply_preview_change(
    invite: Utub_Invite_Links, *, enabled: bool | None, window_days: int | None
) -> None:
    """Apply a manager's preview change to the row (no flush or commit).

    Every write of ``preview_ends_at`` is now + window days, so an enabled row always
    has an end. "Already on" means stored-enabled with an end still in the future.
    """
    now = utc_now()
    already_on = preview_is_on(invite, now=now)

    if window_days is not None:
        invite.preview_window_days = window_days

    if enabled is False:
        invite.preview_enabled = False
        invite.preview_ends_at = None
        return

    if enabled is True and not already_on:
        invite.preview_enabled = True
        invite.preview_ends_at = now + timedelta(days=invite.preview_window_days)
        return

    if window_days is not None and already_on:
        invite.preview_ends_at = now + timedelta(days=invite.preview_window_days)
