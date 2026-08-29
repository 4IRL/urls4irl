from backend import db
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.app_logger import safe_add_many_logs
from backend.extensions.metrics.writer import record_event
from backend.members.constants import MemberRoleTarget, UTubMembersErrorCodes
from backend.metrics.events import EventName
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utubs import Utubs
from backend.schemas.errors import build_message_error_response
from backend.schemas.users import MemberModifiedResponseSchema, UserSchema
from backend.utils.strings.user_strs import MEMBER_FAILURE, MEMBER_SUCCESS
from backend.utubs.guards import reject_if_utub_locked


def modify_member_role(
    *,
    user_id_to_modify: int,
    target_role: MemberRoleTarget,
    current_utub: Utubs,
) -> FlaskResponse:
    """Grant or revoke the co-owner (CO_CREATOR) role for a UTub member.

    Owner-only (enforced by the route decorator). ``target_role`` carries the
    intent: ``cocreator`` promotes a plain member to co-owner, ``member``
    revokes it. A request targeting a member already at the requested role is a
    no-op — it returns success without writing or emitting a metric, so
    redundant events are never recorded.

    Args:
        user_id_to_modify (int): The ID of the member whose role is changing
        target_role (MemberRoleTarget): The role to assign to the member
        current_utub (Utubs): The UTub the member belongs to

    Returns:
        FlaskResponse: JSON response and HTTP status code
            - 200 (on successful role change or no-op)
            - 400 (targeting the UTub's literal owner)
            - 403 (the UTub is locked)
            - 404 (the target user is not a member of the UTub)
    """
    utub_locked_error: FlaskResponse | None = reject_if_utub_locked(
        current_utub, error_code=UTubMembersErrorCodes.UTUB_IS_LOCKED
    )
    if utub_locked_error is not None:
        return utub_locked_error

    member: Utub_Members | None = Utub_Members.query.get(
        (current_utub.id, user_id_to_modify)
    )
    if member is None:
        return build_message_error_response(
            message=MEMBER_FAILURE.MEMBER_NOT_IN_UTUB,
            status_code=404,
        )

    if user_id_to_modify == current_utub.utub_creator:
        return build_message_error_response(
            message=MEMBER_FAILURE.CANNOT_MODIFY_OWNER_ROLE,
            error_code=UTubMembersErrorCodes.CANNOT_MODIFY_OWNER,
            status_code=400,
        )

    # Relies on the MemberRoleTarget.value == Member_Role.value invariant: the
    # two enums share identical wire values, so constructing directly is total.
    new_member_role: Member_Role = Member_Role(target_role.value)

    if member.member_role == new_member_role:
        # No-op: the member already holds the requested role. Return success
        # without a write or a metric emit to avoid redundant events.
        return _build_success_response(member=member, current_utub=current_utub)

    member.member_role = new_member_role
    current_utub.set_last_updated()
    db.session.commit()

    safe_add_many_logs(
        [
            "Modified member role in UTub",
            f"UTub.id={current_utub.id}",
            f"User={user_id_to_modify}",
            f"new_role={target_role.value}",
        ]
    )
    record_event(
        EventName.MEMBER_ROLE_CHANGED, dimensions={"new_role": target_role.value}
    )

    return _build_success_response(member=member, current_utub=current_utub)


def _build_success_response(member: Utub_Members, current_utub: Utubs) -> FlaskResponse:
    """Build the 200 role-modified envelope for a member.

    Args:
        member (Utub_Members): The membership row that was (or would be) modified
        current_utub (Utubs): The UTub the member belongs to

    Returns:
        FlaskResponse: JSON success response and HTTP status code 200
    """
    return APIResponse(
        message=MEMBER_SUCCESS.MEMBER_ROLE_MODIFIED,
        data=MemberModifiedResponseSchema(
            utub_id=current_utub.id,
            member=UserSchema(id=member.to_user.id, username=member.to_user.username),
        ),
    ).to_response()
