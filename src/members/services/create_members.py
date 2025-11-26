from flask_login import current_user

from src import db
from src.api_common.responses import APIResponse, FlaskResponse
from src.app_logger import (
    critical_log,
    safe_add_many_logs,
    turn_form_into_str_for_log,
    warning_log,
)
from src.members.constants import UTubMembersErrorCodes
from src.members.data_models import ValidatedMember
from src.members.forms import UTubNewMemberForm
from src.models.users import Users
from src.models.utub_members import Utub_Members
from src.models.utubs import Utubs
from src.utils.strings.model_strs import MODELS
from src.utils.strings.user_strs import MEMBER_FAILURE, MEMBER_SUCCESS


def handle_invalid_form_on_create_utub_member(
    member_form: UTubNewMemberForm,
) -> FlaskResponse:
    if member_form.errors is not None:
        warning_log(
            f"User={current_user.id} | Invalid form: {turn_form_into_str_for_log(member_form.errors)}"  # type: ignore
        )
        return APIResponse(
            status_code=400,
            message=MEMBER_FAILURE.UNABLE_TO_ADD_MEMBER,
            error_code=UTubMembersErrorCodes.INVALID_FORM_INPUT,
            errors=member_form.errors,
        ).to_response()

    critical_log(f"User={current_user.id} failed to add member to UTub")
    return APIResponse(
        status_code=404,
        message=MEMBER_FAILURE.UNABLE_TO_ADD_MEMBER,
        error_code=UTubMembersErrorCodes.UNKNOWN_EXCEPTION,
    ).to_response()


def create_utub_member(
    member_form: UTubNewMemberForm, current_utub: Utubs
) -> FlaskResponse:
    """
    Adds a user to a UTub. Handles if the user already exists in the UTub.

    Args:
        member_form (UTubNewMemberForm): Form containing the username of the user to add
        current_utub (Utubs): The UTub to add the user to

    Returns:
        tuple[Response, int]:
        - Response: JSON response on create
        - int: HTTP status code 200 (Success), 400 (User already member in UTub)
    """
    username = member_form.username.data

    member_in_utub = _validate_if_member_already_in_utub(username, current_utub)
    if member_in_utub.in_utub:
        return APIResponse(
            status_code=400,
            message=MEMBER_FAILURE.MEMBER_ALREADY_IN_UTUB,
        ).to_response()

    return _add_user_to_utub(user=member_in_utub.user, current_utub=current_utub)


def _validate_if_member_already_in_utub(
    username: str | None, current_utub: Utubs
) -> ValidatedMember:
    """
    Validates if the user is already a member in the UTub.

    Args:
        username (str): Username of the user to add as a member to this UTub
        current_utub (Utubs): The UTub to add the user to

    Returns:
        ValidatedMembers: Containing the User object of the member to add, and a boolean indicating
            whether the user is already in the UTub
    """
    new_user: Users = Users.query.filter(Users.username == username).first_or_404()
    already_in_utub = Utub_Members.query.get((current_utub.id, new_user.id)) is not None

    if already_in_utub:
        # User already exists in UTub
        warning_log(
            f"User={current_user.id} tried adding a User={new_user.id} already in this UTub"
        )

    return ValidatedMember(user=new_user, in_utub=already_in_utub)


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
        data={
            MEMBER_SUCCESS.UTUB_ID: current_utub.id,
            MEMBER_SUCCESS.MEMBER: {
                MODELS.USERNAME: user.username,
                MODELS.ID: user.id,
            },
        },
    ).to_response()
