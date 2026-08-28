from flask import Blueprint
from flask_login import current_user

from backend.api_common.auth_decorators import (
    email_validation_required,
    url_adder_or_creator_required,
    utub_membership_required,
    utub_membership_with_valid_url_in_utub_required,
)
from backend.api_common.parse_request import api_route
from backend.api_common.responses import FlaskResponse
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.schemas.errors import ErrorResponse
from backend.schemas.requests.urls import (
    CopyUrlsRequest,
    CreateURLRequest,
    DeleteUrlsRequest,
    UpdateURLStringRequest,
    UpdateURLTitleRequest,
)
from backend.schemas.urls import (
    CopyUrlsResponseSchema,
    DeleteUrlsResponseSchema,
    UrlCreatedResponseSchema,
    UrlDeletedResponseSchema,
    UrlReadResponseSchema,
    UrlTitleUpdatedResponseSchema,
    UrlUpdatedResponseSchema,
)
from backend.urls.constants import URLErrorCodes
from backend.urls.services.copy_urls import copy_urls_into_utubs
from backend.urls.services.create_urls import create_url_in_utub
from backend.urls.services.delete_urls import delete_url_in_utub, delete_urls_in_utub
from backend.urls.services.read_urls import get_url_in_utub
from backend.urls.services.update_url_titles import update_url_title_if_new
from backend.urls.services.update_urls import update_url_in_utub
from backend.utils.strings.json_strs import STD_JSON_RESPONSE
from backend.utils.strings.openapi_strs import OPEN_API
from backend.utils.strings.url_strs import URL_FAILURE

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
    tags=[OPEN_API.URLS],
    description="Add a URL to a UTub",
    status_codes={
        200: UrlCreatedResponseSchema,
        400: ErrorResponse,
        404: ErrorResponse,
        409: ErrorResponse,
    },
)
def create_url(
    utub_id: int, current_utub: Utubs, create_url_request: CreateURLRequest
) -> FlaskResponse:
    """
    User wants to add URL to UTub. On success, adds the URL to the UTub.

    Args:
        utub_id (int): The Utubs to add this URL to
    """
    return create_url_in_utub(
        url_string=create_url_request.urlString,
        url_title=create_url_request.urlTitle,
        current_utub=current_utub,
        tag_strings=create_url_request.tagStrings,
    )


@urls.route("/utubs/urls/copy", methods=["POST"])
@email_validation_required
@api_route(
    request_schema=CopyUrlsRequest,
    response_schema=CopyUrlsResponseSchema,
    error_message=URL_FAILURE.UNABLE_TO_COPY_URLS,
    error_code=URLErrorCodes.UNABLE_TO_COPY_URLS_ERROR,
    tags=[OPEN_API.URLS],
    description="Copy selected URLs from a source UTub into one or more destination UTubs",
    status_codes={
        200: CopyUrlsResponseSchema,
        400: ErrorResponse,
        404: ErrorResponse,
    },
)
def copy_urls_to_utubs(copy_urls_request: CopyUrlsRequest) -> FlaskResponse:
    """
    User wants to copy one or more selected URLs from a SOURCE UTub into one or
    more DESTINATION UTubs in a single request. The endpoint carries no path
    param — the source UTub id, the destination UTub ids, and the selected
    UTub-URL ids all travel in the body (`sourceUtubId`, `destUtubIds`,
    `utubUrlIds`). URLs already present in a given destination are skipped and
    reported per-destination; a destination locked at write time is skipped and
    reported (`status="locked"`) rather than failing the whole request; tags are
    never carried across the copy.

    All source AND destination membership + lock + same-UTub validation is
    performed inside the service (`@email_validation_required` only proves a
    logged-in, email-validated user).

    Args:
        copy_urls_request (CopyUrlsRequest): Validated request schema
    """
    return copy_urls_into_utubs(
        source_utub_id=copy_urls_request.sourceUtubId,
        dest_utub_ids=copy_urls_request.destUtubIds,
        utub_url_ids=copy_urls_request.utubUrlIds,
        current_user_id=current_user.id,
    )


@urls.route("/utubs/<int:utub_id>/urls/<int:utub_url_id>", methods=["GET"])
@utub_membership_with_valid_url_in_utub_required
@api_route(
    response_schema=UrlReadResponseSchema,
    tags=[OPEN_API.URLS],
    description="Retrieve a URL from a UTub",
    status_codes={200: UrlReadResponseSchema, 404: ErrorResponse},
)
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

    return get_url_in_utub(
        utub_id=utub_id,
        utub_url_id=utub_url_id,
        current_utub_url=current_utub_url,
    )


