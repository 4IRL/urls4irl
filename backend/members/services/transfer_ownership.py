from backend import db
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.app_logger import safe_add_many_logs
from backend.extensions.metrics.writer import record_event
from backend.invite_links.constants import InviteState
from backend.invite_links.guards import lock_current_invite_for_update
from backend.invite_links.permissions import can_create_invite_links
from backend.invite_links.services.lifecycle import (
    emit_role_change_revokes,
    revoke_invite_link_created_by,
)
from backend.invite_links.validity import evaluate_invite
from backend.members.constants import UTubMembersErrorCodes
from backend.metrics.events import EventName
from backend.models.utub_invite_links import Utub_Invite_Links
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utubs import Utubs
from backend.schemas.errors import build_message_error_response
from backend.schemas.users import OwnershipTransferredResponseSchema, UtubMemberSchema
from backend.utils.strings.user_strs import MEMBER_FAILURE, MEMBER_SUCCESS
from backend.utubs.guards import UtubAccess, get_fresh_membership, lock_and_reauthorize


def transfer_ownership(*, new_owner_id: int, current_utub: Utubs) -> FlaskResponse:
    """Transfer a UTub's ownership from its creator to a chosen member.

    Owner-only (enforced by the route decorator). Reassigns
    ``Utubs.utub_creator`` to ``new_owner_id``, promotes that member to
    ``Member_Role.CREATOR``, and demotes the outgoing owner to
    ``Member_Role.CO_CREATOR`` — the outgoing owner stays in the UTub (DD-3).

    The mutations commit as one atomic unit, and in a mandatory order:
    ``utub_creator`` is reassigned to the new owner, THEN the old owner is
    demoted and flushed, THEN the new owner is promoted. At no intermediate step
    is the row being role-changed still the literal owner (keeping every
    ownership-keyed guard such as ``_someone_removing_the_owner`` pointed at the
    reassigned creator), and the flush guarantees the demotion reaches the DB
    before the promotion, since the single-CREATOR unique index is checked per
    statement.

    When the UTub's invite-link creators rule no longer lets a co-owner create
    links (``owner_only``), the outgoing owner's unrevoked link is revoked in the
    same transaction (``role_change`` metric after the commit), so the new owner
    can create a fresh link at once. Under the default the link stays live.

    Args:
        new_owner_id (int): The ID of the member to promote to UTub owner
        current_utub (Utubs): The UTub whose ownership is being transferred

    Returns:
        FlaskResponse: JSON response and HTTP status code
            - 200 (on a successful transfer)
            - 400 (the target member is already the UTub owner)
            - 403 (the caller is no longer the owner once the UTub row is locked,
              or the UTub is locked)
            - 404 (the target user is not a member of the UTub, or the caller's
              membership or the UTub is gone once the row is locked)
    """
    auth_error: FlaskResponse | None = lock_and_reauthorize(
        current_utub,
        required_access=UtubAccess.OWNER,
        error_code=UTubMembersErrorCodes.UTUB_IS_LOCKED,
    )
    if auth_error is not None:
        return auth_error

    new_owner_membership: Utub_Members | None = get_fresh_membership(
        utub_id=current_utub.id, user_id=new_owner_id
    )
    if new_owner_membership is None:
        return build_message_error_response(
            message=MEMBER_FAILURE.MEMBER_NOT_IN_UTUB,
            error_code=UTubMembersErrorCodes.TARGET_NOT_A_MEMBER,
            status_code=404,
        )

    outgoing_owner_id: int = current_utub.utub_creator
    if new_owner_id == outgoing_owner_id:
        return build_message_error_response(
            message=MEMBER_FAILURE.TARGET_ALREADY_OWNER,
            error_code=UTubMembersErrorCodes.TARGET_ALREADY_OWNER,
            status_code=400,
        )

    # The literal owner is always a member (the utub_owner_required guard's
    # membership check resolves it), so this lookup never returns None.
    outgoing_owner_membership: Utub_Members | None = get_fresh_membership(
        utub_id=current_utub.id, user_id=outgoing_owner_id
    )

    # Mandatory ordering: reassign the creator, demote and FLUSH the old owner,
    # then promote the new one. The single-CREATOR unique index is checked per
    # statement and the unit of work orders UPDATEs by primary key, so without
    # the flush a lower-id promotion would reach the DB before the demotion.
    # Judge liveness before the demotion: only a link that was live counts toward
    # the role_change metric (an expired or used-up row is still revoked, silently).
    current_invite: Utub_Invite_Links | None = lock_current_invite_for_update(
        utub_id=current_utub.id
    )
    link_was_live: bool = (
        current_invite is not None
        and current_invite.created_by == outgoing_owner_id
        and evaluate_invite(current_invite) == InviteState.LIVE
    )

    current_utub.utub_creator = new_owner_id
    outgoing_owner_membership.member_role = Member_Role.CO_CREATOR
    db.session.flush()
    new_owner_membership.member_role = Member_Role.CREATOR
    current_utub.set_last_updated()
    # The outgoing owner is now a co-owner: under owner_only their link is dead,
    # so revoke it in this transaction (the Utubs lock is held).
    revoked_invite = False
    if not can_create_invite_links(utub=current_utub, role=Member_Role.CO_CREATOR):
        revoked_invite = (
            revoke_invite_link_created_by(
                utub_id=current_utub.id, creator_id=outgoing_owner_id
            )
            and link_was_live
        )
    db.session.commit()

    safe_add_many_logs(
        [
            "Transferred UTub ownership",
            f"UTub.id={current_utub.id}",
            f"new_owner={new_owner_id}",
            f"previous_owner={outgoing_owner_id}",
        ]
    )
    record_event(EventName.OWNERSHIP_TRANSFERRED)
    emit_role_change_revokes(int(revoked_invite))

    return APIResponse(
        message=MEMBER_SUCCESS.OWNERSHIP_TRANSFERRED,
        data=OwnershipTransferredResponseSchema(
            utub_id=current_utub.id,
            new_owner=UtubMemberSchema(
                id=new_owner_membership.to_user.id,
                username=new_owner_membership.to_user.username,
                member_role=new_owner_membership.member_role.value,
                joined_at=new_owner_membership.joined_at,
            ),
            previous_owner=UtubMemberSchema(
                id=outgoing_owner_membership.to_user.id,
                username=outgoing_owner_membership.to_user.username,
                member_role=outgoing_owner_membership.member_role.value,
                joined_at=outgoing_owner_membership.joined_at,
            ),
        ),
    ).to_response()
