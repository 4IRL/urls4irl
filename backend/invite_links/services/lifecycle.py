from __future__ import annotations

from backend.invite_links.guards import lock_current_invite_for_update
from backend.invite_links.services.manage_invite_link import revoke_invite_row
from backend.models.utub_invite_links import Utub_Invite_Links


def revoke_invite_link_created_by(*, utub_id: int, creator_id: int) -> bool:
    """Revoke the UTub's unrevoked invite link if ``creator_id`` created it.

    The caller must already hold the ``Utubs`` lock (``lock_utub_for_update``). Takes
    the invite row lock, then revokes and flushes. Never commits and never emits
    metrics: the caller emits ``INVITE_LINK_REVOKED`` (``reason="role_change"``) after
    its own commit. Applies whatever the creator's current role is, since a demoted
    creator can still own an unrevoked row. A row with no creator (``created_by`` NULL)
    is never touched.

    Args:
        utub_id (int): ID of the UTub.
        creator_id (int): ID of the user being removed, leaving or demoted.

    Returns:
        bool: True if a row was revoked, False otherwise.
    """
    invite: Utub_Invite_Links | None = lock_current_invite_for_update(utub_id=utub_id)
    if invite is None or invite.created_by != creator_id:
        return False
    revoke_invite_row(invite)
    return True
