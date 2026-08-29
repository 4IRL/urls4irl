from backend import db
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.app_logger import safe_add_many_logs
from backend.extensions.metrics.writer import record_event
from backend.members.constants import UTubMembersErrorCodes
from backend.metrics.events import EventName
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utubs import Utubs
from backend.schemas.errors import build_message_error_response
from backend.schemas.users import OwnershipTransferredResponseSchema, UtubMemberSchema
from backend.utils.strings.user_strs import MEMBER_FAILURE, MEMBER_SUCCESS
from backend.utubs.guards import reject_if_utub_locked


def transfer_ownership(*, new_owner_id: int, current_utub: Utubs) -> FlaskResponse:
    """Transfer a UTub's ownership from its creator to a chosen member.

    Owner-only (enforced by the route decorator). Reassigns
    ``Utubs.utub_creator`` to ``new_owner_id``, promotes that member to
    ``Member_Role.CREATOR``, and demotes the outgoing owner to
    ``Member_Role.CO_CREATOR`` — the outgoing owner stays in the UTub (DD-3).

    The mutations commit as one atomic unit, and in a mandatory order:
    ``utub_creator`` is reassigned to the new owner BEFORE the old owner is
    demoted, so at no intermediate step is the row being role-changed still the
    literal owner. This keeps every ownership-keyed integrity guard (e.g.
    ``_someone_removing_the_owner``) pointed at the reassigned creator.

    Args:
        new_owner_id (int): The ID of the member to promote to UTub owner
        current_utub (Utubs): The UTub whose ownership is being transferred

    Returns:
        FlaskResponse: JSON response and HTTP status code
            - 200 (on a successful transfer)
            - 400 (the target member is already the UTub owner)
            - 403 (the UTub is locked)
            - 404 (the target user is not a member of the UTub)
    """
    utub_locked_error: FlaskResponse | None = reject_if_utub_locked(
        current_utub, error_code=UTubMembersErrorCodes.UTUB_IS_LOCKED
    )
    if utub_locked_error is not None:
        return utub_locked_error

    new_owner_membership: Utub_Members | None = Utub_Members.query.get(
        (current_utub.id, new_owner_id)
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
    outgoing_owner_membership: Utub_Members | None = Utub_Members.query.get(
        (current_utub.id, outgoing_owner_id)
    )

    # Mandatory ordering: reassign the creator BEFORE demoting the old owner so
    # no intermediate state leaves the row being role-changed as the literal
    # owner (see the docstring's atomicity note).
    current_utub.utub_creator = new_owner_id
    new_owner_membership.member_role = Member_Role.CREATOR
    outgoing_owner_membership.member_role = Member_Role.CO_CREATOR
    current_utub.set_last_updated()
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

    return APIResponse(
        message=MEMBER_SUCCESS.OWNERSHIP_TRANSFERRED,
        data=OwnershipTransferredResponseSchema(
            utub_id=current_utub.id,
            new_owner=UtubMemberSchema(
                id=new_owner_membership.to_user.id,
                username=new_owner_membership.to_user.username,
                member_role=new_owner_membership.member_role.value,
            ),
            previous_owner=UtubMemberSchema(
                id=outgoing_owner_membership.to_user.id,
                username=outgoing_owner_membership.to_user.username,
                member_role=outgoing_owner_membership.member_role.value,
            ),
        ),
    ).to_response()
