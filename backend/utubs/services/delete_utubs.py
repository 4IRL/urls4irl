from flask import abort
from flask_login import current_user

from backend import db
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.app_logger import safe_add_many_logs
from backend.extensions.metrics.writer import record_event
from backend.metrics.events import EventName
from backend.models.utubs import Utubs
from backend.schemas.utubs import UtubDeletedResponseSchema
from backend.utils.datetime_utils import utc_now
from backend.utils.strings.utub_strs import UTUB_SUCCESS
from backend.utubs.constants import UTubErrorCodes
from backend.utubs.guards import reject_if_utub_locked


def delete_utub_for_user(current_utub: Utubs) -> FlaskResponse:
    """
    Moves a UTub to trash for the UTub's creator: the UTub is flagged trashed
    (``deleted_at`` / ``deleted_by``) and its URLs, tags and members are kept
    for restore.

    Args:
        current_utub (Utubs): The UTub to trash

    Returns:
        tuple[Response, int]:
        - Response: JSON response on delete
        - int: HTTP status code 200 (Success)
    """
    utub_locked_error: FlaskResponse | None = reject_if_utub_locked(
        current_utub, error_code=UTubErrorCodes.UTUB_IS_LOCKED
    )
    if utub_locked_error is not None:
        return utub_locked_error

    utub_id = current_utub.id
    utub_name = current_utub.name
    utub_description = current_utub.utub_description

    rows_trashed: int = Utubs.query.filter(
        Utubs.id == utub_id, Utubs.deleted_at.is_(None)
    ).update(
        {Utubs.deleted_at: utc_now(), Utubs.deleted_by: current_user.id},
        synchronize_session=False,
    )
    if rows_trashed == 0:
        db.session.rollback()
        abort(404)
    db.session.commit()

    safe_add_many_logs(
        [
            "Deleted UTub",
            f"UTub.id={utub_id}",
            f"UTub.name={utub_name}",
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
