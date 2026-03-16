from flask_login import current_user

from backend import db
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.app_logger import safe_add_many_logs
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utubs import Utubs
from backend.schemas.utubs import UtubCreatedResponseSchema
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON


def create_new_utub(utub_name: str, utub_description: str | None) -> FlaskResponse:
    """
    Creates a new UTub with the current user as the Creator.

    Args:
        utub_name (str): The name of the new UTub
        utub_description (str | None): Optional description for the UTub

    Returns:
        FlaskResponse: JSON response with success or error details
    """
    utub = _create_new_utub(utub_name, utub_description)

    _create_new_utub_member_for_utub_creator(utub)

    safe_add_many_logs(
        [
            "Created UTub",
            f"UTub.id={utub.id}",
            f"UTub.name={utub.name}",
        ]
    )

    return APIResponse(
        status=STD_JSON.SUCCESS,
        status_code=200,
        data=UtubCreatedResponseSchema(
            utub_id=utub.id,
            utub_name=utub.name,
            utub_description=utub.utub_description,
            utub_creator_id=current_user.id,
        ),
    ).to_response()


def _create_new_utub(name: str, description: str | None) -> Utubs:
    """
    Creates the new UTub and saves it to the database.

    Args:
        name (str): The UTub name
        description (str | None): The UTub description

    Returns:
        (Utubs): The new UTub model
    """
    utub = Utubs(name=name, utub_creator=current_user.id, utub_description=description)
    db.session.add(utub)
    db.session.commit()

    return utub


def _create_new_utub_member_for_utub_creator(utub: Utubs):
    """
    Creates a new Utub_Member association for the newly created UTub.

    Args:
        utub (Utubs): The new UTub the current user is the Creator of
    """
    creator_to_utub = Utub_Members()
    creator_to_utub.user_id = current_user.id
    creator_to_utub.utub_id = utub.id
    creator_to_utub.member_role = Member_Role.CREATOR
    db.session.add(creator_to_utub)
    db.session.commit()
