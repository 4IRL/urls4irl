"""
Bearer-token (/api/v1) wrapper routes for URL tags, UTub tags, and search.

Each route is an exact twin of its web counterpart (backend/tags/url_tag_routes.py,
backend/tags/utub_tag_routes.py, backend/search/routes.py), with three changes:
  - Session decorator → api_ equivalent
  - ajax_required=False (no X-Requested-With sentinel)
  - tags=[OPEN_API.MOBILE_API] + 401/403 added to status_codes
"""

from flask_login import current_user
from pydantic import BaseModel

from backend.api_common.auth_decorators import (
    api_email_validation_required,
    api_utub_membership_required,
    api_utub_membership_with_valid_url_in_utub_required,
    api_utub_membership_with_valid_url_tag,
    api_utub_membership_with_valid_utub_tag,
)
from backend.api_common.parse_request import api_route, parse_query_args
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.api_v1.routes import api_v1
from backend.models.utub_tags import Utub_Tags
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.schemas.errors import ErrorResponse
from backend.schemas.requests.search import SearchQuerySchema
from backend.schemas.requests.tags import AddTagRequest, AddTagsRequest
from backend.schemas.search import SearchResultsSchema
from backend.schemas.tags import (
    UrlTagModifiedResponseSchema,
    UrlTagsModifiedResponseSchema,
    UtubTagAddedToUtubResponseSchema,
    UtubTagDeletedFromUtubResponseSchema,
)
from backend.search.constants import SearchErrorCodes, SearchFailureMessages
from backend.search.services.cross_utub_search import search_across_user_utubs
from backend.tags.constants import URLTagErrorCodes, UTubTagErrorCodes
from backend.tags.services.create_url_tag import (
    add_batch_tags_to_existing_url,
    add_tag_to_url_if_valid,
)
from backend.tags.services.create_utub_tag import create_tag_in_utub
from backend.tags.services.delete_url_tag import delete_url_tag
from backend.tags.services.delete_utub_tag import (
    delete_utub_tag_from_utub_and_utub_urls,
)
from backend.utils.strings.openapi_strs import OPEN_API
from backend.utils.strings.tag_strs import TAGS_FAILURE


@api_v1.route("/utubs/<int:utub_id>/urls/<int:utub_url_id>/tags", methods=["POST"])
@api_utub_membership_with_valid_url_in_utub_required
@api_route(
    request_schema=AddTagRequest,
    response_schema=UrlTagModifiedResponseSchema,
    error_message=TAGS_FAILURE.UNABLE_TO_ADD_TAG_TO_URL,
    error_code=URLTagErrorCodes.INVALID_FORM_INPUT,
    ajax_required=False,
    tags=[OPEN_API.MOBILE_API],
    description="Add a tag to a URL in a UTub",
    status_codes={
        200: UrlTagModifiedResponseSchema,
        400: ErrorResponse,
        401: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
)
def api_v1_create_utub_url_tag(
    utub_id: int,
    utub_url_id: int,
    current_utub: Utubs,
    current_utub_url: Utub_Urls,
    add_tag_request: AddTagRequest,
) -> FlaskResponse:
    """Add a single tag to a URL in a UTub the authenticated user belongs to."""
    return add_tag_to_url_if_valid(
        tag_string=add_tag_request.tagString,
        utub=current_utub,
        utub_url=current_utub_url,
    )


@api_v1.route(
    "/utubs/<int:utub_id>/urls/<int:utub_url_id>/tags/batch", methods=["POST"]
)
@api_utub_membership_with_valid_url_in_utub_required
@api_route(
    request_schema=AddTagsRequest,
    response_schema=UrlTagsModifiedResponseSchema,
    error_message=TAGS_FAILURE.UNABLE_TO_ADD_TAG_TO_URL,
    error_code=URLTagErrorCodes.INVALID_FORM_INPUT,
    ajax_required=False,
    tags=[OPEN_API.MOBILE_API],
    description="Apply multiple tags to a URL in a UTub",
    status_codes={
        200: UrlTagsModifiedResponseSchema,
        400: ErrorResponse,
        401: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
)
def api_v1_create_utub_url_tags(
    utub_id: int,
    utub_url_id: int,
    current_utub: Utubs,
    current_utub_url: Utub_Urls,
    add_tags_request: AddTagsRequest,
) -> FlaskResponse:
    """Apply multiple tags to a URL in one atomic batch."""
    return add_batch_tags_to_existing_url(
        tag_strings=add_tags_request.tagStrings,
        utub=current_utub,
        utub_url=current_utub_url,
    )


@api_v1.route(
    "/utubs/<int:utub_id>/urls/<int:utub_url_id>/tags/<int:utub_tag_id>",
    methods=["DELETE"],
)
@api_utub_membership_with_valid_url_tag
@api_route(
    response_schema=UrlTagModifiedResponseSchema,
    ajax_required=False,
    tags=[OPEN_API.MOBILE_API],
    description="Remove a tag from a URL in a UTub",
    status_codes={
        200: UrlTagModifiedResponseSchema,
        401: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
)
def api_v1_delete_utub_url_tag(
    utub_id: int,
    utub_url_id: int,
    utub_tag_id: int,
    current_utub: Utubs,
    current_utub_url: Utub_Urls,
    current_utub_tag: Utub_Tags,
    current_url_tag: Utub_Url_Tags,
) -> FlaskResponse:
    """Remove a tag from a URL in a UTub the authenticated user belongs to."""
    return delete_url_tag(
        utub=current_utub,
        utub_url=current_utub_url,
        utub_tag=current_utub_tag,
        utub_url_tag=current_url_tag,
    )


@api_v1.route("/utubs/<int:utub_id>/tags", methods=["POST"])
@api_utub_membership_required
@api_route(
    request_schema=AddTagRequest,
    response_schema=UtubTagAddedToUtubResponseSchema,
    error_message=TAGS_FAILURE.UNABLE_TO_ADD_TAG_TO_UTUB,
    error_code=UTubTagErrorCodes.INVALID_FORM_INPUT,
    ajax_required=False,
    tags=[OPEN_API.MOBILE_API],
    description="Add a tag to a UTub",
    status_codes={
        200: UtubTagAddedToUtubResponseSchema,
        400: ErrorResponse,
        401: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
)
def api_v1_create_utub_tag(
    utub_id: int, current_utub: Utubs, add_tag_request: AddTagRequest
) -> FlaskResponse:
    """Add a tag to a UTub the authenticated user belongs to."""
    return create_tag_in_utub(
        tag_string=add_tag_request.tagString, current_utub=current_utub
    )


@api_v1.route(
    "/utubs/<int:utub_id>/tags/<int:utub_tag_id>",
    methods=["DELETE"],
)
@api_utub_membership_with_valid_utub_tag
@api_route(
    response_schema=UtubTagDeletedFromUtubResponseSchema,
    ajax_required=False,
    tags=[OPEN_API.MOBILE_API],
    description="Delete a tag from a UTub",
    status_codes={
        200: UtubTagDeletedFromUtubResponseSchema,
        401: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
)
def api_v1_delete_utub_tag(
    utub_id: int, utub_tag_id: int, current_utub: Utubs, current_utub_tag: Utub_Tags
) -> FlaskResponse:
    """Delete a tag from a UTub and all its associated URL-tag entries."""
    return delete_utub_tag_from_utub_and_utub_urls(
        utub=current_utub, utub_tag=current_utub_tag
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
