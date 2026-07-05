"""
Bearer-token (/api/v1) wrapper routes for Members.

Each route is an exact twin of its web counterpart (backend/members/routes.py),
with three changes:
  - Session decorator → api_ equivalent
  - ajax_required=False (no X-Requested-With sentinel)
  - tags=[OPEN_API.MOBILE_API] + 401/403 added to status_codes
"""

from backend.api_common.auth_decorators import (
    api_utub_creator_required,
    api_utub_membership_required,
)
from backend.api_common.parse_request import api_route
from backend.api_common.responses import FlaskResponse
from backend.api_v1.routes import api_v1
from backend.members.constants import UTubMembersErrorCodes
from backend.members.services.create_members import create_utub_member
from backend.members.services.delete_members import remove_member_or_self_from_utub
from backend.models.utubs import Utubs
from backend.schemas.errors import ErrorResponse
from backend.schemas.requests.members import AddMemberRequest
from backend.schemas.users import MemberModifiedResponseSchema
from backend.utils.strings.openapi_strs import OPEN_API
from backend.utils.strings.user_strs import MEMBER_FAILURE


@api_v1.route("/utubs/<int:utub_id>/members", methods=["POST"])
@api_utub_creator_required
@api_route(
    request_schema=AddMemberRequest,
    response_schema=MemberModifiedResponseSchema,
    error_message=MEMBER_FAILURE.UNABLE_TO_ADD_MEMBER,
    error_code=UTubMembersErrorCodes.INVALID_FORM_INPUT,
    ajax_required=False,
    tags=[OPEN_API.MOBILE_API],
    description="Add a member to a UTub",
    status_codes={
        200: MemberModifiedResponseSchema,
        400: ErrorResponse,
        401: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
)
def api_v1_create_member(
    utub_id: int,
    current_utub: Utubs,
    add_member_request: AddMemberRequest,
) -> FlaskResponse:
    """Add a user to a UTub by username. Caller must be UTub creator."""
    return create_utub_member(
        username=add_member_request.username, current_utub=current_utub
    )


@api_v1.route("/utubs/<int:utub_id>/members/<int:user_id>", methods=["DELETE"])
@api_utub_membership_required
@api_route(
    response_schema=MemberModifiedResponseSchema,
    ajax_required=False,
    tags=[OPEN_API.MOBILE_API],
    description="Remove a member from a UTub",
    status_codes={
        200: MemberModifiedResponseSchema,
        400: ErrorResponse,
        401: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
)
def api_v1_remove_member(
    utub_id: int,
    user_id: int,
    current_utub: Utubs,
) -> FlaskResponse:
    """Remove a member from a UTub.

    Creator can remove any member except themselves.
    Any member can remove themselves from a UTub they did not create.
    """
    return remove_member_or_self_from_utub(user_id, current_utub)
