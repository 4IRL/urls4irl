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
from src.models.utub_tags import Utub_Tags
from src.models.utub_url_tags import Utub_Url_Tags
from src.models.utub_urls import Utub_Urls
from src.models.utubs import Utubs
from src.tags.constants import URLTagErrorCodes
from src.tags.forms import NewTagForm
from src.utils.constants import TAG_CONSTANTS
from src.utils.strings.model_strs import MODELS
from src.utils.strings.tag_strs import TAGS_FAILURE, TAGS_SUCCESS


def handle_invalid_form_input_for_create_url_tag(
    url_tag_form: NewTagForm, utub_url: Utub_Urls
) -> FlaskResponse:
    """
    Handles invalid form inputs or unknown exceptions when a URL Tag is being added.

    Args:
        url_tag_form (NewTagForm): Form containing new URL Tag data
        utub_url (Utub_Urls): The UTub URL object that the tag is being added to

    Returns:
        tuple[Response, int]:
        - Response: JSON response on error.
        - int: HTTP status code 400 (Invalid Form) / 404 (Unknown exception)
    """
    if url_tag_form.errors is not None:
        errors = {MODELS.TAG_STRING: url_tag_form.tag_string.errors}
        warning_log(
            f"User={current_user.id} | Invalid form: {turn_form_into_str_for_log(url_tag_form.errors)}"  # type: ignore
        )
        return APIResponse(
            status_code=400,
            message=TAGS_FAILURE.UNABLE_TO_ADD_TAG_TO_URL,
            error_code=URLTagErrorCodes.INVALID_FORM_INPUT,
            errors=errors,
        ).to_response()

    critical_log(
        f"User={current_user.id} failed to add tag to UTubURL.id={utub_url.id} in UTub.id={utub_url.utub_id}"
    )
    return APIResponse(
        status_code=404,
        message=TAGS_FAILURE.UNABLE_TO_ADD_TAG_TO_URL,
        error_code=URLTagErrorCodes.UNKNOWN_EXCEPTION,
    ).to_response()


def add_tag_to_url_if_valid(
    url_tag_form: NewTagForm, utub: Utubs, utub_url: Utub_Urls
) -> FlaskResponse:
    """
    Adds a tag to a URL, but only if the URL does not already have the maximum number of tags, and if the URL does not have the tag already on it.

    Args:
        url_tag_form (NewTagForm): The form containing the tag string to add to the URL
        utub (Utubs): The UTub containing the URL and tag to add
        utub_url (Utub_Urls): The URL having a tag being added to

    Returns:
        tuple[Response, int]:
        - Response: JSON response on with success or error details.
        - int: HTTP status code
            200 (success)
            400 (at tag limit)
            400 (tag already on URL)
    """
    tag_to_add = url_tag_form.tag_string.get()

    if _url_is_at_url_tag_limit(utub, utub_url):
        return _build_url_at_tag_limit_response(utub_url)

    utub_tag = _get_or_create_utub_tag(tag_to_add, utub)

    if _tag_is_already_on_url(utub_tag, utub_url):
        return _build_tag_already_on_url_response(utub_url, utub_tag)

    utub_url_tag = _add_url_tag(utub_url, utub_tag)

    # Count instances of particular tag in UTub that is to be deleted
    updated_tag_id_count = get_count_of_url_tag_in_utub(utub_tag)

    utub.set_last_updated()
    db.session.commit()

    # Successfully added tag to URL on UTub
    safe_add_many_logs(
        [
            "Added new UTubURLTag",
            f"UTub.id={utub.id}",
            f"UTubURL.id={utub_url.id}",
            f"UTubTag.id={utub_tag.id}",
            f"UTubTag.tag_string={utub_tag.tag_string}",
            f"UTubURLTag.id={utub_url_tag.id}",
        ]
    )

    return APIResponse(
        message=TAGS_SUCCESS.TAG_ADDED_TO_URL,
        data={
            TAGS_SUCCESS.UTUB_URL_TAG_IDS: utub_url.associated_tag_ids,
            TAGS_SUCCESS.UTUB_TAG: utub_tag.serialized_on_add_delete,
            TAGS_SUCCESS.TAG_COUNTS_MODIFIED: updated_tag_id_count,
        },
    ).to_response()


