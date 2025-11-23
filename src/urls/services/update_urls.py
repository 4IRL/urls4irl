from flask import Response, jsonify
from flask_login import current_user
from src import db
from src.app_logger import (
    critical_log,
    safe_add_many_logs,
    turn_form_into_str_for_log,
    warning_log,
)
from src.models.urls import Urls
from src.models.utub_urls import Utub_Urls
from src.models.utubs import Utubs
from src.urls.constants import URLErrorCodes
from src.urls.data_models import ValidatedUrl
from src.urls.forms import UpdateURLForm
from src.urls.services.create_urls import validate_new_url_for_utub
from src.urls.utils import build_form_errors
from src.utils.request_utils import is_adder_of_utub_url, is_current_utub_creator
from src.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from src.utils.strings.url_strs import URL_FAILURE, URL_NO_CHANGE, URL_SUCCESS


def check_if_is_url_adder_or_utub_creator_on_url_update(
    utub_id: int, utub_url_id: int
) -> tuple[Response, int] | None:
    """
    Verify that the current user has permission to delete a URL from a UTub.

    Checks whether the current user is either the creator of the UTub or the user who
    originally added the URL. If neither condition is met, logs a critical error and
    returns a 403 Forbidden response.

    Args:
        utub_id (int): The ID of the UTub containing the URL to be deleted.
        utub_url_id (int): The ID of the Utub_Urls association to be deleted.

    Returns:
        tuple[Response, int] | None: If the user lacks permission, returns:
        - Response: JSON response indicating deletion is not allowed
        - int: HTTP status code 403 (Forbidden)
        If the user has permission, returns None to allow deletion to proceed.
    """
    is_utub_creator_or_adder_of_utub_url = (
        is_current_utub_creator() or is_adder_of_utub_url()
    )
    if not is_utub_creator_or_adder_of_utub_url:
        critical_log(
            f"User={current_user.id} not allowed to modify UTubURL.id={utub_url_id} in UTub.id={utub_id}"
        )

        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_MODIFY_URL,
                }
            ),
            403,
        )


def update_url_in_utub(
    update_url_form: UpdateURLForm, current_utub: Utubs, current_utub_url: Utub_Urls
) -> tuple[Response, int]:
    """
    Updates the given Utub_Urls in the UTub.

    Args:
        update_url_form (UpdateURLForm): Form containing updated URL data
        current_utub (Utubs): The UTub object containing the UTub_Urls
        current_utub_url (Utub_Urls): The UTub_Urls object to update.

    Returns:
        tuple[Response, int]:
        - Response: JSON response on update
        - int: HTTP status code 200 (Success)
    """
    url_to_change_to: str = update_url_form.get_url_string().replace(" ", "")

    # Check for empty URL string to update to
    empty_url_string_response = _check_for_empty_url_string_on_update(
        url_to_change_to, current_utub_url.id
    )

    if empty_url_string_response is not None:
        return empty_url_string_response

    # Check for updating the URL to the same URL
    equivalent_url_response = _check_for_equivalent_url_on_update(
        url_to_change_to, current_utub_url
    )
    if equivalent_url_response is not None:
        return equivalent_url_response

    validate_new_url_response = validate_new_url_for_utub(
        url_to_change_to, current_utub.id
    )
    if not isinstance(validate_new_url_response, ValidatedUrl):
        return validate_new_url_response

    validated_url_obj: ValidatedUrl = validate_new_url_response

    return _associate_updated_url_with_utub(
        url=validated_url_obj.url,
        current_utub=current_utub,
        current_utub_url=current_utub_url,
    )


