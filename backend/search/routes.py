from __future__ import annotations

from flask import Blueprint, request
from flask_login import current_user
from pydantic import BaseModel, ValidationError

from backend.api_common.auth_decorators import email_validation_required
from backend.api_common.parse_request import api_route
from backend.api_common.request_errors import pydantic_errors_to_dict
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.schemas.errors import ErrorResponse, build_field_error_response
from backend.schemas.requests.search import SearchQuerySchema
from backend.schemas.search import SearchResultsSchema
from backend.search.constants import SearchErrorCodes, SearchFailureMessages
from backend.search.services.cross_utub_search import search_across_user_utubs
from backend.utils.strings.openapi_strs import OPEN_API

search = Blueprint("search", __name__)


def _parse_query_args(schema_cls: type[BaseModel]) -> BaseModel | FlaskResponse:
    """Validate `request.args` against the query schema.

    Returns the validated model on success or a 400 field-error response on
    `ValidationError`. The caller checks `isinstance(result, BaseModel)` to
    short-circuit on the error branch — `@api_route(query_schema=...)` is
    OpenAPI metadata only and does not validate at runtime.
    """
    try:
        return schema_cls.model_validate(request.args.to_dict(flat=True))
    except ValidationError as validation_error:
        return build_field_error_response(
            message=SearchFailureMessages.INVALID_QUERY,
            errors=pydantic_errors_to_dict(validation_error),
            error_code=SearchErrorCodes.INVALID_QUERY_PARAM,
            status_code=400,
        )


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
    parsed = _parse_query_args(SearchQuerySchema)
    if not isinstance(parsed, BaseModel):
        return parsed
    response_schema = search_across_user_utubs(query=parsed.q, user_id=current_user.id)
    return APIResponse(data=response_schema, status_code=200).to_response()
