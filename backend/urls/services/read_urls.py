from backend.api_common.responses import APIResponse, FlaskResponse
from backend.app_logger import safe_add_many_logs
from backend.models.utub_urls import Utub_Urls
from backend.schemas.urls import UrlReadResponseSchema, UtubUrlDetailSchema
from backend.utils.strings.url_strs import URL_SUCCESS


def get_url_in_utub(
    utub_id: int, utub_url_id: int, current_utub_url: Utub_Urls
) -> FlaskResponse:
    """
    Retrieves a URL from a UTub and returns the response.

    Args:
        utub_id: The UTub ID containing the relevant URL (used for logging)
        utub_url_id: The UTub URL ID being retrieved (used for logging)
        current_utub_url: The Utub_Urls model instance to read

    Returns:
        FlaskResponse with the URL data
    """
    safe_add_many_logs(
        [
            "Retrieved URL",
            f"UTub.id={utub_id}",
            f"UTubURL.id={utub_url_id}",
        ]
    )
    return APIResponse(
        message=URL_SUCCESS.URL_FOUND_IN_UTUB,
        data=UrlReadResponseSchema(
            url=UtubUrlDetailSchema.from_orm_url(current_utub_url),
        ),
    ).to_response()
