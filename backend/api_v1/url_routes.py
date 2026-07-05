"""
Bearer-token (/api/v1) wrapper routes for URLs and cross-UTub search.

Each route is an exact twin of its web counterpart (backend/urls/routes.py,
backend/search/routes.py), with three changes:
  - Session decorator → api_ equivalent
  - ajax_required=False (no X-Requested-With sentinel)
  - tags=[OPEN_API.MOBILE_API] + 401/403 added to status_codes
"""

from flask_login import current_user
from pydantic import BaseModel

from backend.api_common.auth_decorators import (
    api_email_validation_required,
    api_url_adder_or_creator_required,
    api_utub_membership_required,
    api_utub_membership_with_valid_url_in_utub_required,
)
from backend.api_common.parse_request import api_route, parse_query_args
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.api_v1.routes import api_v1
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.schemas.errors import ErrorResponse
from backend.schemas.requests.search import SearchQuerySchema
from backend.schemas.requests.urls import (
    CreateURLRequest,
    UpdateURLStringRequest,
    UpdateURLTitleRequest,
)
from backend.schemas.search import SearchResultsSchema
from backend.schemas.urls import (
    UrlCreatedResponseSchema,
    UrlDeletedResponseSchema,
    UrlReadResponseSchema,
    UrlTitleUpdatedResponseSchema,
    UrlUpdatedResponseSchema,
)
from backend.search.constants import SearchErrorCodes, SearchFailureMessages
from backend.search.services.cross_utub_search import search_across_user_utubs
from backend.urls.constants import URLErrorCodes
from backend.urls.services.create_urls import create_url_in_utub
from backend.urls.services.delete_urls import delete_url_in_utub
from backend.urls.services.read_urls import get_url_in_utub
from backend.urls.services.update_url_titles import update_url_title_if_new
from backend.urls.services.update_urls import update_url_in_utub
from backend.utils.strings.openapi_strs import OPEN_API
from backend.utils.strings.url_strs import URL_FAILURE


@api_v1.route("/utubs/<int:utub_id>/urls", methods=["POST"])
@api_utub_membership_required
@api_route(
    request_schema=CreateURLRequest,
    response_schema=UrlCreatedResponseSchema,
    error_message=URL_FAILURE.UNABLE_TO_ADD_URL_FORM,
    error_code=URLErrorCodes.INVALID_FORM_INPUT,
    ajax_required=False,
    tags=[OPEN_API.MOBILE_API],
    description="Add a URL to a UTub",
    status_codes={
        200: UrlCreatedResponseSchema,
        400: ErrorResponse,
        401: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
        409: ErrorResponse,
    },
)
def api_v1_create_url(
    utub_id: int, current_utub: Utubs, create_url_request: CreateURLRequest
) -> FlaskResponse:
    """Create a new URL in a UTub the authenticated user belongs to."""
    return create_url_in_utub(
        url_string=create_url_request.urlString,
        url_title=create_url_request.urlTitle,
        current_utub=current_utub,
        tag_strings=create_url_request.tagStrings,
    )


