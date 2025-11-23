from flask import Response, jsonify
from flask_login import current_user

from src import db
from src.app_logger import (
    critical_log,
    safe_add_many_logs,
    turn_form_into_str_for_log,
    warning_log,
)
from src.models.utub_members import Member_Role, Utub_Members
from src.models.utubs import Utubs
from src.utils.strings.utub_strs import UTUB_FAILURE, UTUB_SUCCESS
from src.utubs.constants import UTubErrorCodes
from src.utubs.forms import UTubForm
from src.utubs.utils import build_form_errors
from src.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON


def create_new_utub() -> tuple[Response, int]:
    """
    Creates a new UTub with the current user as the Creator.

    Handle invalid form inputs and unexpected errors.

    Returns:
        tuple[Response, int]: A tuple containing:
        - Response: JSON response with success or error details
        - int: HTTP status code
            200 on success
            400 for form errors
            404 for unknown errors
    """

    create_utub_form: UTubForm = UTubForm()

    if not create_utub_form.validate_on_submit():
        return _handle_create_utub_form_input(create_utub_form)

    utub = _create_new_utub(create_utub_form)

    _create_new_utub_member_for_utub_creator(utub)

    safe_add_many_logs(
        [
            "Created UTub",
            f"UTub.id={utub.id}",
            f"UTub.name={utub.name}",
        ]
    )

    return (
        jsonify(
            {
                STD_JSON.STATUS: STD_JSON.SUCCESS,
                UTUB_SUCCESS.UTUB_ID: utub.id,
                UTUB_SUCCESS.UTUB_NAME: utub.name,
                UTUB_SUCCESS.UTUB_DESCRIPTION: utub.utub_description,
                UTUB_SUCCESS.UTUB_CREATOR_ID: current_user.id,
            }
        ),
        200,
    )


def _create_new_utub(create_utub_form: UTubForm) -> Utubs:
    """
    Creates the new UTub using details from the form and saves it to the database.

    Args:
        create_utub_form (UTubForm): Form containing the new UTub details

    Returns:
        (Utubs): The new UTub model
    """
    name = create_utub_form.name.get()
    description = create_utub_form.description.get()

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


def _handle_create_utub_form_input(create_utub_form: UTubForm) -> tuple[Response, int]:
    # Invalid form inputs
    if create_utub_form.errors is not None:
        warning_log(
            f"User={current_user.id} | Invalid form: {turn_form_into_str_for_log(create_utub_form.errors)}"  # type: ignore
        )
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: UTUB_FAILURE.UNABLE_TO_MAKE_UTUB,
                    STD_JSON.ERROR_CODE: UTubErrorCodes.INVALID_FORM_INPUT,
                    STD_JSON.ERRORS: build_form_errors(create_utub_form),
                }
            ),
            400,
        )

    critical_log(f"User={current_user.id} failed to make UTub")
    return (
        jsonify(
            {
                STD_JSON.STATUS: STD_JSON.FAILURE,
                STD_JSON.MESSAGE: UTUB_FAILURE.UNABLE_TO_MAKE_UTUB,
                STD_JSON.ERROR_CODE: UTubErrorCodes.UNKNOWN_ERROR,
            }
        ),
        404,
    )
