from flask_login import current_user

from src import db
from src.api_common.responses import APIResponse, FlaskResponse
from src.app_logger import (
    critical_log,
    safe_add_log,
    turn_form_into_str_for_log,
    warning_log,
)
from src.models.utub_urls import Utub_Urls
from src.models.utubs import Utubs
from src.urls.constants import URLErrorCodes
from src.urls.forms import UpdateURLTitleForm
from src.urls.utils import build_form_errors
from src.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from src.utils.strings.url_strs import URL_FAILURE, URL_NO_CHANGE, URL_SUCCESS


def update_url_title_if_new(
    new_url_title: str, current_utub: Utubs, current_utub_url: Utub_Urls
) -> FlaskResponse:
    """
    Verify that the current user has permission to delete a URL from a UTub.

    Checks whether the current user is either the creator of the UTub or the user who
    originally added the URL. If neither condition is met, logs a critical error and
    returns a 403 Forbidden response.

    Args:
        new_url_title (str): The URL title to update to
        current_utub (Utubs): The UTub object containing the UTub_Urls
        current_utub_url (Utub_Urls): The UTub_Urls object to update the title for.

    Returns:
        tuple[Response, int]:
        - Response: JSON response on update
        - int: HTTP status code 200 (Success)
    """
    serialized_url_in_utub = current_utub_url.serialized_on_get_or_update
    is_different_title = new_url_title != current_utub_url.url_title

    if is_different_title:
        current_utub_url.url_title = new_url_title  # Updates the title

        serialized_url_in_utub = current_utub_url.serialized_on_get_or_update
        current_utub.set_last_updated()
        db.session.commit()
        safe_add_log("URL title updated")
    else:
        warning_log(f"User={current_user.id} tried updating to identical URL title")

    message = URL_SUCCESS.URL_TITLE_MODIFIED

    return APIResponse(
        status=STD_JSON.SUCCESS if is_different_title else STD_JSON.NO_CHANGE,
        message=message if is_different_title else URL_NO_CHANGE.URL_TITLE_NOT_MODIFIED,
        data={
            URL_SUCCESS.URL: serialized_url_in_utub,
        },
    ).to_response()


def handle_invalid_update_url_title_form_input(
    update_url_title_form: UpdateURLTitleForm,
) -> FlaskResponse:
    """
    Handle invalid form input when updating a URL Title in a UTub.

    Logs validation errors and returns an appropriate error response with form field errors
    or a generic failure message if form validation passes but something else fails.

    Args:
        update_url_title_form (UpdateURLTitleForm): The form object containing URL input data and validation errors.

    Returns:
        tuple[Response, int]: A tuple containing:
        - Response: JSON response with error details and status
        - int: HTTP status code (400 for form errors, 404 for unknown errors)
    """

    # Missing URL title field
    if update_url_title_form.url_title.data is None:
        warning_log(f"User={current_user.id} missing URL title field")
        return APIResponse(
            status_code=400,
            message=URL_FAILURE.UNABLE_TO_MODIFY_URL_FORM,
            errors={URL_FAILURE.URL_TITLE: URL_FAILURE.FIELD_REQUIRED},
        ).to_response()

    # Invalid form input
    if update_url_title_form.errors is not None:
        warning_log(
            f"User={current_user.id} | Invalid form: {turn_form_into_str_for_log(update_url_title_form.errors)}"  # type: ignore
        )
        return APIResponse(
            status_code=400,
            message=URL_FAILURE.UNABLE_TO_MODIFY_URL_FORM,
            error_code=URLErrorCodes.INVALID_FORM_INPUT,
            errors=build_form_errors(update_url_title_form),
        ).to_response()

    # Something else went wrong
    critical_log("Unable to update URL title in UTub")
    return APIResponse(
        status_code=404,
        message=URL_FAILURE.UNABLE_TO_MODIFY_URL,
        error_code=URLErrorCodes.UNKNOWN_ERROR,
    ).to_response()
