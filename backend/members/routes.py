from flask import Blueprint

from backend.api_common.auth_decorators import (
    utub_creator_required,
    utub_membership_required,
)
from backend.api_common.parse_request import parse_json_body
from backend.api_common.responses import FlaskResponse
from backend.members.constants import UTubMembersErrorCodes
from backend.members.services.create_members import create_utub_member
from backend.members.services.delete_members import remove_member_or_self_from_utub
from backend.models.utubs import Utubs
from backend.schemas.requests.members import AddMemberRequest
from backend.utils.strings.user_strs import MEMBER_FAILURE

members = Blueprint("members", __name__)


@members.route("/utubs/<int:utub_id>/members/<int:user_id>", methods=["DELETE"])
@utub_membership_required
def remove_member(utub_id: int, user_id: int, current_utub: Utubs) -> FlaskResponse:
    """
    Remove a user from a Utubs. The creator of the Utubs can remove anyone but themselves.
    Any user can remove themselves from a UTub they did not create.

    Args:
        utub_id (int): ID of the UTub to remove the user from
        user_id (int): ID of the User to remove from the UTub
    """
    return remove_member_or_self_from_utub(user_id, current_utub)


@members.route("/utubs/<int:utub_id>/members", methods=["POST"])
@utub_creator_required
@parse_json_body(
    AddMemberRequest,
    message=MEMBER_FAILURE.UNABLE_TO_ADD_MEMBER,
    error_code=UTubMembersErrorCodes.INVALID_FORM_INPUT,
)
def create_member(
    utub_id: int, current_utub: Utubs, validated_request: AddMemberRequest
) -> FlaskResponse:
    """
    Creator of utub wants to add a user to the utub.

    Args:
        utub_id (int): The utub to which this user is being added
    """
    return create_utub_member(
        username=validated_request.username, current_utub=current_utub
    )
