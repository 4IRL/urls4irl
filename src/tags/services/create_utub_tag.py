from flask import Response, jsonify
from flask_login import current_user

from src import db
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
from src.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from src.utils.strings.tag_strs import TAGS_FAILURE, TAGS_SUCCESS


def handle_invalid_form_input_for_create_utub_tag(
    utub_tag_form: NewTagForm, current_utub: Utubs
) -> tuple[Response, int]:
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
        errors = {MODELS.TAG_STRING: utub_tag_form.tag_string.errors}
        warning_log(
            f"User={current_user.id} | Invalid form: {turn_form_into_str_for_log(utub_tag_form.errors)}"  # type: ignore
        )
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: TAGS_FAILURE.UNABLE_TO_ADD_TAG_TO_UTUB,
                    STD_JSON.ERROR_CODE: UTubTagErrorCodes.INVALID_FORM_INPUT,
                    STD_JSON.ERRORS: errors,
                }
            ),
            400,
        )

    critical_log(
        f"User={current_user.id} failed to add UTubTag to UTub.id={current_utub.id}"
    )
    return (
        jsonify(
            {
                STD_JSON.STATUS: STD_JSON.FAILURE,
                STD_JSON.MESSAGE: TAGS_FAILURE.UNABLE_TO_ADD_TAG_TO_UTUB,
                STD_JSON.ERROR_CODE: UTubTagErrorCodes.UNKNOWN_EXCEPTION,
            }
        ),
        404,
    )


def create_tag_in_utub(
    utub_tag_form: NewTagForm, current_utub: Utubs
) -> tuple[Response, int]:
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

    duplicate_utub_tag_response = _check_if_duplicate_utub_tag_response(
        tag_to_add, current_utub
    )
    if duplicate_utub_tag_response is not None:
        return duplicate_utub_tag_response

    return _create_new_utub_tag(tag_to_add, current_utub)


def _check_if_duplicate_utub_tag_response(
    tag: str, utub: Utubs
) -> tuple[Response, int] | None:
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
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: TAGS_FAILURE.TAG_ALREADY_IN_UTUB,
                }
            ),
            400,
        )


def _create_new_utub_tag(tag: str, utub: Utubs) -> tuple[Response, int]:
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
    return (
        jsonify(
            {
                STD_JSON.STATUS: STD_JSON.SUCCESS,
                STD_JSON.MESSAGE: TAGS_SUCCESS.TAG_ADDED_TO_UTUB,
                TAGS_SUCCESS.UTUB_TAG: new_utub_tag.serialized_on_add_delete,
                TAGS_SUCCESS.TAG_COUNTS_MODIFIED: 0,  # No URLs associated yet
            },
        ),
        200,
    )
