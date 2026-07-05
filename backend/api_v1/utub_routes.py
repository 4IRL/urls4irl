"""
Bearer-token (/api/v1) wrapper routes for UTub CRUD.

Each route is an exact twin of its web counterpart (backend/utubs/routes.py),
with three changes:
  - Session decorator → api_ equivalent
  - ajax_required=False (no X-Requested-With sentinel)
  - tags=[OPEN_API.MOBILE_API] + 401/403 added to status_codes
"""

from backend.api_common.auth_decorators import (
    api_email_validation_required,
    api_utub_creator_required,
    api_utub_membership_required,
)
from backend.api_common.parse_request import api_route
from backend.api_common.responses import FlaskResponse
from backend.api_v1.routes import api_v1
from backend.models.utubs import Utubs
from backend.schemas.errors import ErrorResponse
from backend.schemas.requests.utubs import (
    CreateUTubRequest,
    UpdateUTubDescriptionRequest,
    UpdateUTubNameRequest,
)
from backend.schemas.users import UtubSummaryListSchema
from backend.schemas.utubs import (
    UtubCreatedResponseSchema,
    UtubDeletedResponseSchema,
    UtubDescUpdatedResponseSchema,
    UtubDetailSchema,
    UtubNameUpdatedResponseSchema,
)
from backend.utubs.constants import UTubErrorCodes
from backend.utubs.services.create_utubs import create_new_utub
from backend.utubs.services.delete_utubs import delete_utub_for_user
from backend.utubs.services.read_utubs import (
    get_all_utubs_of_user,
    get_single_utub_for_user,
)
from backend.utubs.services.update_utubs import (
    update_utub_desc_if_new,
    update_utub_name_if_new,
)
from backend.utils.strings.openapi_strs import OPEN_API
from backend.utils.strings.utub_strs import UTUB_FAILURE


@api_v1.route("/utubs", methods=["POST"])
@api_email_validation_required
@api_route(
    request_schema=CreateUTubRequest,
    response_schema=UtubCreatedResponseSchema,
    error_message=UTUB_FAILURE.UNABLE_TO_MAKE_UTUB,
    error_code=UTubErrorCodes.INVALID_FORM_INPUT,
    ajax_required=False,
    tags=[OPEN_API.MOBILE_API],
    description="Create a new UTub",
    status_codes={
        200: UtubCreatedResponseSchema,
        400: ErrorResponse,
        401: ErrorResponse,
        403: ErrorResponse,
    },
)
def api_v1_create_utub(create_utub_request: CreateUTubRequest) -> FlaskResponse:
    """Create a new UTub for the authenticated user."""
    return create_new_utub(
        create_utub_request.utubName, create_utub_request.utubDescription
    )


@api_v1.route("/utubs", methods=["GET"])
@api_email_validation_required
@api_route(
    response_schema=UtubSummaryListSchema,
    ajax_required=False,
    tags=[OPEN_API.MOBILE_API],
    description="Retrieve a summary of all UTubs for the current user",
    status_codes={
        200: UtubSummaryListSchema,
        401: ErrorResponse,
        403: ErrorResponse,
    },
)
def api_v1_get_utubs() -> FlaskResponse:
    """Return a summary list of all UTubs the authenticated user belongs to."""
    return get_all_utubs_of_user()


@api_v1.route("/utubs/<int:utub_id>", methods=["GET"])
@api_utub_membership_required
@api_route(
    response_schema=UtubDetailSchema,
    ajax_required=False,
    tags=[OPEN_API.MOBILE_API],
    description="Retrieve data for a single UTub",
    status_codes={
        200: UtubDetailSchema,
        401: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
)
def api_v1_get_single_utub(utub_id: int, current_utub: Utubs) -> FlaskResponse:
    """Return full detail for a single UTub the authenticated user is a member of."""
    return get_single_utub_for_user(current_utub)


@api_v1.route("/utubs/<int:utub_id>/name", methods=["PATCH"])
@api_utub_creator_required
@api_route(
    request_schema=UpdateUTubNameRequest,
    response_schema=UtubNameUpdatedResponseSchema,
    error_message=UTUB_FAILURE.UNABLE_TO_MODIFY_UTUB_NAME,
    error_code=UTubErrorCodes.INVALID_FORM_INPUT,
    ajax_required=False,
    tags=[OPEN_API.MOBILE_API],
    description="Update a UTub name",
    status_codes={
        200: UtubNameUpdatedResponseSchema,
        400: ErrorResponse,
        401: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
)
def api_v1_update_utub_name(
    utub_id: int,
    current_utub: Utubs,
    update_utub_name_request: UpdateUTubNameRequest,
) -> FlaskResponse:
    """Update the name of a UTub the authenticated user created."""
    return update_utub_name_if_new(current_utub, update_utub_name_request.utubName)


@api_v1.route("/utubs/<int:utub_id>/description", methods=["PATCH"])
@api_utub_creator_required
@api_route(
    request_schema=UpdateUTubDescriptionRequest,
    response_schema=UtubDescUpdatedResponseSchema,
    error_message=UTUB_FAILURE.UNABLE_TO_MODIFY_UTUB_DESC,
    error_code=UTubErrorCodes.INVALID_FORM_INPUT,
    ajax_required=False,
    tags=[OPEN_API.MOBILE_API],
    description="Update a UTub description",
    status_codes={
        200: UtubDescUpdatedResponseSchema,
        400: ErrorResponse,
        401: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
)
def api_v1_update_utub_desc(
    utub_id: int,
    current_utub: Utubs,
    update_utub_description_request: UpdateUTubDescriptionRequest,
) -> FlaskResponse:
    """Update the description of a UTub the authenticated user created."""
    return update_utub_desc_if_new(
        current_utub, update_utub_description_request.utubDescription
    )


@api_v1.route("/utubs/<int:utub_id>", methods=["DELETE"])
@api_utub_creator_required
@api_route(
    response_schema=UtubDeletedResponseSchema,
    ajax_required=False,
    tags=[OPEN_API.MOBILE_API],
    description="Delete a UTub",
    status_codes={
        200: UtubDeletedResponseSchema,
        401: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
)
def api_v1_delete_utub(utub_id: int, current_utub: Utubs) -> FlaskResponse:
    """Delete a UTub the authenticated user created."""
    return delete_utub_for_user(current_utub)
