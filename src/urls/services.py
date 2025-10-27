import time
from typing import cast

from flask import Response, current_app, jsonify
from flask_login import current_user

from src import db
from src.app_logger import (
    critical_log,
    safe_add_log,
    safe_add_many_logs,
    safe_get_request_id,
    turn_form_into_str_for_log,
    warning_log,
)
from src.extensions.extension_utils import safe_get_notif_sender, safe_get_url_validator
from src.extensions.url_validation.url_validator import (
    AdaUrlParsingError,
    InvalidURLError,
    URLWithCredentialsError,
)
from src.models.urls import Urls
from src.models.utub_url_tags import Utub_Url_Tags
from src.models.utub_urls import Utub_Urls
from src.models.utubs import Utubs
from src.urls.constants import URLErrorCodes, URLState
from src.urls.forms import NewURLForm
from src.urls.utils import (
    build_form_errors,
    get_utub_url_tag_ids_and_count_in_utub,
    get_utub_url_tag_ids_and_utub_tag_ids_on_utub_url,
)
from src.utils.request_utils import is_adder_of_utub_url, is_current_utub_creator
from src.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from src.utils.strings.url_strs import URL_FAILURE, URL_SUCCESS


def check_if_is_url_adder_or_utub_creator_on_url_delete(
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
    is_utub_creator_or_added_of_utub_url = (
        is_current_utub_creator() or is_adder_of_utub_url()
    )
    if not is_utub_creator_or_added_of_utub_url:
        # Can only remove URLs you added, or if you are the creator of this UTub
        critical_log(
            f"User={current_user.id} tried removing UTubURL.id={utub_url_id} from UTub.id={utub_id} and they aren't the URL adder or UTub creator"
        )

        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_DELETE_URL,
                }
            ),
            403,
        )


def update_tag_counts_on_url_delete(
    current_utub_url: Utub_Urls, current_utub: Utubs
) -> dict[int, int]:
    """
    Update tag usage counts when deleting a URL and remove all associated tag relationships.

    Retrieves all tags associated with the URL being deleted, removes the tag associations
    from the database, and calculates updated tag counts for the UTub. This ensures tag
    counts accurately reflect the removal of the URL.

    Args:
        current_utub_url (Utub_Urls): The Utub_Urls object representing the URL being deleted.
        current_utub (Utubs): The UTub object from which the URL is being removed.

    Returns:
        dict[int, int]: A dictionary mapping tag IDs to their updated counts (decremented by 1)
        for all tags that were associated with the deleted URL.
    """
    # Find all rows corresponding to tags on the URL to be deleted in current UTub
    utub_url_tag_ids, utub_tag_ids = get_utub_url_tag_ids_and_utub_tag_ids_on_utub_url(
        utub_id=current_utub.id, utub_url_id=current_utub_url.id
    )

    # Count instances of tags in UTub that were unique to the URL to be deleted
    tag_ids_and_count = get_utub_url_tag_ids_and_count_in_utub(
        utub_id=current_utub.id, utub_tag_ids=utub_tag_ids
    )

    # Remove all tags associated with this URL in this UTub
    db.session.query(Utub_Url_Tags).filter(Utub_Url_Tags.id.in_(utub_url_tag_ids)).delete()  # type: ignore

    # Update utub tag count after successful removal of all tags associated with deleted URL
    return {t[0]: t[1] - 1 for t in tag_ids_and_count}


