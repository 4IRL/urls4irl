from flask import (
    Blueprint,
    abort,
    redirect,
    request,
    url_for,
)
from werkzeug.wrappers import Response as WerkzeugResponse

from backend.api_common.auth_decorators import (
    email_validation_required,
    utub_creator_required,
    utub_membership_required,
    xml_http_request_only,
)
from backend.api_common.parse_request import api_route
from backend.api_common.responses import FlaskResponse
from backend.models.utubs import Utubs
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
from backend.utils.strings.utub_strs import UTUB_FAILURE, UTUB_ID_QUERY_PARAM
from backend.utubs.constants import UTubErrorCodes
from backend.utubs.services.create_utubs import create_new_utub
from backend.utubs.services.delete_utubs import delete_utub_for_user
from backend.utubs.services.home_page import (
    render_home_page,
    validate_query_param_is_utub_id,
    validate_user_is_member_of_utub_on_home_page_with_query_param,
)
from backend.utubs.services.read_utubs import (
    get_all_utubs_of_user,
    get_single_utub_for_user,
)
from backend.utubs.services.update_utubs import (
    update_utub_desc_if_new,
    update_utub_name_if_new,
)
from backend.utils.all_routes import ROUTES
from backend.utils.constants import provide_config_for_constants

utubs = Blueprint("utubs", __name__)


@utubs.context_processor
def provide_constants():
    return provide_config_for_constants()


@utubs.route("/home", methods=["GET"])
@email_validation_required
def home() -> str | WerkzeugResponse:
    """
    Home page for logged in user. Loads and displays all UTubs, and contained URLs.
    If the query param UTubID is included, the user may be trying to directly access
    a single UTub.

    If the user is not a member of this UTub, or this UTub does not exist, we reroute
    them to their home page, instead of denying them access.

    Selection and loading of the selected UTub via query param is handled on the client.

    URL_VALIDATION
    Args:
        /home : With no args, this returns all UTubIDs for the given user
        /home?UTubID=1 : Returns same as `/home` - UTub selection is handled on the client

    Returns:
        - All UTubIDs and names
    """
    if not request.args:
        return render_home_page()

    if not validate_query_param_is_utub_id():
        abort(404)

    utub_id = request.args.get(UTUB_ID_QUERY_PARAM, "")

    valid_member = validate_user_is_member_of_utub_on_home_page_with_query_param(
        utub_id
    )

    if not valid_member:
        return redirect(url_for(ROUTES.UTUBS.HOME))

    return render_home_page()


@utubs.route("/utubs", methods=["POST"])
@email_validation_required
@api_route(
    request_schema=CreateUTubRequest,
    response_schema=UtubCreatedResponseSchema,
    error_message=UTUB_FAILURE.UNABLE_TO_MAKE_UTUB,
    error_code=UTubErrorCodes.INVALID_FORM_INPUT,
)
def create_utub(create_u_tub_request: CreateUTubRequest) -> FlaskResponse:
    return create_new_utub(
        create_u_tub_request.utubName, create_u_tub_request.utubDescription
    )


@utubs.route("/utubs/<int:utub_id>", methods=["GET"])
@xml_http_request_only
@utub_membership_required
@api_route(response_schema=UtubDetailSchema)
def get_single_utub(utub_id: int, current_utub: Utubs) -> FlaskResponse:
    """
    Retrieves data for a single UTub, and returns it in a serialized format
    """
    return get_single_utub_for_user(current_utub)


@utubs.route("/utubs", methods=["GET"])
@xml_http_request_only
@email_validation_required
@api_route(response_schema=UtubSummaryListSchema)
def get_utubs() -> FlaskResponse:
    """
    User wants a summary of their UTubs in JSON format.
    """
    return get_all_utubs_of_user()


@utubs.route("/utubs/<int:utub_id>/name", methods=["PATCH"])
@utub_creator_required
@api_route(
    request_schema=UpdateUTubNameRequest,
    response_schema=UtubNameUpdatedResponseSchema,
    error_message=UTUB_FAILURE.UNABLE_TO_MODIFY_UTUB_NAME,
    error_code=UTubErrorCodes.INVALID_FORM_INPUT,
)
def update_utub_name(
    utub_id: int, current_utub: Utubs, update_u_tub_name_request: UpdateUTubNameRequest
) -> FlaskResponse:
    """
    Creator wants to update their UTub name.
    Name limit is 30 characters.

    Args:
        utub_id (int): The ID of the UTub that will have its name updated
    """
    return update_utub_name_if_new(current_utub, update_u_tub_name_request.utubName)


@utubs.route("/utubs/<int:utub_id>/description", methods=["PATCH"])
@utub_creator_required
@api_route(
    request_schema=UpdateUTubDescriptionRequest,
    response_schema=UtubDescUpdatedResponseSchema,
    error_message=UTUB_FAILURE.UNABLE_TO_MODIFY_UTUB_DESC,
    error_code=UTubErrorCodes.INVALID_FORM_INPUT,
)
def update_utub_desc(
    utub_id: int,
    current_utub: Utubs,
    update_u_tub_description_request: UpdateUTubDescriptionRequest,
) -> FlaskResponse:
    """
    Creator wants to update their UTub description.
    Description limit is 500 characters.

    Args:
        utub_id (int): The ID of the UTub that will have its description updated
    """
    return update_utub_desc_if_new(
        current_utub, update_u_tub_description_request.utubDescription
    )


@utubs.route("/utubs/<int:utub_id>", methods=["DELETE"])
@utub_creator_required
@api_route(response_schema=UtubDeletedResponseSchema)
def delete_utub(utub_id: int, current_utub: Utubs) -> FlaskResponse:
    """
    Creator wants to delete their UTub. It deletes all associations between this UTub and its contained
    URLS, tags, and users.

    Args:
        utub_id (int): The ID of the UTub to be deleted
    """
    return delete_utub_for_user(current_utub)
