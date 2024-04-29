from flask import (
    Blueprint,
    jsonify,
)
from flask_login import current_user

from src import db
from src.members.forms import (
    UTubNewMemberForm,
)
from src.models.users import Users
from src.models.utubs import Utubs
from src.models.utub_members import Utub_Members
from src.utils.strings.json_strs import STD_JSON_RESPONSE
from src.utils.strings.model_strs import MODELS
from src.utils.strings.user_strs import MEMBER_FAILURE, MEMBER_SUCCESS
from src.utils.email_validation import email_validation_required

members = Blueprint("members", __name__)

# Standard response for JSON messages
STD_JSON = STD_JSON_RESPONSE


@members.route("/utubs/<int:utub_id>/members/<int:user_id>", methods=["DELETE"])
@email_validation_required
def remove_member(utub_id: int, user_id: int):
    """
    Remove a user from a Utubs. The creator of the Utubs can remove anyone but themselves.
    Any user can remove themselves from a UTub they did not create.

    Args:
        utub_id (int): ID of the UTub to remove the user from
        user_id (int): ID of the User to remove from the UTub
    """
    current_utub: Utubs = Utubs.query.get_or_404(utub_id)

    if user_id == current_utub.utub_creator:
        # Creator tried to remove themselves, not allowed
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: MEMBER_FAILURE.CREATOR_CANNOT_REMOVE_THEMSELF,
                    STD_JSON.ERROR_CODE: 1,
                }
            ),
            400,
        )

    current_user_ids_in_utub = [member.user_id for member in current_utub.members]

    # User can't remove if current user is not in this current UTub's members
    # User can't remove if current user is not creator of UTub and requested user is not same as current user
    current_user_not_in_utub = current_user.id not in current_user_ids_in_utub
    member_trying_to_remove_another_member = (
        current_user.id != current_utub.created_by.id and user_id != current_user.id
    )

    if current_user_not_in_utub or member_trying_to_remove_another_member:
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: MEMBER_FAILURE.INVALID_PERMISSION_TO_REMOVE,
                    STD_JSON.ERROR_CODE: 2,
                }
            ),
            403,
        )

    if user_id not in current_user_ids_in_utub:
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: MEMBER_FAILURE.MEMBER_NOT_IN_UTUB,
                    STD_JSON.ERROR_CODE: 3,
                }
            ),
            404,
        )

    user_to_remove_in_utub: Utub_Members = Utub_Members.query.filter(
        Utub_Members.utub_id == utub_id, Utub_Members.user_id == user_id
    ).first_or_404()

    removed_user_username = user_to_remove_in_utub.to_user.username

    db.session.delete(user_to_remove_in_utub)
    db.session.commit()

    return (
        jsonify(
            {
                STD_JSON.STATUS: STD_JSON.SUCCESS,
                STD_JSON.MESSAGE: MEMBER_SUCCESS.MEMBER_REMOVED,
                MEMBER_SUCCESS.UTUB_ID: utub_id,
                MEMBER_SUCCESS.MEMBER: {
                    MODELS.ID: user_id,
                    MODELS.USERNAME: removed_user_username,
                },
            }
        ),
        200,
    )


@members.route("/utubs/<int:utub_id>/members", methods=["POST"])
@email_validation_required
def add_member(utub_id: int):
    """
    Creator of utub wants to add a user to the utub.

    Args:
        utub_id (int): The utub to which this user is being added
    """
    utub: Utubs = Utubs.query.get_or_404(utub_id)

    if utub.utub_creator != current_user.id:
        # User not authorized to add a member to this UTub
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: MEMBER_FAILURE.NOT_AUTHORIZED,
                    STD_JSON.ERROR_CODE: 1,
                }
            ),
            403,
        )

    utub_new_user_form = UTubNewMemberForm()

    if utub_new_user_form.validate_on_submit():
        username = utub_new_user_form.username.data

        new_user: Users = Users.query.filter_by(username=username).first_or_404()
        already_in_utub = new_user.id in (member.user_id for member in utub.members)

        if already_in_utub:
            # User already exists in UTub
            return (
                jsonify(
                    {
                        STD_JSON.STATUS: STD_JSON.FAILURE,
                        STD_JSON.MESSAGE: MEMBER_FAILURE.MEMBER_ALREADY_IN_UTUB,
                        STD_JSON.ERROR_CODE: 2,
                    }
                ),
                400,
            )

        new_user_to_utub = Utub_Members()
        new_user_to_utub.to_user = new_user
        utub.members.append(new_user_to_utub)
        db.session.commit()

        # Successfully added user to UTub
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.SUCCESS,
                    STD_JSON.MESSAGE: MEMBER_SUCCESS.MEMBER_ADDED,
                    MEMBER_SUCCESS.UTUB_ID: utub_id,
                    MEMBER_SUCCESS.MEMBER: {
                        MODELS.USERNAME: new_user.username,
                        MODELS.ID: new_user.id,
                    },
                }
            ),
            200,
        )

    if utub_new_user_form.errors is not None:
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: MEMBER_FAILURE.UNABLE_TO_ADD_MEMBER,
                    STD_JSON.ERROR_CODE: 3,
                    STD_JSON.ERRORS: utub_new_user_form.errors,
                }
            ),
            400,
        )

    return (
        jsonify(
            {
                STD_JSON.STATUS: STD_JSON.FAILURE,
                STD_JSON.MESSAGE: MEMBER_FAILURE.UNABLE_TO_ADD_MEMBER,
                STD_JSON.ERROR_CODE: 4,
            }
        ),
        404,
    )
