from flask import Response, jsonify
from src import db
from src.app_logger import safe_add_many_logs
from src.models.utub_tags import Utub_Tags
from src.models.utub_url_tags import Utub_Url_Tags
from src.models.utub_urls import Utub_Urls
from src.models.utubs import Utubs
from src.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from src.utils.strings.tag_strs import TAGS_SUCCESS


def delete_url_tag(
    utub: Utubs, utub_url: Utub_Urls, utub_tag: Utub_Tags, utub_url_tag: Utub_Url_Tags
) -> tuple[Response, int]:
    """
    Handles deleting a UTub URL Tag. Provides the count of the associated UTub Tag in the database.

    Args:
        utub (Utubs): The UTub object containing the URL with it's tag to delete
        utub_url (Utub_Urls): The UTub Urls object with the tag to remove
        utub_tag (Utub_Tags): The UTub Tag that is associated with the URL Tag
        utub_url_tag (Utub_Url_Tags): The tag on the URL to delete

    Returns:
        tuple[Response, int]:
        - Response: JSON response on success
        - int: HTTP status code 200 (Success)
    """
    db.session.delete(utub_url_tag)

    utub.set_last_updated()
    db.session.commit()

    return _handle_delete_url_tag_response(
        # Count instances of particular tag in UTub that is to be deleted
        utub_tag_id_count=_count_tag_in_utub_after_url_tag_delete(utub, utub_tag),
        utub=utub,
        utub_url=utub_url,
        utub_tag=utub_tag,
        utub_url_tag=utub_url_tag,
    )


def _count_tag_in_utub_after_url_tag_delete(utub: Utubs, utub_tag: Utub_Tags) -> int:
    """
    Calculates the count of URLs that have this UTub Tag applied to them.

    Args:
        utub (Utubs): The UTub object containing the UTub Tag and URLs to count
        utub_tag (Utub_Tags): The tag that may be associated with URLs

    Returns:
        (int): The number of URLs associated with this Tag in this UTub
    """
    return Utub_Url_Tags.query.filter(
        Utub_Url_Tags.utub_id == utub.id, Utub_Url_Tags.utub_tag_id == utub_tag.id
    ).count()


def _handle_delete_url_tag_response(
    utub_tag_id_count: int,
    utub: Utubs,
    utub_url: Utub_Urls,
    utub_tag: Utub_Tags,
    utub_url_tag: Utub_Url_Tags,
) -> tuple[Response, int]:
    """
    Builds the JSON response on successful URL Tag delete.

    Args:
        utub_tag_id_count (int): The count of the URLs associated with this UTub Tag
        utub (Utubs): The UTub object containing the URL with it's tag to delete
        utub_url (Utub_Urls): The UTub Urls object with the tag to remove
        utub_tag (Utub_Tags): The UTub Tag that is associated with the URL Tag
        utub_url_tag (Utub_Url_Tags): The tag on the URL to delete

    Returns:
        tuple[Response, int]:
        - Response: JSON response on success
        - int: HTTP status code 200 (Success)
    """
    safe_add_many_logs(
        [
            "Removed UTubURLTag",
            f"UTub.id={utub.id}",
            f"UTubURL.id={utub_url.id}",
            f"UTubTag.id={utub_tag.id}",
            f"UTubTag.tag_string={utub_tag.tag_string}",
            f"UTubURLTag.id={utub_url_tag.id}",
        ]
    )

    return (
        jsonify(
            {
                STD_JSON.STATUS: STD_JSON.SUCCESS,
                STD_JSON.MESSAGE: TAGS_SUCCESS.TAG_REMOVED_FROM_URL,
                TAGS_SUCCESS.UTUB_URL_TAG_IDS: utub_url.associated_tag_ids,
                TAGS_SUCCESS.UTUB_TAG: utub_tag.serialized_on_add_delete,
                TAGS_SUCCESS.TAG_COUNTS_MODIFIED: utub_tag_id_count,
            }
        ),
        200,
    )
