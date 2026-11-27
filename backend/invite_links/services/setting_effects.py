from __future__ import annotations

from dataclasses import dataclass

from backend.invite_links.constants import InviteState
from backend.invite_links.guards import lock_current_invite_for_update
from backend.invite_links.permissions import (
    can_create_invite_links,
    co_owner_preview_from_raw_settings,
    creator_may_create,
    creators_from_raw_settings,
)
from backend.invite_links.preview import (
    apply_preview_change,
    compute_effective_preview,
    preview_is_on,
)
from backend.invite_links.services.manage_invite_link import revoke_invite_row
from backend.invite_links.validity import creator_role, evaluate_invite
from backend.models.utub_invite_links import Utub_Invite_Links
from backend.models.utubs import Utubs
from backend.utils.datetime_utils import utc_now


@dataclass(frozen=True)
class InviteSettingEffects:
    """What a settings write did to the UTub's invite link.

    ``link_revoked`` is True only when a link that was live before the write was
    revoked by it. ``preview_ended`` is True only when a preview that was on
    (effectively) before the write was ended by it.
    """

    link_revoked: bool = False
    preview_ended: bool = False


def apply_invite_setting_effects(
    utub: Utubs, *, before: dict | None
) -> InviteSettingEffects:
    """Revoke a now-disallowed link and end a now-disallowed preview.

    Call after ``utub.settings`` holds the NEW overrides and before the service's
    single commit; the caller must hold the ``Utubs`` lock. Runs only when the
    effective creators rule or the co-owner preview flag differs between ``before``
    and the new settings, then takes the invite row lock (Utubs, then invite). Never
    commits and never emits metrics: the caller emits ``INVITE_LINK_REVOKED``
    (``reason="setting_change"``) after its commit when ``link_revoked``.

    Args:
        utub (Utubs): The UTub whose settings were just reassigned.
        before (dict | None): The raw stored settings before the write.

    Returns:
        InviteSettingEffects: Whether a live link was revoked / a preview ended.
    """
    after = utub.settings
    creators_before = creators_from_raw_settings(before)
    creators_changed = creators_before != creators_from_raw_settings(after)
    preview_before = co_owner_preview_from_raw_settings(before)
    preview_after = co_owner_preview_from_raw_settings(after)
    preview_tightened = preview_before and not preview_after
    preview_changed = preview_before != preview_after
    if not (creators_changed or preview_changed):
        return InviteSettingEffects()

    invite: Utub_Invite_Links | None = lock_current_invite_for_update(utub_id=utub.id)
    if invite is None:
        return InviteSettingEffects()

    role = creator_role(invite)
    if not can_create_invite_links(utub=utub, role=role):
        was_live = evaluate_invite(
            invite
        ) == InviteState.CREATOR_NOT_ALLOWED and creator_may_create(
            creators=creators_before, role=role
        )
        revoke_invite_row(invite)
        return InviteSettingEffects(link_revoked=was_live)

    if preview_tightened and preview_is_on(invite, now=utc_now()):
        was_on = compute_effective_preview(
            invite, state=evaluate_invite(invite)
        ).enabled
        apply_preview_change(invite, enabled=False, window_days=None)
        return InviteSettingEffects(preview_ended=was_on)

    return InviteSettingEffects()
