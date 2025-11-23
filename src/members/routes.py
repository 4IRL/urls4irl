from flask import (
    Blueprint,
    Response,
)

from src.members.forms import (
    UTubNewMemberForm,
)
from src.members.services.create_members import (
    create_utub_member,
    handle_invalid_form_on_create_utub_member,
)
from src.members.services.delete_members import remove_member_or_self_from_utub
from src.models.utubs import Utubs
from src.utils.auth_decorators import (
    utub_creator_required,
    utub_membership_required,
)
from src.utils.strings.json_strs import STD_JSON_RESPONSE

members = Blueprint("members", __name__)

# Standard response for JSON messages
STD_JSON = STD_JSON_RESPONSE


@members.route("/utubs/<int:utub_id>/members/<int:user_id>", methods=["DELETE"])
@utub_membership_required
def remove_member(
    utub_id: int, user_id: int, current_utub: Utubs
) -> tuple[Response, int]:
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
def create_member(utub_id: int, current_utub: Utubs) -> tuple[Response, int]:
    """
    Creator of utub wants to add a user to the utub.

    Args:
        utub_id (int): The utub to which this user is being added
    """
    member_form = UTubNewMemberForm()

    if not member_form.validate_on_submit():
        return handle_invalid_form_on_create_utub_member(member_form)

    return create_utub_member(member_form=member_form, current_utub=current_utub)
