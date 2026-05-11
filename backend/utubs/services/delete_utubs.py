from backend import db
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.app_logger import safe_add_many_logs
from backend.extensions.metrics.writer import record_event
from backend.metrics.events import EventName
from backend.models.utubs import Utubs
from backend.schemas.utubs import UtubDeletedResponseSchema
from backend.utils.strings.utub_strs import UTUB_SUCCESS


def delete_utub_for_user(current_utub: Utubs) -> FlaskResponse:
    """
    Deletes a UTub for the UTub's creator.

    Args:
        current_utub (Utubs): The UTub to delete

    Returns:
        tuple[Response, int]:
        - Response: JSON response on delete
        - int: HTTP status code 200 (Success)
    """
    utub_id = current_utub.id
    utub_name = current_utub.name
    utub_description = current_utub.utub_description

    db.session.delete(current_utub)
    db.session.commit()

    safe_add_many_logs(
        [
            "Deleted UTub",
            f"UTub.id={utub_id}",
            f"UTub.name={current_utub.name}",
        ]
    )

    record_event(EventName.UTUB_DELETED)

    return APIResponse(
        message=UTUB_SUCCESS.UTUB_DELETED,
        data=UtubDeletedResponseSchema(
            utub_id=utub_id,
            utub_name=utub_name,
            utub_description=utub_description,
        ),
    ).to_response()
