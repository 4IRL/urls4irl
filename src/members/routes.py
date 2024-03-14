from flask import (
    Blueprint,
    jsonify,
)
from flask_login import current_user

from src import db
from src.models import Utub, Utub_Users, User
from src.users.forms import (
    UTubNewUserForm,
)
from src.utils.strings.json_strs import STD_JSON_RESPONSE
from src.utils.strings.user_strs import USER_FAILURE, USER_SUCCESS
from src.utils.email_validation import email_validation_required

members = Blueprint("members", __name__)

# Standard response for JSON messages
STD_JSON = STD_JSON_RESPONSE

@members.route("/user/remove/<int:utub_id>/<int:user_id>", methods=["POST"])
@email_validation_required
def delete_member(utub_id: int, user_id: int):
    """
    Delete a user from a Utub. The creator of the Utub can delete anyone but themselves.
    Any user can remove themselves from a UTub they did not create.

    Args:
        utub_id (int): ID of the UTub to remove the user from
        user_id (int): ID of the User to remove from the UTub
    """
    current_utub = Utub.query.get_or_404(utub_id)

    if user_id == current_utub.created_by.id:
        # Creator tried to delete themselves, not allowed
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: USER_FAILURE.CREATOR_CANNOT_REMOVE_THEMSELF,
                    USER_FAILURE.EMAIL_VALIDATED: str(True),
                    STD_JSON.ERROR_CODE: 1,
                }
            ),
            400,
        )

    current_user_ids_in_utub = [member.user_id for member in current_utub.members]
    current_user_id = current_user.id

    # User can't remove if current user is not in this current UTub's members
    # User can't remove if current user is not creator of UTub and requested user is not same as current user
    current_user_not_in_utub = current_user_id not in current_user_ids_in_utub
    member_trying_to_remove_another_member = (
        current_user_id != current_utub.created_by.id and user_id != current_user_id
    )

    if current_user_not_in_utub or member_trying_to_remove_another_member:
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: USER_FAILURE.INVALID_PERMISSION_TO_REMOVE,
                    USER_FAILURE.EMAIL_VALIDATED: str(True),
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
                    STD_JSON.MESSAGE: USER_FAILURE.USER_NOT_IN_UTUB,
                    USER_FAILURE.EMAIL_VALIDATED: str(True),
                    STD_JSON.ERROR_CODE: 3,
                }
            ),
            404,
        )

    user_to_delete_in_utub = Utub_Users.query.filter(
        Utub_Users.utub_id == utub_id, Utub_Users.user_id == user_id
    ).first_or_404()

    deleted_user = User.query.get(user_id)
    deleted_user_username = deleted_user.username

    db.session.delete(user_to_delete_in_utub)
    db.session.commit()

    return (
        jsonify(
            {
                STD_JSON.STATUS: STD_JSON.SUCCESS,
                STD_JSON.MESSAGE: USER_SUCCESS.USER_REMOVED,
                USER_SUCCESS.USER_ID_REMOVED: f"{user_id}",
                USER_SUCCESS.USERNAME_REMOVED: f"{deleted_user_username}",
                USER_SUCCESS.UTUB_ID: f"{utub_id}",
                USER_SUCCESS.UTUB_NAME: f"{current_utub.name}",
                USER_SUCCESS.UTUB_USERS: [
                    user.to_user.username for user in current_utub.members
                ],
            }
        ),
        200,
    )


@members.route("/user/add/<int:utub_id>", methods=["POST"])
@email_validation_required
def add_member(utub_id: int):
    """
    Creator of utub wants to add a user to the utub.

    Args:
        utub_id (int): The utub to which this user is being added
    """
    utub = Utub.query.get_or_404(utub_id)

    if int(utub.created_by.id) != int(current_user.get_id()):
        # User not authorized to add a user to this UTub
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: USER_FAILURE.NOT_AUTHORIZED,
                    STD_JSON.ERROR_CODE: 1,
                }
            ),
            403,
        )

    utub_new_user_form = UTubNewUserForm()

    if utub_new_user_form.validate_on_submit():
        username = utub_new_user_form.username.data

        new_user = User.query.filter_by(username=username).first_or_404()
        already_in_utub = [
            member for member in utub.members if int(member.user_id) == int(new_user.id)
        ]

        if already_in_utub:
            # User already exists in UTub
            return (
                jsonify(
                    {
                        STD_JSON.STATUS: STD_JSON.FAILURE,
                        STD_JSON.MESSAGE: USER_FAILURE.USER_ALREADY_IN_UTUB,
                        STD_JSON.ERROR_CODE: 2,
                    }
                ),
                400,
            )

        else:
            new_user_to_utub = Utub_Users()
            new_user_to_utub.to_user = new_user
            utub.members.append(new_user_to_utub)
            db.session.commit()

            # Successfully added user to UTub
            return (
                jsonify(
                    {
                        STD_JSON.STATUS: STD_JSON.SUCCESS,
                        STD_JSON.MESSAGE: USER_SUCCESS.USER_ADDED,
                        USER_SUCCESS.USER_ID_ADDED: int(new_user.id),
                        USER_SUCCESS.UTUB_ID: int(utub_id),
                        USER_SUCCESS.UTUB_NAME: f"{utub.name}",
                        USER_SUCCESS.UTUB_USERS: [
                            user.to_user.username for user in utub.members
                        ],
                    }
                ),
                200,
            )

    if utub_new_user_form.errors is not None:
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: USER_FAILURE.UNABLE_TO_ADD,
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
                STD_JSON.MESSAGE: USER_FAILURE.UNABLE_TO_ADD,
                STD_JSON.ERROR_CODE: 4,
            }
        ),
        404,
    )
