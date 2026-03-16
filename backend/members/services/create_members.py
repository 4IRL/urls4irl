from flask_login import current_user

from backend import db
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.app_logger import (
    safe_add_many_logs,
    warning_log,
)
from backend.members.data_models import ValidatedMember
from backend.models.users import Users
from backend.models.utub_members import Utub_Members
from backend.models.utubs import Utubs
from backend.schemas.users import MemberModifiedResponseSchema, UserSchema
from backend.utils.strings.user_strs import MEMBER_FAILURE, MEMBER_SUCCESS, USER_FAILURE


def create_utub_member(username: str, current_utub: Utubs) -> FlaskResponse:
    """
    Adds a user to a UTub. Handles if the user already exists in the UTub.

    Args:
        username (str): Username of the user to add
        current_utub (Utubs): The UTub to add the user to

    Returns:
        tuple[Response, int]:
        - Response: JSON response on create
        - int: HTTP status code 200 (Success), 400 (User not found or already a member)
    """
    new_user: Users | None = Users.query.filter(Users.username == username).first()
    if new_user is None:
        warning_log(f"User={current_user.id} tried adding nonexistent username")
        return APIResponse(
            status_code=400,
            message=MEMBER_FAILURE.UNABLE_TO_ADD_MEMBER,
            errors={"username": [USER_FAILURE.USER_NOT_EXIST]},
        ).to_response()

    member_in_utub = _check_if_member_already_in_utub(new_user, current_utub)
    if member_in_utub.in_utub:
        return APIResponse(
            status_code=400,
            message=MEMBER_FAILURE.MEMBER_ALREADY_IN_UTUB,
        ).to_response()

    return _add_user_to_utub(user=new_user, current_utub=current_utub)


def _check_if_member_already_in_utub(
    user: Users, current_utub: Utubs
) -> ValidatedMember:
    """
    Checks if the user is already a member in the UTub.

    Args:
        user (Users): The user to check
        current_utub (Utubs): The UTub to check membership in

    Returns:
        ValidatedMember: Containing the User object and whether they are already in the UTub
    """
    already_in_utub = Utub_Members.query.get((current_utub.id, user.id)) is not None

    if already_in_utub:
        warning_log(
            f"User={current_user.id} tried adding a User={user.id} already in this UTub"
        )

    return ValidatedMember(user=user, in_utub=already_in_utub)


def _add_user_to_utub(user: Users, current_utub: Utubs) -> FlaskResponse:
    """
    Handles adding the user to the UTub as a new UTub member.

    Args:
        user (Users): User being added to this UTub
        current_utub (Utubs): The UTub where this new member is being added too

    Returns:
        tuple[Response, int]:
        - Response: JSON response on success
        - int: HTTP status code 200
    """
    new_user_to_utub = Utub_Members()
    new_user_to_utub.utub_id = current_utub.id
    new_user_to_utub.user_id = user.id
    db.session.add(new_user_to_utub)
    current_utub.set_last_updated()
    db.session.commit()

    # Successfully added user to UTub
    safe_add_many_logs(
        ["Added member to UTub", f"UTub.id={current_utub.id}", f"Added User={user.id}"]
    )

    return APIResponse(
        message=MEMBER_SUCCESS.MEMBER_ADDED,
        data=MemberModifiedResponseSchema(
            utub_id=current_utub.id,
            member=UserSchema(id=user.id, username=user.username),
        ),
    ).to_response()
