from __future__ import annotations

from flask import Blueprint
from flask_login import current_user
from pydantic import BaseModel

from backend.api_common.auth_decorators import email_validation_required
from backend.api_common.parse_request import api_route, parse_query_args
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.schemas.errors import ErrorResponse
from backend.schemas.requests.search import SearchQuerySchema
from backend.schemas.search import SearchResultsSchema
from backend.search.constants import SearchErrorCodes, SearchFailureMessages
from backend.search.services.cross_utub_search import search_across_user_utubs
from backend.utils.strings.openapi_strs import OPEN_API

search = Blueprint("search", __name__)


@search.route("/search", methods=["GET"])
@email_validation_required
@api_route(
    query_schema=SearchQuerySchema,
    response_schema=SearchResultsSchema,
    ajax_required=True,
    tags=[OPEN_API.SEARCH],
    description="Search across all of the current user's member UTubs, grouped by source UTub.",
    status_codes={200: SearchResultsSchema, 400: ErrorResponse},
)
def search_across_utubs() -> FlaskResponse:
    parsed = parse_query_args(
        SearchQuerySchema,
        message=SearchFailureMessages.INVALID_QUERY,
        error_code=SearchErrorCodes.INVALID_QUERY_PARAM,
    )
    if not isinstance(parsed, BaseModel):
        return parsed
    response_schema = search_across_user_utubs(query=parsed.q, user_id=current_user.id)
    return APIResponse(data=response_schema, status_code=200).to_response()
