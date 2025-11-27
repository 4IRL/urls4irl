from flask_login import current_user

from src import db
from src.api_common.responses import APIResponse, FlaskResponse
from src.app_logger import (
    critical_log,
    safe_add_many_logs,
    turn_form_into_str_for_log,
    warning_log,
)
from src.models.utub_tags import Utub_Tags
from src.models.utubs import Utubs
from src.tags.constants import UTubTagErrorCodes
from src.tags.forms import NewTagForm
from src.utils.strings.model_strs import MODELS
from src.utils.strings.tag_strs import TAGS_FAILURE, TAGS_SUCCESS


def handle_invalid_form_input_for_create_utub_tag(
    utub_tag_form: NewTagForm, current_utub: Utubs
) -> FlaskResponse:
    """
    Handles an invalid form input or unknown exception when creating a new UTub Tag.

    Args:
        utub_tag_form (NewTagForm): Form containing new UTub Tag data
        current_utub (Utubs): The UTub object that the tag is being added to

    Returns:
        tuple[Response, int]:
        - Response: JSON response with error message and details
        - int: HTTP status code 400 (Invalid input) / 404 (Unknown exception)
    """
    if utub_tag_form.errors is not None:
        warning_log(
            f"User={current_user.id} | Invalid form: {turn_form_into_str_for_log(utub_tag_form.errors)}"  # type: ignore
        )

        return APIResponse(
            status_code=400,
            message=TAGS_FAILURE.UNABLE_TO_ADD_TAG_TO_UTUB,
            error_code=UTubTagErrorCodes.INVALID_FORM_INPUT,
            errors={MODELS.TAG_STRING: utub_tag_form.tag_string.errors},
        ).to_response()

    critical_log(
        f"User={current_user.id} failed to add UTubTag to UTub.id={current_utub.id}"
    )
    return APIResponse(
        status_code=404,
        message=TAGS_FAILURE.UNABLE_TO_ADD_TAG_TO_UTUB,
        error_code=UTubTagErrorCodes.UNKNOWN_EXCEPTION,
    ).to_response()


def create_tag_in_utub(utub_tag_form: NewTagForm, current_utub: Utubs) -> FlaskResponse:
    """
    Handles creating a new UTub tag in a UTub, not necessarily associated with a URL.
    Verifies that the tag is not already in the UTub.

    Args:
        utub_tag_form (NewTagForm): Form containing new UTub Tag data
        current_utub (Utubs): The UTub object that the tag is being added to

    Returns:
        tuple[Response, int]:
        - Response: JSON response on success or duplicate UTub tag.
        - int: HTTP status code 200 (Success) / 400 (Duplicate UTub tag)
    """
    tag_to_add = utub_tag_form.tag_string.get()

    is_duplicate_utub_tag = _check_if_duplicate_utub_tag(tag_to_add, current_utub)

    if is_duplicate_utub_tag:
        return APIResponse(
            status_code=400,
            message=TAGS_FAILURE.TAG_ALREADY_IN_UTUB,
        ).to_response()

    return _create_new_utub_tag(tag_to_add, current_utub)


def _check_if_duplicate_utub_tag(tag: str, utub: Utubs) -> bool:
    """
    Checks if the tag string is already a tag in this UTub.

    Args:
        tag (str): The tag string checking for a duplicate
        utub (Utubs): The UTub being checked for a duplicate tag

    Returns:
        tuple[Response, int]:
        - Response: JSON response on duplicate UTub tag
        - int: HTTP status code 400 (Duplicate tag)
        None: If the tag is not a duplicate
    """
    utub_tag_already_created: Utub_Tags = Utub_Tags.query.filter(
        Utub_Tags.utub_id == utub.id, Utub_Tags.tag_string == tag
    ).first()

    if utub_tag_already_created:
        warning_log(
            f"User={current_user.id} tried adding UTubTag.tag_string={tag} but UTubTag already exists in UTub.id={utub.id}"
        )

    return utub_tag_already_created


def _create_new_utub_tag(tag: str, utub: Utubs) -> FlaskResponse:
    """
    Creates a new UTub tag and associates it with the UTub.

    Args:
        tag (str): The tag string being added to the UTub
        utub (Utubs): The UTub being added to

    Returns:
        tuple[Response, int]:
        - Response: JSON response on successful UTub tag ad
        - int: HTTP status code 200

    """
    new_utub_tag = Utub_Tags(
        utub_id=utub.id, tag_string=tag, created_by=current_user.id
    )
    db.session.add(new_utub_tag)
    utub.set_last_updated()
    db.session.commit()

    # Successfully added tag to UTub
    safe_add_many_logs(
        [
            "Added UTubTag",
            f"UTub.id={utub.id}",
            f"UTubTag.id={new_utub_tag.id}",
            f"UTubTag.tag_string={tag}",
        ]
    )
    return APIResponse(
        message=TAGS_SUCCESS.TAG_ADDED_TO_UTUB,
        data={
            TAGS_SUCCESS.UTUB_TAG: new_utub_tag.serialized_on_add_delete,
            TAGS_SUCCESS.TAG_COUNTS_MODIFIED: 0,  # No URLs associated yet
        },
    ).to_response()
