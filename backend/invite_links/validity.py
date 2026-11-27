from __future__ import annotations

from backend.invite_links.constants import InviteLinkStatus, InviteState
from backend.invite_links.permissions import can_create_invite_links
from backend.models.utub_invite_links import Utub_Invite_Links
from backend.models.utub_members import Member_Role
from backend.utils.datetime_utils import utc_now
from backend.utubs.guards import get_fresh_membership


def creator_role(invite: Utub_Invite_Links) -> Member_Role | None:
    """The link creator's current role, or None if NULL creator or not a member."""
    if invite.created_by is None:
        return None
    membership = get_fresh_membership(utub_id=invite.utub_id, user_id=invite.created_by)
    if membership is None:
        return None
    return membership.member_role


def evaluate_invite(invite: Utub_Invite_Links) -> InviteState:
    """Report whether an invite link is live, or the first condition that kills it.

    Check order: REVOKED, EXPIRED, USED_UP, CREATOR_NOT_MANAGER (creator gone or
    no longer a manager), CREATOR_NOT_ALLOWED (creator a manager but the UTub's
    creators setting no longer lets their role create links), UTUB_TRASHED,
    UTUB_LOCKED, LIVE.

    Pure read: writes nothing, takes no lock and reads no ``current_user``. Fails
    closed: ``LIVE`` is returned only after every condition has positively passed.
    """
    if invite.revoked_at is not None:
        return InviteState.REVOKED
    if invite.expires_at <= utc_now():
        return InviteState.EXPIRED
    if invite.max_uses is not None and invite.use_count >= invite.max_uses:
        return InviteState.USED_UP
    role = creator_role(invite)
    if role not in (Member_Role.CREATOR, Member_Role.CO_CREATOR):
        return InviteState.CREATOR_NOT_MANAGER
    if not can_create_invite_links(utub=invite.utub, role=role):
        return InviteState.CREATOR_NOT_ALLOWED
    if invite.utub.is_trashed:
        return InviteState.UTUB_TRASHED
    if invite.utub.is_locked:
        return InviteState.UTUB_LOCKED
    return InviteState.LIVE


_STATE_TO_LINK_STATUS: dict[InviteState, InviteLinkStatus] = {
    InviteState.LIVE: InviteLinkStatus.LIVE,
    InviteState.UTUB_LOCKED: InviteLinkStatus.LIVE,
    InviteState.EXPIRED: InviteLinkStatus.EXPIRED,
    InviteState.USED_UP: InviteLinkStatus.USED_UP,
    InviteState.CREATOR_NOT_MANAGER: InviteLinkStatus.CREATOR_DEMOTED,
    InviteState.CREATOR_NOT_ALLOWED: InviteLinkStatus.CREATOR_NOT_ALLOWED,
}


def invite_state_to_link_status(state: InviteState) -> InviteLinkStatus:
    """Map an evaluated state to the manager-facing status; fails closed.

    ``REVOKED`` and ``UTUB_TRASHED`` (and any future state) raise rather than
    ever mapping to ``live``.
    """
    try:
        return _STATE_TO_LINK_STATUS[state]
    except KeyError:
        raise ValueError(
            f"InviteState {state!r} has no manager-facing link status"
        ) from None


def is_invite_live(state: InviteState) -> bool:
    """Only ``InviteState.LIVE`` is live; every other state, including future ones, denies."""
    return state is InviteState.LIVE