def handle_invalid_url_form_input(
    utub_new_url_form: NewURLForm,
) -> tuple[Response, int]:
    """
    Handle invalid form input when adding a new URL to a UTub.

    Logs validation errors and returns an appropriate error response with form field errors
    or a generic failure message if form validation passes but something else fails.

    Args:
        utub_new_url_form (NewURLForm): The form object containing URL input data and validation errors.

    Returns:
        tuple[Response, int]: A tuple containing:
        - Response: JSON response with error details and status
        - int: HTTP status code (400 for form errors, 404 for unknown errors)
    """
    # Invalid form input
    if utub_new_url_form.errors is not None:
        errors = cast(dict[str, list[str]], utub_new_url_form.errors)
        warning_log(
            f"User={current_user.id} | Invalid form: {turn_form_into_str_for_log(errors)}"
        )
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_ADD_URL_FORM,
                    STD_JSON.ERROR_CODE: URLErrorCodes.INVALID_FORM_INPUT,
                    STD_JSON.ERRORS: build_form_errors(utub_new_url_form),
                }
            ),
            400,
        )

    # Something else went wrong
    critical_log("Unable to add URL to UTub")
    return (
        jsonify(
            {
                STD_JSON.STATUS: STD_JSON.FAILURE,
                STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_ADD_URL,
                STD_JSON.ERROR_CODE: URLErrorCodes.UNKNOWN_ERROR,
            }
        ),
        404,
    )


def handle_url_with_credentials_error(
    start_time: float, exception: URLWithCredentialsError
) -> tuple[Response, int]:
    """
    Handle the case where a URL containing credentials (username/password) is detected.

    Logs the security violation with timing information and returns an error response
    indicating that URLs with credentials are not allowed.

    Args:
        start_time (float): The timestamp when URL processing began (from time.perf_counter()).
        exception (URLWithCredentialsError): The exception raised when credentials were detected.

    Returns:
        tuple[Response, int]: A tuple containing:
        - Response: JSON response with error message and details
        - int: HTTP status code 400
    """
    end = (time.perf_counter() - start_time) * 1000
    request_id = safe_get_request_id()
    warning_log(
        f"[{request_id}] URL with crendentials passed by User={current_user.id}\n"
        + f"[{request_id}] Took {end:.3f} ms to fail validation\n"
        + f"[{request_id}] Exception={str(exception)}"
    )

    return (
        jsonify(
            {
                STD_JSON.STATUS: STD_JSON.FAILURE,
                STD_JSON.MESSAGE: URL_FAILURE.URLS_WITH_CREDENTIALS_EXCEPTION,
                STD_JSON.DETAILS: str(exception),
                STD_JSON.ERROR_CODE: URLErrorCodes.URL_WITH_CREDENTIALS_ERROR,
            }
        ),
        400,
    )


def handle_invalid_url_error(
    start_time: float, url_string: str | None, exception: InvalidURLError
) -> tuple[Response, int]:
    """
    Handle validation errors for malformed or invalid URLs.

    Logs the validation failure with timing information and returns an error response
    with details about why the URL failed validation.

    Args:
        start_time (float): The timestamp when URL processing began (from time.perf_counter()).
        url_string (str | None): The URL string that failed validation.
        exception (InvalidURLError): The exception raised during URL validation.

    Returns:
        tuple[Response, int]: A tuple containing:
        - Response: JSON response with error message and exception details
        - int: HTTP status code 400
    """
    end = (time.perf_counter() - start_time) * 1000
    request_id = safe_get_request_id()

    warning_log(
        f"[{request_id}] Unable to validate the URL given by User={current_user.id}\n"
        + f"[{request_id}] Took {end:.3f} ms to fail validation\n"
        + f"[{request_id}] url_string={url_string}\n"
        + f"[{request_id}] Exception={str(exception)}"
    )

    return (
        jsonify(
            {
                STD_JSON.STATUS: STD_JSON.FAILURE,
                STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_VALIDATE_THIS_URL,
                STD_JSON.DETAILS: str(exception),
                STD_JSON.ERROR_CODE: URLErrorCodes.INVALID_URL_ERROR,
            }
        ),
        400,
    )


