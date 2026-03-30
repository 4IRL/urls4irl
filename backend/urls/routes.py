from flask import Blueprint

from backend.api_common.auth_decorators import (
    utub_membership_required,
    utub_membership_with_valid_url_in_utub_required,
    xml_http_request_only,
)
from backend.api_common.parse_request import api_route
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.app_logger import (
    safe_add_many_logs,
)
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.schemas.errors import build_message_error_response
from backend.schemas.requests.urls import (
    CreateURLRequest,
    UpdateURLStringRequest,
    UpdateURLTitleRequest,
)
from backend.schemas.urls import (
    UrlCreatedResponseSchema,
    UrlDeletedResponseSchema,
    UrlReadResponseSchema,
    UrlTitleUpdatedResponseSchema,
    UrlUpdatedResponseSchema,
    UtubUrlDetailSchema,
)
from backend.urls.services.create_urls import create_url_in_utub
from backend.urls.services.delete_urls import (
    check_if_is_url_adder_or_utub_creator_on_url_delete,
    delete_url_in_utub,
)
from backend.urls.services.update_url_titles import update_url_title_if_new
from backend.urls.services.update_urls import (
    check_if_is_url_adder_or_utub_creator_on_url_update,
    update_url_in_utub,
)
from backend.urls.constants import URLErrorCodes
from backend.utils.strings.json_strs import STD_JSON_RESPONSE
from backend.utils.strings.url_strs import URL_FAILURE, URL_SUCCESS

urls = Blueprint("urls", __name__)

# Standard response for JSON messages
STD_JSON = STD_JSON_RESPONSE


@urls.route("/utubs/<int:utub_id>/urls", methods=["POST"])
@utub_membership_required
@api_route(
    request_schema=CreateURLRequest,
    response_schema=UrlCreatedResponseSchema,
    error_message=URL_FAILURE.UNABLE_TO_ADD_URL_FORM,
    error_code=URLErrorCodes.INVALID_FORM_INPUT,
)
def create_url(
    utub_id: int, current_utub: Utubs, validated_request: CreateURLRequest
) -> FlaskResponse:
    """
    User wants to add URL to UTub. On success, adds the URL to the UTub.

    Args:
        utub_id (int): The Utubs to add this URL to
    """
    return create_url_in_utub(
        url_string=validated_request.urlString,
        url_title=validated_request.urlTitle,
        current_utub=current_utub,
    )


@urls.route("/utubs/<int:utub_id>/urls/<int:utub_url_id>", methods=["GET"])
@xml_http_request_only
@utub_membership_with_valid_url_in_utub_required
@api_route(response_schema=UrlReadResponseSchema)
def get_url(
    utub_id: int, utub_url_id: int, current_utub: Utubs, current_utub_url: Utub_Urls
) -> FlaskResponse:
    """
    Allows a user to read a URL in a UTub. Only users who are a member of the
    UTub can GET this URL.

    Args:
        utub_id (int): The UTub ID containing the relevant URL
        utub_url_id (int): The URL ID to be modified
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


@urls.route("/utubs/<int:utub_id>/urls/<int:utub_url_id>", methods=["PATCH"])
@utub_membership_with_valid_url_in_utub_required
@api_route(
    request_schema=UpdateURLStringRequest,
    response_schema=UrlUpdatedResponseSchema,
    error_message=URL_FAILURE.UNABLE_TO_MODIFY_URL_FORM,
    error_code=URLErrorCodes.INVALID_FORM_INPUT,
)
def update_url(
    utub_id: int,
    utub_url_id: int,
    current_utub: Utubs,
    current_utub_url: Utub_Urls,
    validated_request: UpdateURLStringRequest,
) -> FlaskResponse:
    """
    Allows a user to update a URL without updating the title.
    Only the user who added the URL, or who created the UTub containing
    the URL, can modify the URL.

    Args:
        utub_id (int): The UTub ID containing the relevant URL
        utub_url_id (int): The URL ID to be modified
        current_utub: (Utubs): The UTub for this URL
        current_utub_url: (Utub_Urls): The UTub_Urls to update
    """
    if not check_if_is_url_adder_or_utub_creator_on_url_update(
        utub_id=utub_id, utub_url_id=utub_url_id
    ):
        return build_message_error_response(
            message=URL_FAILURE.UNABLE_TO_MODIFY_URL, status_code=403
        )

    return update_url_in_utub(
        url_string=validated_request.urlString,
        current_utub=current_utub,
        current_utub_url=current_utub_url,
    )


@urls.route("/utubs/<int:utub_id>/urls/<int:utub_url_id>/title", methods=["PATCH"])
@utub_membership_with_valid_url_in_utub_required
@api_route(
    request_schema=UpdateURLTitleRequest,
    response_schema=UrlTitleUpdatedResponseSchema,
    error_message=URL_FAILURE.UNABLE_TO_MODIFY_URL_FORM,
    error_code=URLErrorCodes.INVALID_FORM_INPUT,
)
def update_url_title(
    utub_id: int,
    utub_url_id: int,
    current_utub: Utubs,
    current_utub_url: Utub_Urls,
    validated_request: UpdateURLTitleRequest,
) -> FlaskResponse:
    """
    Allows a user to update a URL title without updating the url.
    Only the user who added the URL, or who created the UTub containing
    the URL, can modify the title.

    Args:
        utub_id (int): The UTub ID containing the relevant URL
        utub_url_id (int): The URL ID to be modified
        current_utub: (Utubs): The UTub for this URL
        current_utub_url: (Utub_Urls): The UTub_Urls to update
    """
    if not check_if_is_url_adder_or_utub_creator_on_url_update(
        utub_id=utub_id, utub_url_id=utub_url_id
    ):
        return build_message_error_response(
            message=URL_FAILURE.UNABLE_TO_MODIFY_URL, status_code=403
        )

    return update_url_title_if_new(
        new_url_title=validated_request.urlTitle,
        current_utub=current_utub,
        current_utub_url=current_utub_url,
    )


@urls.route("/utubs/<int:utub_id>/urls/<int:utub_url_id>", methods=["DELETE"])
@utub_membership_with_valid_url_in_utub_required
@api_route(response_schema=UrlDeletedResponseSchema)
def delete_url(
    utub_id: int, utub_url_id: int, current_utub: Utubs, current_utub_url: Utub_Urls
) -> FlaskResponse:
    """
    User wants to remove a URL from a UTub. Only available to owner of that utub,
    or whoever added the URL into that Utubs.

    Args:
        utub_id (int): The ID of the UTub that contains the URL to be removed
        utub_url_id (int): The ID of the UtubUrl to be removed
    """
    is_utub_creator_or_url_adder = check_if_is_url_adder_or_utub_creator_on_url_delete(
        utub_id=utub_id, utub_url_id=utub_url_id
    )

    if not is_utub_creator_or_url_adder:
        return build_message_error_response(
            message=URL_FAILURE.UNABLE_TO_DELETE_URL, status_code=403
        )

    return delete_url_in_utub(
        current_utub=current_utub, current_utub_url=current_utub_url
    )
