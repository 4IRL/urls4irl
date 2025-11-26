from src import db
from src.api_common.responses import APIResponse, FlaskResponse
from src.app_logger import safe_add_many_logs
from src.models.utub_tags import Utub_Tags
from src.models.utub_url_tags import Utub_Url_Tags
from src.models.utubs import Utubs
from src.utils.strings.model_strs import MODELS
from src.utils.strings.tag_strs import TAGS_SUCCESS


def delete_utub_tag_from_utub_and_utub_urls(
    utub: Utubs, utub_tag: Utub_Tags
) -> FlaskResponse:
    """
    Deletes a UTub tag from a UTub. Provides a list of all URL IDs that had this tag associated withit.

    Args:
        utub (Utubs): The UTub where this tag is being removed from
        utub_tag (Utub_Tags): The tag being deleted

    Returns:
        tuple[Response, int]:
        - Response: JSON response on success
        - int: HTTP status code 200
    """
    utub_url_ids_with_utub_tag = _get_utub_url_ids_for_utub_tag(utub, utub_tag)

    serialized_tag = utub_tag.serialized_on_add_delete

    db.session.delete(utub_tag)

    utub.set_last_updated()
    db.session.commit()
    safe_add_many_logs(
        [
            "Deleted UTubTag",
            f"UTub.id={utub.id}",
            f"UTubTag.id={utub_tag.id}",
            f"UTubTag.tag_string={serialized_tag[MODELS.TAG_STRING]}",
        ]
    )

    return APIResponse(
        message=TAGS_SUCCESS.TAG_REMOVED_FROM_UTUB,
        data={
            TAGS_SUCCESS.UTUB_TAG: serialized_tag,
            TAGS_SUCCESS.UTUB_URL_IDS: utub_url_ids_with_utub_tag,
        },
    ).to_response()


def _get_utub_url_ids_for_utub_tag(utub: Utubs, utub_tag: Utub_Tags) -> list[int]:
    """
    Gets all associated UTub URL IDs that had a UTub Tag associated with it.

    Args:
        utub (Utubs): The UTub to check the associated UTub Tag with URLs
        utub_tag (Utub_Tags): The UTub Tags being checked

    Returns:
        list[int]: The list of UTub URL IDs that have this UTub Tag
    """
    return [
        id_tuple[0]
        for id_tuple in db.session.query(Utub_Url_Tags.utub_url_id)
        .filter(
            Utub_Url_Tags.utub_id == utub.id, Utub_Url_Tags.utub_tag_id == utub_tag.id
        )
        .all()
    ]
