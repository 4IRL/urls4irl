from flask_login import current_user

from src import db
from src.api_common.responses import APIResponse, FlaskResponse
from src.app_logger import (
    critical_log,
    safe_add_log,
    safe_add_many_logs,
    turn_form_into_str_for_log,
    warning_log,
)
from src.models.utubs import Utubs
from src.utils.strings.utub_strs import UTUB_FAILURE, UTUB_SUCCESS
from src.utubs.constants import UTubErrorCodes
from src.utubs.forms import UTubDescriptionForm, UTubNewNameForm
from src.utubs.utils import build_form_errors


def handle_invalid_update_utub_name_form_input(
    utub_name_form: UTubNewNameForm,
) -> FlaskResponse:
    """
    Handles an invalid form for updating the UTub name, or an unknown exception.

    Args:
        utub_name_form (UTubNewNameForm): Contains form errors if form is invalid

    Returns:
        tuple[Response, int]:
        - Response: JSON response on for given exception
        - int: HTTP status code 400 (Invalid Form) or 404 (Unknown Exception)
    """
    # Invalid form errors
    if utub_name_form.errors is not None:
        warning_log(
            f"User={current_user.id} | Invalid form: {turn_form_into_str_for_log(utub_name_form.errors)}"  # type: ignore
        )
        return APIResponse(
            status_code=400,
            message=UTUB_FAILURE.UNABLE_TO_MODIFY_UTUB_NAME,
            error_code=UTubErrorCodes.INVALID_FORM_INPUT,
            errors=build_form_errors(utub_name_form),
        ).to_response()

    critical_log(f"User={current_user.id} | Unable to update UTub name")
    return APIResponse(
        status_code=404,
        message=UTUB_FAILURE.UNABLE_TO_MODIFY_UTUB_NAME,
        error_code=UTubErrorCodes.UNKNOWN_ERROR,
    ).to_response()


def update_utub_name_if_new(
    current_utub: Utubs, utub_name_form: UTubNewNameForm
) -> FlaskResponse:
    """
    Updates the name for the UTub only if it is not equivalent to the old name.

    Args:
        current_utub (Utubs): The UTub that is being updated
        utub_name_form (UTubNewNameForm): Contains the new name for the UTub

    Returns:
        tuple[Response, int]:
        - Response: JSON response on update
        - int: HTTP status code 200 (Success)
    """
    old_utub_name = current_utub.name

    new_utub_name = utub_name_form.name.get()

    if new_utub_name != old_utub_name:
        current_utub.name = new_utub_name
        current_utub.set_last_updated()
        db.session.commit()

        safe_add_many_logs(
            [
                "User updated UTub name",
                f"UTub.id={current_utub.id}",
                f"OLD UTub.name={old_utub_name}",
                f"NEW UTub.name={current_utub.name}",
            ]
        )

    return APIResponse(
        data={
            UTUB_SUCCESS.UTUB_ID: current_utub.id,
            UTUB_SUCCESS.UTUB_NAME: current_utub.name,
        }
    ).to_response()


def handle_invalid_update_utub_description_form_input(
    utub_desc_form: UTubDescriptionForm,
) -> FlaskResponse:
    """
    Handles an invalid form for updating the UTub description, or an unknown exception.

    Args:
        utub_desc_form (UTubDescriptionForm): Contains form errors if form is invalid

    Returns:
        tuple[Response, int]:
        - Response: JSON response on for given exception
        - int: HTTP status code 400 (Invalid Form) or 404 (Unknown Exception)
    """
    # Invalid form input
    if utub_desc_form.errors is not None:
        warning_log(
            f"User={current_user.id} | Invalid form: {turn_form_into_str_for_log(utub_desc_form.errors)}"  # type: ignore
        )
        return APIResponse(
            status_code=400,
            message=UTUB_FAILURE.UNABLE_TO_MODIFY_UTUB_DESC,
            error_code=UTubErrorCodes.INVALID_FORM_INPUT,
            errors=build_form_errors(utub_desc_form),
        ).to_response()

    critical_log(f"User={current_user.id} | Unable to update UTub description")
    return APIResponse(
        status_code=404,
        message=UTUB_FAILURE.UNABLE_TO_MODIFY_UTUB_DESC,
        error_code=UTubErrorCodes.UNKNOWN_ERROR,
    ).to_response()


def update_utub_desc_if_new(
    current_utub: Utubs, utub_desc_form: UTubDescriptionForm
) -> FlaskResponse:
    """
    Updates the description for the UTub only if it is not equivalent to the old description.

    Args:
        current_utub (Utubs): The UTub that is being updated
        utub_desc_form (UTubDescriptionForm): Contains the new description for the UTub

    Returns:
        tuple[Response, int]:
        - Response: JSON response on update
        - int: HTTP status code 200 (Success)
    """

    current_utub_description = (
        "" if current_utub.utub_description is None else current_utub.utub_description
    )

    new_utub_description = utub_desc_form.description.data

    if new_utub_description is None:
        warning_log(f"User={current_user.id} | UTub description was None")
        return APIResponse(
            status_code=400,
            message=UTUB_FAILURE.UNABLE_TO_MODIFY_UTUB_DESC,
            error_code=UTubErrorCodes.INVALID_FORM_INPUT,
        ).to_response()

    if new_utub_description != current_utub_description:
        current_utub.utub_description = new_utub_description
        current_utub.set_last_updated()
        db.session.commit()

        safe_add_many_logs(
            [
                "Updated UTub description",
                f"UTub.id={current_utub.id}",
                f"OLD UTub.description={current_utub_description}",
                f"NEW UTub.description={new_utub_description}",
            ]
        )
    else:
        safe_add_log("No change in UTub description")

    return APIResponse(
        data={
            UTUB_SUCCESS.UTUB_ID: current_utub.id,
            UTUB_SUCCESS.UTUB_DESCRIPTION: current_utub.utub_description,
        }
    ).to_response()
