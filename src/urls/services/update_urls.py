from flask_login import current_user
from src import db
from src.api_common.request_utils import is_adder_of_utub_url, is_current_utub_creator
from src.api_common.responses import APIResponse, FlaskResponse
from src.app_logger import (
    critical_log,
    safe_add_many_logs,
    turn_form_into_str_for_log,
    warning_log,
)
from src.models.urls import Urls
from src.models.utub_urls import Utub_Urls
from src.models.utubs import Utubs
from src.urls.constants import URLErrorCodes, URLState
from src.urls.forms import UpdateURLForm
from src.urls.services.create_urls import (
    build_response_for_invalidated_url,
    validate_new_url_for_utub,
)
from src.urls.utils import build_form_errors
from src.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from src.utils.strings.url_strs import URL_FAILURE, URL_NO_CHANGE, URL_SUCCESS


def check_if_is_url_adder_or_utub_creator_on_url_update(
    utub_id: int, utub_url_id: int
) -> bool:
    """
    Verify that the current user has permission to delete a URL from a UTub.

    Checks whether the current user is either the creator of the UTub or the user who
    originally added the URL. If neither condition is met, logs a critical error and
    returns a 403 Forbidden response.

    Args:
        utub_id (int): The ID of the UTub containing the URL to be deleted.
        utub_url_id (int): The ID of the Utub_Urls association to be deleted.

    Returns:
        (bool): True if is UTub Creator URL adder
    """
    is_utub_creator_or_adder_of_utub_url = (
        is_current_utub_creator() or is_adder_of_utub_url()
    )
    if not is_utub_creator_or_adder_of_utub_url:
        critical_log(
            f"User={current_user.id} not allowed to modify UTubURL.id={utub_url_id} in UTub.id={utub_id}"
        )

    return is_utub_creator_or_adder_of_utub_url


def update_url_in_utub(
    update_url_form: UpdateURLForm, current_utub: Utubs, current_utub_url: Utub_Urls
) -> FlaskResponse:
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
    is_empty_url = _check_for_empty_url_string_on_update(
        url_to_change_to, current_utub_url.id
    )

    if is_empty_url:
        return APIResponse(
            status_code=400,
            message=URL_FAILURE.EMPTY_URL,
            error_code=URLErrorCodes.EMPTY_URL,
        ).to_response()

    # Check for updating the URL to the same URL
    is_equivalent_url = _check_for_equivalent_url_on_update(
        url_to_change_to, current_utub_url
    )

    if is_equivalent_url:
        return APIResponse(
            status=STD_JSON.NO_CHANGE,
            message=URL_NO_CHANGE.URL_NOT_MODIFIED,
            data={
                URL_SUCCESS.URL: current_utub_url.serialized_on_get_or_update,
            },
        ).to_response()

    validated_new_url = validate_new_url_for_utub(url_to_change_to, current_utub.id)
    if (
        validated_new_url.url_state == URLState.INVALID_URL_STRING
        or validated_new_url.url is None
    ):
        return build_response_for_invalidated_url(validated_new_url.normalized_url)

    return _associate_updated_url_with_utub(
        url=validated_new_url.url,
        current_utub=current_utub,
        current_utub_url=current_utub_url,
    )


def _check_for_empty_url_string_on_update(
    url_string: str,
    utub_url_id: int,
) -> bool:
    """
    Checks if the provided URL to update to is an empty string.

    Args:
        url_string (str): The URL string to update to.
        utub_url_id (int): The ID of the UTub URL

    Returns:
        (bool): True if url string is empty
    """
    is_empty_url = not url_string
    if is_empty_url:
        warning_log(
            f"User={current_user.id} tried changing UTubURL.id={utub_url_id} to a URL with only spaces"
        )
    return is_empty_url


def _check_for_equivalent_url_on_update(
    url_to_change_to: str, current_utub_url: Utub_Urls
) -> bool:
    """
    Checks if the provided URL to update to is equivalent to the current URL.

    Args:
        url_to_change_to (str): The URL string to update to.
        utub_url_id (int): The ID of the UTub URL

    Returns:
        (bool): True if url string is equivalent to given URL
    """

    is_equivalent_url = url_to_change_to == current_utub_url.standalone_url.url_string

    if is_equivalent_url:
        warning_log(
            f"User={current_user.id} tried changing UTubURL.id={current_utub_url.id} to the same URL"
        )
    return is_equivalent_url


def _associate_updated_url_with_utub(
    url: Urls,
    current_utub: Utubs,
    current_utub_url: Utub_Urls,
) -> FlaskResponse:
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

    return APIResponse(
        message=URL_SUCCESS.URL_MODIFIED,
        data={
            URL_SUCCESS.UTUB_ID: current_utub.id,
            URL_SUCCESS.UTUB_NAME: current_utub.name,
            URL_SUCCESS.URL: new_serialized_url,
        },
    ).to_response()


def handle_invalid_update_url_form_input(
    update_url_form: UpdateURLForm,
) -> FlaskResponse:
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
        return APIResponse(
            status_code=400,
            message=URL_FAILURE.UNABLE_TO_MODIFY_URL_FORM,
            error_code=URLErrorCodes.INVALID_FORM_INPUT,
            errors=build_form_errors(update_url_form),
        ).to_response()

    # Something else went wrong
    critical_log("Unable to update URL to UTub")
    return APIResponse(
        status_code=404,
        message=URL_FAILURE.UNABLE_TO_MODIFY_URL,
        error_code=URLErrorCodes.UNKNOWN_ERROR,
    ).to_response()
