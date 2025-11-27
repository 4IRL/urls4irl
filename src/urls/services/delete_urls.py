from flask_login import current_user
from sqlalchemy import case, func

from src import db
from src.api_common.request_utils import is_adder_of_utub_url, is_current_utub_creator
from src.api_common.responses import APIResponse, FlaskResponse
from src.app_logger import critical_log, safe_add_many_logs
from src.models.utub_url_tags import Utub_Url_Tags
from src.models.utub_urls import Utub_Urls
from src.models.utubs import Utubs
from src.utils.strings.url_strs import URL_SUCCESS


def check_if_is_url_adder_or_utub_creator_on_url_delete(
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
        (bool): True if is URL adder or creator
        tuple[Response, int] | None: If the user lacks permission, returns:
        - Response: JSON response indicating deletion is not allowed
        - int: HTTP status code 403 (Forbidden)
        If the user has permission, returns None to allow deletion to proceed.
    """
    is_utub_creator_or_adder_of_utub_url = (
        is_current_utub_creator() or is_adder_of_utub_url()
    )
    if not is_utub_creator_or_adder_of_utub_url:
        # Can only remove URLs you added, or if you are the creator of this UTub
        critical_log(
            f"User={current_user.id} tried removing UTubURL.id={utub_url_id} from UTub.id={utub_id} and they aren't the URL adder or UTub creator"
        )

    return is_utub_creator_or_adder_of_utub_url


def delete_url_in_utub(
    current_utub: Utubs,
    current_utub_url: Utub_Urls,
) -> FlaskResponse:
    """
    Deletes a URL from a UTub. Returns associated tag data for the UTub.

    Args:
        current_utub (Utubs): The UTub object containing the UTub_Urls
        current_utub_url (Utub_Urls): The Utub_Urls to delete

    Returns:
        tuple[Response, int]:
        - Response: JSON response on delete
        - int: HTTP status code 200 (Success)
    """
    # Store serialized data from URL association with UTub and associated tags
    url_string_to_remove = current_utub_url.standalone_url.url_string
    url_id_to_remove = current_utub_url.standalone_url.id
    utub_url_id = current_utub_url.id

    tag_ids_and_updated_count = _update_tag_counts_on_url_delete(
        current_utub_url, current_utub
    )

    db.session.delete(current_utub_url)
    current_utub.set_last_updated()

    db.session.commit()

    safe_add_many_logs(
        [
            "Deleted UTubURL and associated UTubURLTags",
            f"User.id={current_user.id}",
            f"UTub.id={current_utub.id}",
            f"UTubURL.id={utub_url_id}",
            f"URL.id={url_id_to_remove}",
        ]
    )

    return APIResponse(
        message=URL_SUCCESS.URL_REMOVED,
        data={
            URL_SUCCESS.UTUB_ID: current_utub.id,
            URL_SUCCESS.URL: {
                URL_SUCCESS.URL_STRING: url_string_to_remove,
                URL_SUCCESS.UTUB_URL_ID: utub_url_id,
                URL_SUCCESS.URL_TITLE: current_utub_url.url_title,
            },
            URL_SUCCESS.TAG_COUNTS_MODIFIED: tag_ids_and_updated_count,
        },
    ).to_response()


def _update_tag_counts_on_url_delete(
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
    utub_url_tag_ids, utub_tag_ids = _get_utub_url_tag_ids_and_utub_tag_ids_on_utub_url(
        utub_id=current_utub.id, utub_url_id=current_utub_url.id
    )

    # Count instances of tags in UTub that were unique to the URL to be deleted
    tag_ids_and_count = _get_utub_url_tag_ids_and_count_in_utub(
        utub_id=current_utub.id, utub_tag_ids=utub_tag_ids
    )

    # Remove all tags associated with this URL in this UTub
    db.session.query(Utub_Url_Tags).filter(Utub_Url_Tags.id.in_(utub_url_tag_ids)).delete()  # type: ignore

    # Update utub tag count after successful removal of all tags associated with deleted URL
    return {t[0]: t[1] - 1 for t in tag_ids_and_count}


def _get_utub_url_tag_ids_and_utub_tag_ids_on_utub_url(
    utub_id: int, utub_url_id: int
) -> tuple[list[int], list[int]]:
    primary_key_and_tag_ids = (
        db.session.query(Utub_Url_Tags)
        .filter(
            Utub_Url_Tags.utub_id == utub_id,
            Utub_Url_Tags.utub_url_id == utub_url_id,
        )
        .with_entities(Utub_Url_Tags.id, Utub_Url_Tags.utub_tag_id)
        .all()
    )
    return _parse_utub_url_tag_ids_and_utub_tag_ids(primary_key_and_tag_ids)


def _parse_utub_url_tag_ids_and_utub_tag_ids(
    primary_key_and_tag_ids: list[Utub_Url_Tags],
) -> tuple[list[int], list[int]]:
    utub_tag_ids = []
    utub_url_tag_ids = []

    for utub_url_tag_id, utub_tag_id in primary_key_and_tag_ids:
        utub_tag_ids.append(utub_tag_id)
        utub_url_tag_ids.append(utub_url_tag_id)

    return utub_url_tag_ids, utub_tag_ids


def _get_utub_url_tag_ids_and_count_in_utub(
    utub_id: int, utub_tag_ids: list[int]
) -> list[tuple[int, int]]:
    tag_ids_and_count_in_utub = (
        db.session.query(
            Utub_Url_Tags.utub_tag_id,
            case([(func.count() > 0, func.count() - 1)], else_=0).label("count"),
        )
        .filter(
            Utub_Url_Tags.utub_id == utub_id,
            Utub_Url_Tags.utub_tag_id.in_(utub_tag_ids),
        )
        .group_by(Utub_Url_Tags.utub_tag_id)
        .all()
    )
    return tag_ids_and_count_in_utub