def _url_is_at_url_tag_limit(utub: Utubs, utub_url: Utub_Urls) -> bool:
    """
    Checks if the given UTub URL is already at the limit of available tags.

    Args:
        utub (Utubs): The UTub of the URL with tags on it to check
        utub_url (Utub_Urls): The URL with the tag being added

    Returns:
        (bool): True if the URL is at/above the tag limit
    """
    tags_already_on_this_url: list[Utub_Url_Tags] = Utub_Url_Tags.query.filter(
        Utub_Url_Tags.utub_id == utub.id, Utub_Url_Tags.utub_url_id == utub_url.id
    ).all()

    return len(tags_already_on_this_url) >= TAG_CONSTANTS.MAX_URL_TAGS


def _build_url_at_tag_limit_response(utub_url: Utub_Urls) -> FlaskResponse:
    """
        Builds JSON response for when a URL is at the tag limit

        Args:
            utub_url (Utub_Urls): The URL at the tag limit

    Returns:
            tuple[Response, int]:
            - Response: JSON response on error.
            - int: HTTP status code 400
    """
    warning_log(
        f"User={current_user.id} tried adding tag to UTubURL.id={utub_url.id} but tag limited"
    )
    return APIResponse(
        status_code=400,
        message=TAGS_FAILURE.FIVE_TAGS_MAX,
    ).to_response()


def _get_or_create_utub_tag(tag: str, utub: Utubs) -> Utub_Tags:
    """
    Gets the UTub Tag with the given string, or builds it if it doesn't exist.

    Args:
        tag (str): The tag string to add or get
        utub (Utubs): The UTub containing the tag

    Returns:
        (Utub_Tags): The tag object in the UTub
    """
    utub_tag: Utub_Tags = Utub_Tags.query.filter(
        Utub_Tags.utub_id == utub.id, Utub_Tags.tag_string == tag
    ).first()

    if not utub_tag:
        # Create tag, then associate with this UTub and URL
        utub_tag = Utub_Tags(
            utub_id=utub.id, tag_string=tag, created_by=current_user.id
        )
        db.session.add(utub_tag)
        db.session.commit()

        safe_add_log(f"Added new UTubTag with UTubTag.id={utub_tag.id}")

    return utub_tag


def _tag_is_already_on_url(utub_tag: Utub_Tags, utub_url: Utub_Urls) -> bool:
    """
    Checks if the given UTub Tag is already on the given UTub URL.

    Args:
        utub_tag (Utub_Tags): The UTub tag that may or may not be on the UTub URL
        utub_url (Utub_Urls): The UTub URL that may or may not contain the UTub tag

    Returns:
        (bool): True if the UTub Tag is already associated with the UTub URL
    """
    return utub_tag.id in utub_url.associated_tag_ids


def _build_tag_already_on_url_response(
    utub_url: Utub_Urls, utub_tag: Utub_Tags
) -> FlaskResponse:
    """
    Builds JSON response for when a UTub URL already contains a given tag.

    Args:
        utub_url (Utub_Urls): The URL already containing the given UTub Tag
        utub_tag (Utub_Tags): The tag already on the URL

    Returns:
        tuple[Response, int]:
        - Response: JSON response on error.
        - int: HTTP status code 400
    """
    warning_log(
        f"User={current_user.id} tried adding UTubTag.tag_string={utub_tag.tag_string} to UTubURL.id={utub_url.id} but already on UTubURL"
    )
    return APIResponse(
        status_code=400,
        message=TAGS_FAILURE.TAG_ALREADY_ON_URL,
    ).to_response()


def _add_url_tag(utub_url: Utub_Urls, utub_tag: Utub_Tags) -> Utub_Url_Tags:
    """
    Adds a UTub tag to a given UTub URL.

    Args:
        utub_url (Utub_Urls): The UTub URL that has a tag being added to it
        utub_tag (Utub_Tags): The UTub Tag to add to the URL

    Returns:
        (Utub_Url_Tags): The newly created URL Tag
    """
    utub_url_tag = Utub_Url_Tags(
        utub_id=utub_url.utub_id, utub_url_id=utub_url.id, utub_tag_id=utub_tag.id
    )

    db.session.add(utub_url_tag)

    return utub_url_tag


def get_count_of_url_tag_in_utub(utub_tag: Utub_Tags) -> int:
    """
    Counts the number of URL Tags for a given UTub tag in a UTub.

    Args:
        utub_tag (Utub_Tags): The tag to check for in the UTub

    Returns:
        (int): The number of URL tags for this UTub Tag
    """
    return Utub_Url_Tags.query.filter(
        Utub_Url_Tags.utub_id == utub_tag.utub_id,
        Utub_Url_Tags.utub_tag_id == utub_tag.id,
    ).count()