def _check_for_empty_url_string_on_update(
    url_string: str,
    utub_url_id: int,
) -> tuple[Response, int] | None:
    """
    Checks if the provided URL to update to is an empty string.

    Args:
        url_string (str): The URL string to update to.
        utub_url_id (int): The ID of the UTub URL

    Returns:
        tuple[Response, int]: On empty string, returns a response with error code.
        None: On a non-empty string, returns None
    """
    if not url_string:
        warning_log(
            f"User={current_user.id} tried changing UTubURL.id={utub_url_id} to a URL with only spaces"
        )
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: URL_FAILURE.EMPTY_URL,
                    STD_JSON.ERROR_CODE: URLErrorCodes.EMPTY_URL,
                }
            ),
            400,
        )


def _check_for_equivalent_url_on_update(
    url_to_change_to: str, current_utub_url: Utub_Urls
) -> tuple[Response, int] | None:
    """
    Checks if the provided URL to update to is equivalent to the current URL.

    Args:
        url_to_change_to (str): The URL string to update to.
        utub_url_id (int): The ID of the UTub URL

    Returns:
        tuple[Response, int]: On the URLs being equivalent, returns a response with code.
        None: On a non-equivalent URL, returns None
    """

    serialized_url_in_utub = current_utub_url.serialized_on_get_or_update

    if url_to_change_to == current_utub_url.standalone_url.url_string:
        warning_log(
            f"User={current_user.id} tried changing UTubURL.id={current_utub_url.id} to the same URL"
        )
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.NO_CHANGE,
                    STD_JSON.MESSAGE: URL_NO_CHANGE.URL_NOT_MODIFIED,
                    URL_SUCCESS.URL: serialized_url_in_utub,
                }
            ),
            200,
        )


def _associate_updated_url_with_utub(
    url: Urls,
    current_utub: Utubs,
    current_utub_url: Utub_Urls,
) -> tuple[Response, int]:
    """
    Associates the updated UTub_Url with the UTub.

    Args:
        url (Urls): The URL being updated
        current_utub (Utubs): The UTub object containing the UTub_Urls
        current_utub_url (Utub_Urls): The UTub_Urls object to update the title for.

    Returns:
        tuple[Response, int]:
        - Response: JSON response on update
        - int: HTTP status code 200 (Success)
    """
    # Now set the URL ID for the old URL to the new URL
    current_utub_url.url_id = url.id
    current_utub_url.standalone_url = url

    new_serialized_url = current_utub_url.serialized_on_get_or_update

    current_utub.set_last_updated()
    db.session.commit()

    safe_add_many_logs(
        ["Added URL to UTub", f"UTub.id={current_utub.id}", f"URL.id={url.id}"]
    )

    return (
        jsonify(
            {
                STD_JSON.STATUS: STD_JSON.SUCCESS,
                STD_JSON.MESSAGE: URL_SUCCESS.URL_MODIFIED,
                URL_SUCCESS.UTUB_ID: current_utub.id,
                URL_SUCCESS.UTUB_NAME: current_utub.name,
                URL_SUCCESS.URL: new_serialized_url,
            }
        ),
        200,
    )


def handle_invalid_update_url_form_input(
    update_url_form: UpdateURLForm,
) -> tuple[Response, int]:
    """
    Handle invalid form input when updating a URL in a UTub.

    Logs validation errors and returns an appropriate error response with form field errors
    or a generic failure message if form validation passes but something else fails.

    Args:
        update_url_form (UpdateURLForm): The form object containing URL input data and validation errors.

    Returns:
        tuple[Response, int]: A tuple containing:
        - Response: JSON response with error details and status
        - int: HTTP status code (400 for form errors, 404 for unknown errors)
    """
    if update_url_form.errors is not None:
        warning_log(f"User={current_user.id} | Invalid form: {turn_form_into_str_for_log(update_url_form.errors)}")  # type: ignore
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_MODIFY_URL_FORM,
                    STD_JSON.ERROR_CODE: URLErrorCodes.INVALID_FORM_INPUT,
                    STD_JSON.ERRORS: build_form_errors(update_url_form),
                }
            ),
            400,
        )

    # Something else went wrong
    critical_log("Unable to update URL to UTub")
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