@urls.route("/utubs/<int:utub_id>/urls/<int:utub_url_id>", methods=["PATCH"])
@url_adder_or_creator_required(message=URL_FAILURE.UNABLE_TO_MODIFY_URL)
@api_route(
    request_schema=UpdateURLStringRequest,
    response_schema=UrlUpdatedResponseSchema,
    error_message=URL_FAILURE.UNABLE_TO_MODIFY_URL_FORM,
    error_code=URLErrorCodes.INVALID_FORM_INPUT,
    tags=[OPEN_API.URLS],
    description="Update a URL string in a UTub",
    status_codes={
        200: UrlUpdatedResponseSchema,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
        409: ErrorResponse,
    },
)
def update_url(
    utub_id: int,
    utub_url_id: int,
    current_utub: Utubs,
    current_utub_url: Utub_Urls,
    update_url_string_request: UpdateURLStringRequest,
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
    return update_url_in_utub(
        url_string=update_url_string_request.urlString,
        current_utub=current_utub,
        current_utub_url=current_utub_url,
    )


@urls.route("/utubs/<int:utub_id>/urls/<int:utub_url_id>/title", methods=["PATCH"])
@url_adder_or_creator_required(message=URL_FAILURE.UNABLE_TO_MODIFY_URL)
@api_route(
    request_schema=UpdateURLTitleRequest,
    response_schema=UrlTitleUpdatedResponseSchema,
    error_message=URL_FAILURE.UNABLE_TO_MODIFY_URL_FORM,
    error_code=URLErrorCodes.INVALID_FORM_INPUT,
    tags=[OPEN_API.URLS],
    description="Update a URL title in a UTub",
    status_codes={
        200: UrlTitleUpdatedResponseSchema,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
)
def update_url_title(
    utub_id: int,
    utub_url_id: int,
    current_utub: Utubs,
    current_utub_url: Utub_Urls,
    update_url_title_request: UpdateURLTitleRequest,
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
    return update_url_title_if_new(
        new_url_title=update_url_title_request.urlTitle,
        current_utub=current_utub,
        current_utub_url=current_utub_url,
    )


@urls.route("/utubs/<int:utub_id>/urls/<int:utub_url_id>", methods=["DELETE"])
@url_adder_or_creator_required(message=URL_FAILURE.UNABLE_TO_DELETE_URL)
@api_route(
    response_schema=UrlDeletedResponseSchema,
    tags=[OPEN_API.URLS],
    description="Delete a URL from a UTub",
    status_codes={
        200: UrlDeletedResponseSchema,
        403: ErrorResponse,
        404: ErrorResponse,
    },
)
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
    return delete_url_in_utub(
        current_utub=current_utub, current_utub_url=current_utub_url
    )


@urls.route("/utubs/<int:utub_id>/urls/delete", methods=["POST"])
@utub_membership_required
@api_route(
    request_schema=DeleteUrlsRequest,
    response_schema=DeleteUrlsResponseSchema,
    error_message=URL_FAILURE.UNABLE_TO_DELETE_URLS,
    error_code=URLErrorCodes.UNABLE_TO_DELETE_URLS_ERROR,
    tags=[OPEN_API.URLS],
    description="Bulk-delete selected URLs from a UTub",
    status_codes={
        200: DeleteUrlsResponseSchema,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
)
def delete_urls_from_utub(
    utub_id: int, current_utub: Utubs, delete_urls_request: DeleteUrlsRequest
) -> FlaskResponse:
    """
    User wants to bulk-delete selected URLs from a single (active) UTub in one
    request. Membership is proved by ``@utub_membership_required``; the per-URL
    delete permission is re-checked inside the service against the *manager*
    predicate — the adder of a URL, or a manager (literal owner OR co-owner
    ``CO_CREATOR``) — matching each URL's ``canDelete`` and the single-URL delete
    guard. URLs the user may not delete are skipped and reported; unknown or
    cross-UTub ids reject the whole request as a 400; a locked UTub is a
    whole-request 403.

    Args:
        utub_id (int): The UTub to delete the selected URLs from
        current_utub (Utubs): The UTub for this request (membership already proved)
        delete_urls_request (DeleteUrlsRequest): Validated request schema
    """
    return delete_urls_in_utub(
        utub_url_ids=delete_urls_request.utubUrlIds,
        utub=current_utub,
        current_user_id=current_user.id,
    )
