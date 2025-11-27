from flask_login import current_user

from src import db
from src.api_common.request_utils import is_current_utub_creator
from src.api_common.responses import APIResponse, FlaskResponse
from src.app_logger import critical_log, safe_add_many_logs, warning_log
from src.models.utub_members import Utub_Members
from src.models.utubs import Utubs
from src.utils.strings.model_strs import MODELS
from src.utils.strings.user_strs import MEMBER_FAILURE, MEMBER_SUCCESS


def remove_member_or_self_from_utub(
    user_id_to_remove: int, current_utub: Utubs
) -> FlaskResponse:
    """
    Handles validating if a given user id corresponds to a valid UTub member, and whether that
    member can be removed by the current user.

    UTub creators can remove anyone but themselves, and members can only remove themselves.

    Args:
        user_id_to_remove (int): The ID of the user to remove from this UTub
        current_utub (Utubs): The UTub to remove the user from

    Returns:
        tuple[Response, int]:
        - Response: JSON response on successful or invalid removal
        - int: HTTP status code
            - 200 (on successful removal)
            - 400 (on creator trying to remove themselves)
            - 403 (on member trying to remove someone else)
            - 404 (on member being removed not existing in UTub)
    """
    is_utub_creator = is_current_utub_creator()

    creator_removing_themself = _creator_removing_themself(
        is_utub_creator, user_id_to_remove
    )

    if creator_removing_themself:
        return APIResponse(
            status_code=400,
            message=MEMBER_FAILURE.CREATOR_CANNOT_REMOVE_THEMSELF,
        ).to_response()

    member_removing_another_member = _member_is_removing_another_member(
        is_utub_creator=is_utub_creator,
        user_id_to_remove=user_id_to_remove,
        current_utub=current_utub,
    )

    if member_removing_another_member:
        return APIResponse(
            status_code=403,
            message=MEMBER_FAILURE.INVALID_PERMISSION_TO_REMOVE,
        ).to_response()

    user_to_remove_in_utub: Utub_Members | None = Utub_Members.query.get(
        (current_utub.id, user_id_to_remove)
    )

    if user_to_remove_in_utub is None:
        return _handle_removing_nonexistent_member()

    return _remove_member_from_utub(
        user_to_remove=user_to_remove_in_utub, current_utub=current_utub
    )


def _creator_removing_themself(is_utub_creator: bool, user_id_to_remove: int) -> bool:
    """
    Creators cannot remove themselves from the UTub currently.

    Args:
        is_utub_creator (bool): True if the user is this UTub's creator
        user_id_to_remove (int): The ID of the user being removed

    Returns:
        (bool): True if creator is removing themselves
    """
    is_creator_removing_themself = (
        is_utub_creator and current_user.id == user_id_to_remove
    )

    if is_creator_removing_themself:
        warning_log(f"User={current_user.id} | UTub creator tried to remove themselves")

    return is_creator_removing_themself


def _member_is_removing_another_member(
    is_utub_creator: bool, user_id_to_remove: int, current_utub: Utubs
) -> bool:
    """
    Members cannot remove other members from UTubs.

    Args:
        is_utub_creator (bool): True if the user is this UTub's creator
        user_id_to_remove (int): The ID of the user being removed
        current_utub (Utubs): The UTub to remove the user from

    Returns:
        tuple[Response, int]:
        - Response: JSON response on member removing another member
        - int: HTTP status code 403 (Success)
        OR
        None: If the user is not a creator and removing themself, or is the creator and removing a member
    """
    # Non-creators can only remove themselves
    is_member_removing_other_member = (
        not is_utub_creator and current_user.id != user_id_to_remove
    )

    if is_member_removing_other_member:
        critical_log(
            f"User={current_user.id} tried removing another member from UTub.id={current_utub.id}"
        )

    return is_member_removing_other_member


def _handle_removing_nonexistent_member() -> FlaskResponse:
    """
    Builds the response for a nonexistent member being removed

    Returns:
        tuple[Response, int]:
        - Response: JSON response on create
        - int: HTTP status code 200 (Success)

    """
    warning_log(
        f"User={current_user.id} tried removing a member that isn't in this UTub"
    )
    return APIResponse(
        status_code=404,
        message=MEMBER_FAILURE.MEMBER_NOT_IN_UTUB,
    ).to_response()


def _remove_member_from_utub(
    user_to_remove: Utub_Members, current_utub: Utubs
) -> FlaskResponse:
    """
    Remove a member from a UTub.

    Args:
        user_to_remove (Utub_Members): The member being removed from this UTub
        current_utub (Utubs): The UTub to remove the user from

    Returns:
        tuple[Response, int]:
        - Response: JSON response on successful removal
        - int: HTTP status code 200 (Success)
    """
    user_id_to_remove = user_to_remove.user_id
    removed_user_username: str = user_to_remove.to_user.username

    db.session.delete(user_to_remove)
    current_utub.set_last_updated()
    db.session.commit()

    safe_add_many_logs(
        [
            "Removed member from UTub",
            f"UTub.id={current_utub.id}",
            f"User={user_id_to_remove}",
        ]
    )

    return APIResponse(
        message=MEMBER_SUCCESS.MEMBER_REMOVED,
        data={
            MEMBER_SUCCESS.UTUB_ID: current_utub.id,
            MEMBER_SUCCESS.MEMBER: {
                MODELS.ID: user_id_to_remove,
                MODELS.USERNAME: removed_user_username,
            },
        },
    ).to_response()
