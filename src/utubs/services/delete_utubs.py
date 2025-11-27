from src import db
from src.api_common.responses import APIResponse, FlaskResponse
from src.app_logger import safe_add_many_logs
from src.models.utubs import Utubs
from src.utils.strings.utub_strs import UTUB_SUCCESS


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

    return APIResponse(
        message=UTUB_SUCCESS.UTUB_DELETED,
        data={
            UTUB_SUCCESS.UTUB_ID: utub_id,
            UTUB_SUCCESS.UTUB_NAME: utub_name,
            UTUB_SUCCESS.UTUB_DESCRIPTION: utub_description,
        },
    ).to_response()
