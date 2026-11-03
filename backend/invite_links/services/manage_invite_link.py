from __future__ import annotations

from backend.invite_links.validity import evaluate_invite, invite_state_to_link_status
from backend.models.utub_invite_links import Utub_Invite_Links
from backend.models.utubs import Utubs
from backend.schemas.invite_links import InviteLinkResponseSchema, InviteLinkSchema
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON


def build_invite_link_schema(invite: Utub_Invite_Links) -> InviteLinkSchema:
    """Build the manager-facing schema for an unrevoked invite link.

    The one builder every invite link response goes through. ``status`` comes from
    ``evaluate_invite`` (first-match order) mapped to the manager-facing status.
    Pure read: writes nothing and takes no lock.
    """
    return InviteLinkSchema(
        token=invite.token,
        status=invite_state_to_link_status(evaluate_invite(invite)),
        expires_at=invite.expires_at,
        max_uses=invite.max_uses,
        use_count=invite.use_count,
        created_at=invite.created_at,
        creator_username=None if invite.creator is None else invite.creator.username,
    )


def get_unrevoked_invite(*, utub_id: int) -> Utub_Invite_Links | None:
    """Read (without locking) the UTub's unrevoked invite link, if any."""
    return Utub_Invite_Links.query.filter(
        Utub_Invite_Links.utub_id == utub_id,
        Utub_Invite_Links.revoked_at.is_(None),
    ).one_or_none()


def read_invite_link(current_utub: Utubs) -> InviteLinkResponseSchema:
    """Return the UTub's current invite link, or a null link when there is none."""
    invite = get_unrevoked_invite(utub_id=current_utub.id)
    return InviteLinkResponseSchema(
        status=STD_JSON.SUCCESS,
        invite_link=None if invite is None else build_invite_link_schema(invite),
    )
