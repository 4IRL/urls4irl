from backend import db
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.app_logger import safe_add_many_logs
from backend.extensions.metrics.writer import record_event
from backend.metrics.events import EventName
from backend.models.utub_tags import Utub_Tags
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utubs import Utubs
from backend.schemas.tags import (
    UtubTagDeletedFromUtubResponseSchema,
    UtubTagOnAddDeleteSchema,
)
from backend.utils.strings.tag_strs import TAGS_SUCCESS


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

    tag_schema = UtubTagOnAddDeleteSchema.from_orm_tag(utub_tag)

    db.session.delete(utub_tag)

    utub.set_last_updated()
    db.session.commit()
    safe_add_many_logs(
        [
            "Deleted UTubTag",
            f"UTub.id={utub.id}",
            f"UTubTag.id={utub_tag.id}",
            f"UTubTag.tag_string={tag_schema.tag_string}",
        ]
    )

    record_event(EventName.TAG_DELETED)

    return APIResponse(
        message=TAGS_SUCCESS.TAG_REMOVED_FROM_UTUB,
        data=UtubTagDeletedFromUtubResponseSchema(
            utub_tag=tag_schema,
            utub_url_ids=utub_url_ids_with_utub_tag,
        ),
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
