from flask import Blueprint
from flask_login import current_user

from backend import limiter
from backend.api_common.auth_decorators import (
    utub_manager_required,
    utub_membership_required,
    utub_owner_required,
)
from backend.api_common.parse_request import api_route
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.members.constants import MEMBER_ADD_RATE_LIMIT, UTubMembersErrorCodes
from backend.members.services.co_member_search import get_co_member_candidates
from backend.members.services.create_members import create_utub_member
from backend.members.services.delete_members import remove_member_or_self_from_utub
from backend.members.services.modify_member_role import (
    modify_member_role as modify_member_role_service,
)
from backend.members.services.transfer_ownership import transfer_ownership
from backend.models.utubs import Utubs
from backend.schemas.errors import ErrorResponse
from backend.schemas.requests.members import (
    AddMemberRequest,
    ModifyMemberRoleRequest,
    TransferOwnershipRequest,
)
from backend.schemas.users import (
    CoMemberListSchema,
    MemberModifiedResponseSchema,
    OwnershipTransferredResponseSchema,
)
from backend.utils.strings.openapi_strs import OPEN_API
from backend.utils.strings.user_strs import MEMBER_FAILURE

members = Blueprint("members", __name__)


@members.route("/utubs/<int:utub_id>/members/<int:user_id>", methods=["DELETE"])
@utub_membership_required
@api_route(
    response_schema=MemberModifiedResponseSchema,
    tags=[OPEN_API.MEMBERS],
    description="Remove a member from a UTub",
    status_codes={
        200: MemberModifiedResponseSchema,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
)
def remove_member(utub_id: int, user_id: int, current_utub: Utubs) -> FlaskResponse:
    """
    Remove a user from a Utubs. The creator of the Utubs can remove anyone but themselves.
    Any user can remove themselves from a UTub they did not create.

    Args:
        utub_id (int): ID of the UTub to remove the user from
        user_id (int): ID of the User to remove from the UTub
    """
    return remove_member_or_self_from_utub(user_id, current_utub)


@members.route("/utubs/<int:utub_id>/members/<int:user_id>", methods=["PATCH"])
@utub_owner_required
@api_route(
    request_schema=ModifyMemberRoleRequest,
    response_schema=MemberModifiedResponseSchema,
    error_message=MEMBER_FAILURE.UNABLE_TO_MODIFY_MEMBER_ROLE,
    error_code=UTubMembersErrorCodes.INVALID_FORM_INPUT,
    tags=[OPEN_API.MEMBERS],
    description="Grant or revoke the co-owner role for a UTub member (owner only)",
    status_codes={
        200: MemberModifiedResponseSchema,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
)
def modify_member_role(
    utub_id: int,
    user_id: int,
    current_utub: Utubs,
    modify_member_role_request: ModifyMemberRoleRequest,
) -> FlaskResponse:
    """
    UTub owner grants or revokes the co-owner role for a member.

    Args:
        utub_id (int): The UTub whose member is being modified
        user_id (int): The member whose role is changing
    """
    return modify_member_role_service(
        user_id_to_modify=user_id,
        target_role=modify_member_role_request.member_role,
        current_utub=current_utub,
    )


@members.route("/utubs/<int:utub_id>/owner", methods=["PATCH"])
@utub_owner_required
@api_route(
    request_schema=TransferOwnershipRequest,
    response_schema=OwnershipTransferredResponseSchema,
    error_message=MEMBER_FAILURE.UNABLE_TO_TRANSFER_OWNERSHIP,
    error_code=UTubMembersErrorCodes.INVALID_FORM_INPUT,
    tags=[OPEN_API.MEMBERS],
    description="Transfer UTub ownership to a chosen member (owner only)",
    status_codes={
        200: OwnershipTransferredResponseSchema,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
)
def transfer_utub_ownership(
    utub_id: int,
    current_utub: Utubs,
    transfer_ownership_request: TransferOwnershipRequest,
) -> FlaskResponse:
    """
    UTub owner transfers ownership to a chosen member: the target is promoted to
    creator and the outgoing owner is demoted to co-owner (kept in the UTub).

    Args:
        utub_id (int): The UTub whose ownership is being transferred
    """
    return transfer_ownership(
        new_owner_id=transfer_ownership_request.new_owner_id,
        current_utub=current_utub,
    )


@members.route("/utubs/<int:utub_id>/members", methods=["POST"])
@utub_manager_required
@api_route(
    request_schema=AddMemberRequest,
    response_schema=MemberModifiedResponseSchema,
    error_message=MEMBER_FAILURE.UNABLE_TO_ADD_MEMBER,
    error_code=UTubMembersErrorCodes.INVALID_FORM_INPUT,
    tags=[OPEN_API.MEMBERS],
    description="Add a member to a UTub",
    status_codes={
        200: MemberModifiedResponseSchema,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
        429: ErrorResponse,
    },
)
@limiter.limit(MEMBER_ADD_RATE_LIMIT, methods=["POST"])
def create_member(
    utub_id: int, current_utub: Utubs, add_member_request: AddMemberRequest
) -> FlaskResponse:
    """
    Creator of utub wants to add a user to the utub.

    Args:
        utub_id (int): The utub to which this user is being added
    """
    return create_utub_member(
        username=add_member_request.username,
        current_utub=current_utub,
        source=add_member_request.source,
    )


@members.route("/utubs/<int:utub_id>/co-members", methods=["GET"])
@utub_manager_required
@api_route(
    response_schema=CoMemberListSchema,
    ajax_required=True,
    tags=[OPEN_API.MEMBERS],
    description="Get co-member add candidates for a UTub (creator only)",
    status_codes={
        200: CoMemberListSchema,
        403: ErrorResponse,
        404: ErrorResponse,
    },
)
def get_co_member_candidates_route(utub_id: int, current_utub: Utubs) -> FlaskResponse:
    """
    Return the co-member add candidates for the given UTub. Only the creator,
    who is the only member able to open the add-member UI, can load candidates.

    Args:
        utub_id (int): The UTub to load co-member candidates for
    """
    return APIResponse(
        data=get_co_member_candidates(current_user.id, current_utub),
        status_code=200,
    ).to_response()
