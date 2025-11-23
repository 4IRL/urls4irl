from flask import Response, jsonify
from flask_login import current_user

from src import db
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
) -> tuple[Response, int]:
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
    title_diff = new_url_title != current_utub_url.url_title

    if title_diff:
        current_utub_url.url_title = new_url_title  # Updates the title

        serialized_url_in_utub = current_utub_url.serialized_on_get_or_update
        current_utub.set_last_updated()
        db.session.commit()
        safe_add_log("URL title updated")
    else:
        warning_log(f"User={current_user.id} tried updating to identical URL title")

    return (
        jsonify(
            {
                STD_JSON.STATUS: STD_JSON.SUCCESS if title_diff else STD_JSON.NO_CHANGE,
                STD_JSON.MESSAGE: (
                    URL_SUCCESS.URL_TITLE_MODIFIED
                    if title_diff
                    else URL_NO_CHANGE.URL_TITLE_NOT_MODIFIED
                ),
                URL_SUCCESS.URL: serialized_url_in_utub,
            }
        ),
        200,
    )


def handle_invalid_update_url_title_form_input(
    update_url_title_form: UpdateURLTitleForm,
) -> tuple[Response, int]:
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
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_MODIFY_URL_FORM,
                    STD_JSON.ERRORS: {
                        URL_FAILURE.URL_TITLE: URL_FAILURE.FIELD_REQUIRED
                    },
                }
            ),
            400,
        )

    # Invalid form input
    if update_url_title_form.errors is not None:
        warning_log(
            f"User={current_user.id} | Invalid form: {turn_form_into_str_for_log(update_url_title_form.errors)}"  # type: ignore
        )
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_MODIFY_URL_FORM,
                    STD_JSON.ERROR_CODE: URLErrorCodes.INVALID_FORM_INPUT,
                    STD_JSON.ERRORS: build_form_errors(update_url_title_form),
                }
            ),
            400,
        )

    # Something else went wrong
    critical_log("Unable to update URL title in UTub")
    return (
        jsonify(
            {
                STD_JSON.STATUS: STD_JSON.FAILURE,
                STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_MODIFY_URL,
                STD_JSON.ERROR_CODE: URLErrorCodes.UNKNOWN_ERROR,
            }
        ),
        404,
    )
