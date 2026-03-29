from flask_login import current_user

from backend import db
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.app_logger import (
    safe_add_many_logs,
    warning_log,
)
from backend.models.utub_tags import Utub_Tags
from backend.models.utubs import Utubs
from backend.schemas.errors import build_message_error_response
from backend.schemas.tags import (
    UtubTagAddedToUtubResponseSchema,
    UtubTagOnAddDeleteSchema,
)
from backend.utils.strings.tag_strs import TAGS_FAILURE, TAGS_SUCCESS


def create_tag_in_utub(tag_string: str, current_utub: Utubs) -> FlaskResponse:
    """
    Handles creating a new UTub tag in a UTub, not necessarily associated with a URL.
    Verifies that the tag is not already in the UTub.

    Args:
        tag_string (str): The tag string to add to the UTub
        current_utub (Utubs): The UTub object that the tag is being added to

    Returns:
        tuple[Response, int]:
        - Response: JSON response on success or duplicate UTub tag.
        - int: HTTP status code 200 (Success) / 400 (Duplicate UTub tag)
    """
    tag_to_add = tag_string.strip()

    is_duplicate_utub_tag = _check_if_duplicate_utub_tag(tag_to_add, current_utub)

    if is_duplicate_utub_tag:
        return build_message_error_response(message=TAGS_FAILURE.TAG_ALREADY_IN_UTUB)

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
        data=UtubTagAddedToUtubResponseSchema(
            utub_tag=UtubTagOnAddDeleteSchema.from_orm_tag(new_utub_tag),
            tag_counts_modified=0,
        ),
    ).to_response()