def handle_unexpected_url_validation_error(
    start_time: float, url_string: str | None, exception: AdaUrlParsingError | Exception
) -> tuple[Response, int]:
    """
    Handle unexpected exceptions that occur during URL validation.

    Logs critical error information, sends a notification about the unexpected failure,
    and returns an error response. This is for catching unanticipated validation errors
    that don't fall into known error categories.

    Args:
        start_time (float): The timestamp when URL processing began (from time.perf_counter()).
        url_string (str | None): The URL string being validated when the error occurred.
        exception (AdaUrlParsingError | Exception): The unexpected exception that was raised.

    Returns:
        tuple[Response, int]: A tuple containing:
        - Response: JSON response with error message and exception details
        - int: HTTP status code 400
    """
    end = (time.perf_counter() - start_time) * 1000
    request_id = safe_get_request_id()

    critical_log(
        f"[{request_id}] Unexpected exception validating the URL given by User={current_user.id}\n"
        + f"[{request_id}] Took {end:.3f} ms to fail validation\n"
        + f"[{request_id}] url_string={url_string}\n"
        + f"[{request_id}] Exception={str(exception)}"
    )
    notification_sender = safe_get_notif_sender(current_app)
    notification_sender.send_notification(
        f"Unexpected exception validating {url_string} | Exception={str(exception)}"
    )

    return (
        jsonify(
            {
                STD_JSON.STATUS: STD_JSON.FAILURE,
                STD_JSON.MESSAGE: URL_FAILURE.UNEXPECTED_VALIDATION_EXCEPTION,
                STD_JSON.DETAILS: str(exception),
                STD_JSON.ERROR_CODE: URLErrorCodes.UNEXPECTED_VALIDATION_ERROR,
            }
        ),
        400,
    )


def get_or_create_url(url_string: str) -> tuple[int, URLState]:
    """
    Retrieve an existing URL from the database or create a new one if it doesn't exist.

    Checks if the normalized URL string already exists in the database. If found, returns
    its ID and EXISTING_URL state. Otherwise, creates a new URL entry, commits it to the
    database, and returns its ID with FRESH_URL state.

    Args:
        url_string (str): The normalized URL string to look up or create.

    Returns:
        tuple[int, URLState]: A tuple containing:
        - int: The database ID of the URL (existing or newly created)
        - URLState: Either URLState.EXISTING_URL or URLState.FRESH_URL
    """
    already_created_url: Urls = Urls.query.filter(Urls.url_string == url_string).first()

    if already_created_url:
        return already_created_url.id, URLState.EXISTING_URL

    new_url = Urls(
        normalized_url=url_string,
        current_user_id=current_user.id,
    )

    # Commit new URL to the database
    db.session.add(new_url)
    db.session.commit()
    safe_add_log(f"Added new URL, URL.id={new_url.id}")

    return new_url.id, URLState.FRESH_URL


def check_url_already_in_utub(
    utub_id: int, url_id: int, url_string: str
) -> tuple[Response, int] | None:
    """
    Check if a URL is already associated with a specific UTub.

    Queries the database to determine if the URL-UTub association already exists. If it does,
    logs a warning and returns a conflict error response. Otherwise, returns None to indicate
    the URL can be added to the UTub.

    Args:
        utub_id (int): The ID of the UTub to check.
        url_id (int): The ID of the URL to check.
        url_string (str): The URL string for error response purposes.

    Returns:
        tuple[Response, int] | None: If the URL already exists in the UTub, returns:
        - Response: JSON response indicating the URL is already in the UTub
        - int: HTTP status code 409 (Conflict)
        If the URL is not in the UTub, returns None.
    """
    utub_url = Utub_Urls.query.filter(
        Utub_Urls.utub_id == utub_id, Utub_Urls.url_id == url_id
    ).first()
    safe_add_log(f"URL already exists in U4I, URL.id={url_id}")

    if not utub_url:
        return

    warning_log(
        f"User={current_user.id} tried adding URL.id={url_id} but already exists in UTub.id={utub_id}"
    )

    return (
        jsonify(
            {
                STD_JSON.STATUS: STD_JSON.FAILURE,
                STD_JSON.MESSAGE: URL_FAILURE.URL_IN_UTUB,
                STD_JSON.ERROR_CODE: URLErrorCodes.URL_ALREADY_IN_UTUB_ERROR,
                URL_FAILURE.URL_STRING: url_string,
            }
        ),
        409,
    )


