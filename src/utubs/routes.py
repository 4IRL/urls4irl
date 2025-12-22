from flask import (
    Blueprint,
    abort,
    redirect,
    request,
    url_for,
)
from werkzeug.wrappers import Response as WerkzeugResponse

from src.api_common.auth_decorators import (
    email_validation_required,
    utub_creator_required,
    utub_membership_required,
    xml_http_request_only,
)
from src.api_common.responses import FlaskResponse
from src.models.utubs import Utubs
from src.utils.strings.utub_strs import UTUB_ID_QUERY_PARAM
from src.utubs.forms import UTubDescriptionForm, UTubNewNameForm
from src.utubs.services.create_utubs import create_new_utub
from src.utubs.services.delete_utubs import delete_utub_for_user
from src.utubs.services.home_page import (
    render_home_page,
    validate_query_param_is_utub_id,
    validate_user_is_member_of_utub_on_home_page_with_query_param,
)
from src.utubs.services.read_utubs import (
    get_all_utubs_of_user,
    get_single_utub_for_user,
)
from src.utubs.services.update_utubs import (
    handle_invalid_update_utub_description_form_input,
    handle_invalid_update_utub_name_form_input,
    update_utub_desc_if_new,
    update_utub_name_if_new,
)
from src.utils.all_routes import ROUTES
from src.utils.constants import provide_config_for_constants

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
def create_utub() -> FlaskResponse:
    return create_new_utub()


@utubs.route("/utubs/<int:utub_id>", methods=["GET"])
@xml_http_request_only
@utub_membership_required
def get_single_utub(utub_id: int, current_utub: Utubs) -> FlaskResponse:
    """
    Retrieves data for a single UTub, and returns it in a serialized format
    """
    return get_single_utub_for_user(current_utub)


@utubs.route("/utubs", methods=["GET"])
@xml_http_request_only
@email_validation_required
def get_utubs() -> FlaskResponse:
    """
    User wants a summary of their UTubs in JSON format.
    """
    return get_all_utubs_of_user()


@utubs.route("/utubs/<int:utub_id>/name", methods=["PATCH"])
@utub_creator_required
def update_utub_name(utub_id: int, current_utub: Utubs) -> FlaskResponse:
    """
    Creator wants to update their UTub name.
    Name limit is 30 characters.
    Form data required to be sent from the frontend with a parameter "name".

    Input is required and the new name cannot be empty. Members cannot update UTub names. Creators
    of other UTubs cannot update another UTub's name. The "name" field must be included in the form.

    On PATCH:
        The new name is saved to the database for that UTub.

    Args:
        utub_id (int): The ID of the UTub that will have its description updated
    """
    utub_name_form: UTubNewNameForm = UTubNewNameForm()

    if not utub_name_form.validate_on_submit():
        return handle_invalid_update_utub_name_form_input(utub_name_form)

    return update_utub_name_if_new(
        current_utub=current_utub, utub_name_form=utub_name_form
    )


@utubs.route("/utubs/<int:utub_id>/description", methods=["PATCH"])
@utub_creator_required
def update_utub_desc(utub_id: int, current_utub: Utubs) -> FlaskResponse:
    """
    Creator wants to update their UTub description.
    Description limit is 500 characters.
    Form data required to be sent from the frontend with a parameter "utub_description".

    Members cannot update UTub descriptions. Creators of other UTubs cannot update another
    UTub's name. The "utub_description" field must be contained in the form. The description
    can be made blank if desired.

    On POST:
        The new description is saved to the database for that UTub.

    Args:
        utub_id (int): The ID of the UTub that will have its description updated
    """

    utub_desc_form: UTubDescriptionForm = UTubDescriptionForm()

    if not utub_desc_form.validate_on_submit():
        return handle_invalid_update_utub_description_form_input(utub_desc_form)

    return update_utub_desc_if_new(
        current_utub=current_utub, utub_desc_form=utub_desc_form
    )


@utubs.route("/utubs/<int:utub_id>", methods=["DELETE"])
@utub_creator_required
def delete_utub(utub_id: int, current_utub: Utubs) -> FlaskResponse:
    """
    Creator wants to delete their UTub. It deletes all associations between this UTub and its contained
    URLS, tags, and users.

    Args:
        utub_id (int): The ID of the UTub to be deleted
    """
    return delete_utub_for_user(current_utub)