@api_v1.route("/utubs/<int:utub_id>/urls/<int:utub_url_id>", methods=["GET"])
@api_utub_membership_with_valid_url_in_utub_required
@api_route(
    response_schema=UrlReadResponseSchema,
    ajax_required=False,
    tags=[OPEN_API.MOBILE_API],
    description="Retrieve a URL from a UTub",
    status_codes={
        200: UrlReadResponseSchema,
        401: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
)
def api_v1_get_url(
    utub_id: int, utub_url_id: int, current_utub: Utubs, current_utub_url: Utub_Urls
) -> FlaskResponse:
    """Return a single URL from a UTub the authenticated user belongs to."""
    return get_url_in_utub(
        utub_id=utub_id,
        utub_url_id=utub_url_id,
        current_utub_url=current_utub_url,
    )


@api_v1.route("/utubs/<int:utub_id>/urls/<int:utub_url_id>", methods=["PATCH"])
@api_url_adder_or_creator_required(message=URL_FAILURE.UNABLE_TO_MODIFY_URL)
@api_route(
    request_schema=UpdateURLStringRequest,
    response_schema=UrlUpdatedResponseSchema,
    error_message=URL_FAILURE.UNABLE_TO_MODIFY_URL_FORM,
    error_code=URLErrorCodes.INVALID_FORM_INPUT,
    ajax_required=False,
    tags=[OPEN_API.MOBILE_API],
    description="Update a URL string in a UTub",
    status_codes={
        200: UrlUpdatedResponseSchema,
        400: ErrorResponse,
        401: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
        409: ErrorResponse,
    },
)
def api_v1_update_url(
    utub_id: int,
    utub_url_id: int,
    current_utub: Utubs,
    current_utub_url: Utub_Urls,
    update_url_string_request: UpdateURLStringRequest,
) -> FlaskResponse:
    """Update the URL string for a URL the authenticated user added or the UTub they created."""
    return update_url_in_utub(
        url_string=update_url_string_request.urlString,
        current_utub=current_utub,
        current_utub_url=current_utub_url,
    )


@api_v1.route("/utubs/<int:utub_id>/urls/<int:utub_url_id>/title", methods=["PATCH"])
@api_url_adder_or_creator_required(message=URL_FAILURE.UNABLE_TO_MODIFY_URL)
@api_route(
    request_schema=UpdateURLTitleRequest,
    response_schema=UrlTitleUpdatedResponseSchema,
    error_message=URL_FAILURE.UNABLE_TO_MODIFY_URL_FORM,
    error_code=URLErrorCodes.INVALID_FORM_INPUT,
    ajax_required=False,
    tags=[OPEN_API.MOBILE_API],
    description="Update a URL title in a UTub",
    status_codes={
        200: UrlTitleUpdatedResponseSchema,
        400: ErrorResponse,
        401: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
)
def api_v1_update_url_title(
    utub_id: int,
    utub_url_id: int,
    current_utub: Utubs,
    current_utub_url: Utub_Urls,
    update_url_title_request: UpdateURLTitleRequest,
) -> FlaskResponse:
    """Update the title of a URL the authenticated user added or the UTub they created."""
    return update_url_title_if_new(
        new_url_title=update_url_title_request.urlTitle,
        current_utub=current_utub,
        current_utub_url=current_utub_url,
    )


@api_v1.route("/utubs/<int:utub_id>/urls/<int:utub_url_id>", methods=["DELETE"])
@api_url_adder_or_creator_required(message=URL_FAILURE.UNABLE_TO_DELETE_URL)
@api_route(
    response_schema=UrlDeletedResponseSchema,
    ajax_required=False,
    tags=[OPEN_API.MOBILE_API],
    description="Delete a URL from a UTub",
    status_codes={
        200: UrlDeletedResponseSchema,
        401: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
)
def api_v1_delete_url(
    utub_id: int, utub_url_id: int, current_utub: Utubs, current_utub_url: Utub_Urls
) -> FlaskResponse:
    """Delete a URL from a UTub. Caller must be the URL adder or UTub creator."""
    return delete_url_in_utub(
        current_utub=current_utub, current_utub_url=current_utub_url
    )


@api_v1.route("/search", methods=["GET"])
@api_email_validation_required
@api_route(
    query_schema=SearchQuerySchema,
    response_schema=SearchResultsSchema,
    ajax_required=False,
    tags=[OPEN_API.MOBILE_API],
    description="Search across all of the current user's member UTubs, grouped by source UTub.",
    status_codes={
        200: SearchResultsSchema,
        400: ErrorResponse,
        401: ErrorResponse,
        403: ErrorResponse,
    },
)
def api_v1_search_across_utubs() -> FlaskResponse:
    """Search across all UTubs the authenticated user belongs to."""
    parsed = parse_query_args(
        SearchQuerySchema,
        message=SearchFailureMessages.INVALID_QUERY,
        error_code=SearchErrorCodes.INVALID_QUERY_PARAM,
    )
    if not isinstance(parsed, BaseModel):
        return parsed
    response_schema = search_across_user_utubs(
        query=parsed.q, fields=parsed.fields, user_id=current_user.id
    )
    return APIResponse(data=response_schema, status_code=200).to_response()