def associate_url_with_utub(
    current_utub: Utubs,
    url_id: int,
    url_title: str,
    url_string: str,
    url_state: URLState,
) -> tuple[Response, int]:
    """
    Create an association between a URL and a UTub, adding the URL to the UTub.

    Creates a new Utub_Urls entry linking the URL to the UTub with the specified title,
    updates the UTub's last modified timestamp, and commits the changes to the database.

    Args:
        current_utub (Utubs): The UTub object to associate the URL with.
        url_id (int): The database ID of the URL to add.
        url_title (str): The title to display for this URL in the UTub.
        url_string (str): The URL string for the success response.
        url_state (URLState): Whether this is a newly created or existing URL.

    Returns:
        tuple[Response, int]: A tuple containing:
        - Response: JSON response with success message and URL details
        - int: HTTP status code 200
    """
    url_utub_user_add = Utub_Urls(
        utub_id=current_utub.id,
        url_id=url_id,
        user_id=current_user.id,
        url_title=url_title,
    )
    db.session.add(url_utub_user_add)
    current_utub.set_last_updated()
    db.session.commit()

    # Successfully added a URL, and associated it to a UTub
    safe_add_many_logs(
        ["Added URL to UTub", f"UTub.id={current_utub.id}", f"URL.id={url_id}"]
    )
    return (
        jsonify(
            {
                STD_JSON.STATUS: STD_JSON.SUCCESS,
                STD_JSON.MESSAGE: (
                    URL_SUCCESS.URL_CREATED_ADDED
                    if url_state == URLState.FRESH_URL
                    else URL_SUCCESS.URL_ADDED
                ),
                URL_SUCCESS.UTUB_ID: current_utub.id,
                URL_SUCCESS.ADDED_BY: current_user.id,
                URL_SUCCESS.URL: {
                    URL_SUCCESS.URL_STRING: url_string,
                    URL_SUCCESS.UTUB_URL_ID: url_utub_user_add.id,
                    URL_SUCCESS.URL_TITLE: url_title,
                },
            }
        ),
        200,
    )


def normalize_and_validate_url(url_string: str | None) -> str | tuple[Response, int]:
    """
    Normalize and validate a URL string using the application's URL validator.

    Performs normalization to standardize the URL format, then validates it for correctness
    and security issues. Logs timing information for performance monitoring and handles
    various types of validation errors appropriately.

    Args:
        url_string (str | None): The URL string to normalize and validate.

    Returns:
        str | tuple[Response, int]: On success, returns the validated URL string.
        On failure, returns a tuple containing:
        - Response: JSON response with error details
        - int: HTTP status code 400
    """
    start = time.perf_counter()
    url_validator = safe_get_url_validator(current_app)

    try:
        normalized_url = url_validator.normalize_url(url_string)

        normalized_time = (time.perf_counter() - start) * 1000

        validated_ada_url = url_validator.validate_url(normalized_url)

        validation_time = (time.perf_counter() - start) * 1000

    except URLWithCredentialsError as e:
        return handle_url_with_credentials_error(start, e)

    except InvalidURLError as e:
        return handle_invalid_url_error(start, url_string, e)

    except (AdaUrlParsingError, Exception) as e:
        return handle_unexpected_url_validation_error(start, url_string, e)

    end = (time.perf_counter() - start) * 1000
    safe_add_many_logs(
        [
            f"Finished checks for {url_string=}",
            f"Took {normalized_time:.3f} ms for normalization",
            f"Took {(validation_time - normalized_time):.3f} ms total for validation",
            f"Took {end:.3f} ms total",
        ]
    )
    return validated_ada_url
