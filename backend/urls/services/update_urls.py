from flask import current_app
from flask_login import current_user
from backend import db
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.app_logger import safe_add_many_logs, warning_log
from backend.extensions.extension_utils import safe_get_url_validator
from backend.extensions.metrics.writer import record_event
from backend.metrics.events import EventName
from backend.models.urls import Urls
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.schemas.errors import (
    build_message_error_response,
    build_url_conflict_error_response,
)
from backend.schemas.urls import (
    UrlTitleUpdatedResponseSchema,
    UrlUpdatedResponseSchema,
    UtubUrlDetailSchema,
)
from backend.urls.constants import URLErrorCodes, URLState
from backend.urls.services.create_urls import (
    build_response_for_invalidated_url,
    validate_new_url_for_utub,
)
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.url_strs import URL_FAILURE, URL_NO_CHANGE, URL_SUCCESS
from backend.utubs.guards import reject_if_utub_locked


def update_url_in_utub(
    url_string: str, current_utub: Utubs, current_utub_url: Utub_Urls
) -> FlaskResponse:
    """
    Updates the given Utub_Urls in the UTub.

    Args:
        url_string (str): The new URL string to update to
        current_utub (Utubs): The UTub object containing the UTub_Urls
        current_utub_url (Utub_Urls): The UTub_Urls object to update.

    Returns:
        tuple[Response, int]:
        - Response: JSON response on update
        - int: HTTP status code 200 (Success)
    """
    utub_locked_error: FlaskResponse | None = reject_if_utub_locked(
        current_utub, error_code=URLErrorCodes.UTUB_IS_LOCKED
    )
    if utub_locked_error is not None:
        return utub_locked_error

    url_to_change_to: str = url_string.strip()

    had_tracking: bool = safe_get_url_validator(current_app).contains_tracking_params(
        url_to_change_to
    )

    # Check for empty URL string to update to
    is_empty_url = _check_for_empty_url_string_on_update(
        url_to_change_to, current_utub_url.id
    )

    if is_empty_url:
        return build_message_error_response(
            message=URL_FAILURE.EMPTY_URL,
            error_code=URLErrorCodes.EMPTY_URL,
        )

    # Validate (and strip tracking params from) the new URL before any
    # equivalence comparison, so the stored stripped form is compared against
    # the stripped candidate rather than the raw input.
    validated_new_url = validate_new_url_for_utub(url_to_change_to, current_utub.id)
    if (
        validated_new_url.url_state == URLState.INVALID_URL_STRING
        or validated_new_url.url is None
    ):
        return build_response_for_invalidated_url(validated_new_url.normalized_url)

    validated_url_string: str = validated_new_url.normalized_url.validated_url

    # Check for updating the URL to the same (stripped) URL
    is_equivalent_url = _check_for_equivalent_url_on_update(
        validated_url_string, current_utub_url
    )

    if is_equivalent_url:
        return APIResponse(
            status=STD_JSON.NO_CHANGE,
            message=URL_NO_CHANGE.URL_NOT_MODIFIED,
            data=UrlTitleUpdatedResponseSchema(
                url=UtubUrlDetailSchema.from_orm_url(current_utub_url)
            ),
        ).to_response()

    if validated_new_url.url_state == URLState.EXISTING_URL_IN_UTUB:
        assert validated_new_url.url is not None
        warning_log(
            f"User={current_user.id} tried adding URL.id={validated_new_url.url.id} but already exists in UTub.id={current_utub.id}"
        )
        message = (
            URL_FAILURE.URL_IN_UTUB_TRACKING_PARAMS_STRIPPED
            if had_tracking
            else URL_FAILURE.URL_IN_UTUB
        )
        return build_url_conflict_error_response(
            message=message,
            url_string=validated_new_url.url.url_string,
            error_code=URLErrorCodes.URL_ALREADY_IN_UTUB_ERROR,
        )

    return _associate_updated_url_with_utub(
        url=validated_new_url.url,
        current_utub=current_utub,
        current_utub_url=current_utub_url,
        had_tracking=had_tracking,
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
    validated_url_string: str, current_utub_url: Utub_Urls
) -> bool:
    """
    Checks if the provided URL to update to is equivalent to the current URL.

    Args:
        validated_url_string (str): The stripped, validated URL string to compare against the stored URL.
        current_utub_url (Utub_Urls): The UTub URL whose stored URL string is compared against.

    Returns:
        (bool): True if url string is equivalent to given URL
    """

    is_equivalent_url = (
        validated_url_string == current_utub_url.standalone_url.url_string
    )

    if is_equivalent_url:
        warning_log(
            f"User={current_user.id} tried changing UTubURL.id={current_utub_url.id} to the same URL"
        )
    return is_equivalent_url


def _associate_updated_url_with_utub(
    url: Urls,
    current_utub: Utubs,
    current_utub_url: Utub_Urls,
    had_tracking: bool = False,
) -> FlaskResponse:
    """
    Associates the updated UTub_Url with the UTub.

    Args:
        url (Urls): The URL being updated
        current_utub (Utubs): The UTub object containing the UTub_Urls
        current_utub_url (Utub_Urls): The UTub_Urls object to update the title for.
        had_tracking (bool): Whether the raw input URL carried tracking query
            params that were stripped before storage. Recorded as the
            `stripped` dimension on the URL_TRACKING_PARAMS_STRIPPED event.

    Returns:
        tuple[Response, int]:
        - Response: JSON response on update
        - int: HTTP status code 200 (Success)
    """
    # Now set the URL ID for the old URL to the new URL
    current_utub_url.url_id = url.id
    current_utub_url.standalone_url = url

    current_utub.set_last_updated()
    db.session.commit()

    record_event(EventName.URL_STRING_UPDATED)
    record_event(
        EventName.URL_TRACKING_PARAMS_STRIPPED,
        dimensions={"stripped": "true" if had_tracking else "false"},
    )

    safe_add_many_logs(
        ["Added URL to UTub", f"UTub.id={current_utub.id}", f"URL.id={url.id}"]
    )

    return APIResponse(
        message=URL_SUCCESS.URL_MODIFIED,
        data=UrlUpdatedResponseSchema(
            utub_id=current_utub.id,
            utub_name=current_utub.name,
            url=UtubUrlDetailSchema.from_orm_url(current_utub_url),
        ),
    ).to_response()
