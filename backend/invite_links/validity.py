from __future__ import annotations

from backend.invite_links.constants import InviteState
from backend.models.utub_invite_links import Utub_Invite_Links
from backend.models.utub_members import Member_Role
from backend.utils.datetime_utils import utc_now
from backend.utubs.guards import get_fresh_membership


def _creator_is_manager(invite: Utub_Invite_Links) -> bool:
    """Whether the link's creator still exists, is a member and manages the UTub."""
    if invite.created_by is None:
        return False
    membership = get_fresh_membership(utub_id=invite.utub_id, user_id=invite.created_by)
    if membership is None:
        return False
    return membership.member_role in (Member_Role.CREATOR, Member_Role.CO_CREATOR)


def evaluate_invite(invite: Utub_Invite_Links) -> InviteState:
    """Report whether an invite link is live, or the first condition that kills it.

    Pure read: writes nothing, takes no lock and reads no ``current_user``. Fails
    closed: ``LIVE`` is returned only after every condition has positively passed.
    """
    if invite.revoked_at is not None:
        return InviteState.REVOKED
    if invite.expires_at <= utc_now():
        return InviteState.EXPIRED
    if invite.max_uses is not None and invite.use_count >= invite.max_uses:
        return InviteState.USED_UP
    if not _creator_is_manager(invite):
        return InviteState.CREATOR_NOT_MANAGER
    if invite.utub.is_trashed:
        return InviteState.UTUB_TRASHED
    if invite.utub.is_locked:
        return InviteState.UTUB_LOCKED
    return InviteState.LIVE


def is_invite_live(state: InviteState) -> bool:
    """Only ``InviteState.LIVE`` is live; every other state, including future ones, denies."""
    return state is InviteState.LIVE
