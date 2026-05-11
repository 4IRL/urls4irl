from flask_login import current_user

from backend import db
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.app_logger import (
    safe_add_log,
    warning_log,
)
from backend.extensions.metrics.writer import record_event
from backend.metrics.events import EventName
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.schemas.urls import UrlTitleUpdatedResponseSchema, UtubUrlDetailSchema
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.url_strs import URL_NO_CHANGE, URL_SUCCESS


def update_url_title_if_new(
    new_url_title: str, current_utub: Utubs, current_utub_url: Utub_Urls
) -> FlaskResponse:
    """
    Verify that the current user has permission to delete a URL from a UTub.

    Checks whether the current user is either the creator of the UTub or the user who
    originally added the URL. If neither condition is met, logs a critical error and
    returns a 403 Forbidden response.

    Args:
        new_url_title (str): The URL title to update to
        current_utub (Utubs): The UTub object containing the UTub_Urls
        current_utub_url (Utub_Urls): The UTub_Urls object to update the title for.

    Returns:
        tuple[Response, int]:
        - Response: JSON response on update
        - int: HTTP status code 200 (Success)
    """
    is_different_title = new_url_title != current_utub_url.url_title

    if is_different_title:
        current_utub_url.url_title = new_url_title  # Updates the title
        current_utub.set_last_updated()
        db.session.commit()
        safe_add_log("URL title updated")
        record_event(EventName.URL_TITLE_UPDATED)
    else:
        warning_log(f"User={current_user.id} tried updating to identical URL title")

    message = URL_SUCCESS.URL_TITLE_MODIFIED

    schema = UtubUrlDetailSchema.from_orm_url(current_utub_url)
    return APIResponse(
        status=STD_JSON.SUCCESS if is_different_title else STD_JSON.NO_CHANGE,
        message=message if is_different_title else URL_NO_CHANGE.URL_TITLE_NOT_MODIFIED,
        data=UrlTitleUpdatedResponseSchema(url=schema),
    ).to_response()
