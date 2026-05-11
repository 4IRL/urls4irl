from backend import db
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.app_logger import safe_add_log, safe_add_many_logs
from backend.extensions.metrics.writer import record_event
from backend.metrics.events import EventName
from backend.models.utubs import Utubs
from backend.schemas.utubs import (
    UtubDescUpdatedResponseSchema,
    UtubNameUpdatedResponseSchema,
)


def update_utub_name_if_new(current_utub: Utubs, utub_name: str) -> FlaskResponse:
    """
    Updates the name for the UTub only if it is not equivalent to the old name.

    Args:
        current_utub (Utubs): The UTub that is being updated
        utub_name (str): The new name for the UTub

    Returns:
        FlaskResponse: JSON response on update with 200 status code
    """
    old_utub_name = current_utub.name

    if utub_name != old_utub_name:
        current_utub.name = utub_name
        current_utub.set_last_updated()
        db.session.commit()

        safe_add_many_logs(
            [
                "User updated UTub name",
                f"UTub.id={current_utub.id}",
                f"OLD UTub.name={old_utub_name}",
                f"NEW UTub.name={current_utub.name}",
            ]
        )
        record_event(EventName.UTUB_TITLE_UPDATED)

    return APIResponse(
        data=UtubNameUpdatedResponseSchema(
            utub_id=current_utub.id,
            utub_name=current_utub.name,
        )
    ).to_response()


def update_utub_desc_if_new(
    current_utub: Utubs, utub_description: str | None
) -> FlaskResponse:
    """
    Updates the description for the UTub only if it is not equivalent to the old description.
    A None description means the user wants to clear the description.

    Args:
        current_utub (Utubs): The UTub that is being updated
        utub_description (str | None): The new description, or None to clear it

    Returns:
        FlaskResponse: JSON response on update with 200 status code
    """
    old_utub_description = current_utub.utub_description
    if (utub_description or "") != (old_utub_description or ""):
        current_utub.utub_description = utub_description
        current_utub.set_last_updated()
        db.session.commit()

        safe_add_many_logs(
            [
                "Updated UTub description",
                f"UTub.id={current_utub.id}",
                f"OLD UTub.description={old_utub_description}",
                f"NEW UTub.description={utub_description}",
            ]
        )
        record_event(EventName.UTUB_DESC_UPDATED)
    else:
        safe_add_log("No change in UTub description")

    return APIResponse(
        data=UtubDescUpdatedResponseSchema(
            utub_id=current_utub.id,
            utub_description=current_utub.utub_description,
        )
    ).to_response()
