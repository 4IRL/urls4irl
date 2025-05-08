from typing import Optional
from flask import (
    Blueprint,
    jsonify,
)
from flask_login import current_user

from src import db
from src.app_logger import (
    critical_log,
    safe_add_many_logs,
    turn_form_into_str_for_log,
    warning_log,
)
from src.members.forms import (
    UTubNewMemberForm,
)
from src.models.users import Users
from src.models.utubs import Utubs
from src.models.utub_members import Member_Role, Utub_Members
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
        warning_log(f"User={current_user.id} | UTub creator tried to remove themselves")
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

    # User can't remove if current user is not in this current UTub's members
    # User can't remove if current user is not creator of UTub and requested user is not same as current user
    current_utub_member: Utub_Members = Utub_Members.query.get(
        (utub_id, current_user.id)
    )
    current_utub_member_not_in_utub = current_utub_member is None
    current_utub_member_not_creator_and_removing_another_member = (
        current_utub_member is not None
        and (
            current_user.id != user_id
            and current_utub_member.member_role == Member_Role.MEMBER
        )
    )

    if (
        current_utub_member_not_in_utub
        or current_utub_member_not_creator_and_removing_another_member
    ):
        if current_utub_member_not_in_utub:
            critical_log(
                f"User={current_user.id} tried removing themselves from UTub.id={utub_id} they aren't in"
            )

        if current_utub_member_not_creator_and_removing_another_member:
            critical_log(
                f"User={current_user.id} tried removing another member from UTub.id={utub_id}"
            )

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

    user_to_remove_in_utub: Optional[Utub_Members] = Utub_Members.query.get(
        (utub_id, user_id)
    )

    if user_to_remove_in_utub is None:
        warning_log(
            f"User={current_user.id} tried removing a member that isn't in this UTub"
        )
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

    removed_user_username: str = user_to_remove_in_utub.to_user.username

    db.session.delete(user_to_remove_in_utub)
    current_utub.set_last_updated()
    db.session.commit()

    safe_add_many_logs(
        [
            "Removed member from UTub",
            f"UTub.id={utub_id}",
            f"User={user_id}",
        ]
    )
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
def create_member(utub_id: int):
    """
    Creator of utub wants to add a user to the utub.

    Args:
        utub_id (int): The utub to which this user is being added
    """
    utub: Utubs = Utubs.query.get_or_404(utub_id)

    if utub.utub_creator != current_user.id:
        # User not authorized to add a member to this UTub
        critical_log(
            f"User={current_user.id} tried adding a member to UTub.id={utub_id}"
        )
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

        new_user: Users = Users.query.filter(Users.username == username).first_or_404()
        already_in_utub = Utub_Members.query.get((utub_id, new_user.id)) is not None

        if already_in_utub:
            # User already exists in UTub
            warning_log(
                f"User={current_user.id} tried adding a User={new_user.id} already in this UTub"
            )
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
        new_user_to_utub.utub_id = utub_id
        new_user_to_utub.user_id = new_user.id
        db.session.add(new_user_to_utub)
        utub.set_last_updated()
        db.session.commit()

        # Successfully added user to UTub
        safe_add_many_logs(
            ["Added member to UTub", f"UTub.id={utub_id}", f"Added User={new_user.id}"]
        )

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
        warning_log(
            f"User={current_user.id} | Invalid form: {turn_form_into_str_for_log(utub_new_user_form.errors)}"
        )
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

    critical_log(f"User={current_user.id} failed to add member to UTub")
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
