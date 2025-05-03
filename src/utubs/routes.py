from itertools import islice
from flask import (
    Blueprint,
    abort,
    current_app,
    jsonify,
    redirect,
    request,
    render_template,
    url_for,
)
from flask_login import current_user
from sqlalchemy.exc import DataError

from src import db
from src.app_logger import (
    critical_log,
    safe_add_log,
    safe_add_many_logs,
    turn_form_into_str_for_log,
    warning_log,
)
from src.models.utubs import Utubs
from src.models.utub_members import Member_Role, Utub_Members
from src.utils.strings.config_strs import CONFIG_ENVS
from src.utils.strings.model_strs import MODELS
from src.utubs.forms import UTubForm, UTubDescriptionForm, UTubNewNameForm
from src.utubs.utils import build_form_errors
from src.utils.all_routes import ROUTES
from src.utils.constants import CONSTANTS
from src.utils.strings.json_strs import STD_JSON_RESPONSE
from src.utils.strings.url_validation_strs import URL_VALIDATION
from src.utils.strings.utub_strs import UTUB_ID_QUERY_PARAM, UTUB_SUCCESS, UTUB_FAILURE
from src.utils.email_validation import email_validation_required

utubs = Blueprint("utubs", __name__)

# Standard response for JSON messages
STD_JSON = STD_JSON_RESPONSE


@utubs.context_processor
def provide_constants():
    return dict(CONSTANTS=CONSTANTS())


@utubs.route("/home", methods=["GET"])
@email_validation_required
def home():
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
        utub_details = current_user.serialized_on_initial_load
        safe_add_log("Returning user's UTubs on home page load")

        return render_template(
            "home.html",
            utubs_for_this_user=utub_details[MODELS.UTUBS],
            is_prod_or_testing=current_app.config.get(
                CONFIG_ENVS.TESTING_OR_PROD, True
            ),
        )

    # Count total number of query param keys/values, even for repeats
    query_param_pairs = list(islice(request.args.items(multi=True), 2))

    if len(query_param_pairs) != 1 or UTUB_ID_QUERY_PARAM not in request.args.keys():
        log_msg = (
            "Too many query parameters"
            if len(query_param_pairs) != 1
            else "Does not contain 'UTubID' as a query parameter"
        )
        log_msg = f"User={current_user.id} | " + log_msg
        warning_log(log_msg)
        abort(404)

    utub_id = request.args.get(UTUB_ID_QUERY_PARAM, "")
    try:
        if (
            Utubs.query.get_or_404(int(utub_id))
            and Utub_Members.query.get((int(utub_id), current_user.id)) is None
        ):
            warning_log(f"User={current_user.id} not a member of UTub.id={utub_id}")
            return redirect(url_for(ROUTES.UTUBS.HOME))

        safe_add_log(f"Retrieving UTub.id={utub_id} from query parameter")
        utub_details = current_user.serialized_on_initial_load
        return render_template(
            "home.html",
            utubs_for_this_user=utub_details[MODELS.UTUBS],
            is_prod_or_testing=current_app.config.get(
                CONFIG_ENVS.TESTING_OR_PROD, True
            ),
        )

    except (ValueError, DataError):
        # Handle invalid UTubID passed as query parameter
        warning_log(f"Invalid UTub.id={utub_id} for User={current_user.id}")
        abort(404)


@utubs.route("/utubs/<int:utub_id>", methods=["GET"])
@email_validation_required
def get_single_utub(utub_id: int):
    """
    Retrieves data for a single UTub, and returns it in a serialized format
    """
    if (
        request.headers.get(URL_VALIDATION.X_REQUESTED_WITH, None)
        != URL_VALIDATION.XMLHTTPREQUEST
    ):
        # Ensures JSON not viewed in browser, happens if user does a refresh with URL /home?UTubID=X, which would otherwise return JSON normally
        warning_log(f"User {current_user.id} did not make an AJAX request")
        return redirect(url_for(ROUTES.UTUBS.HOME))

    assert Utub_Members.query.get_or_404((utub_id, current_user.id))

    utub: Utubs = Utubs.query.get_or_404(utub_id)
    utub_data_serialized = utub.serialized(current_user.id)

    utub.set_last_updated()
    db.session.commit()

    safe_add_log(f"Retrieving UTub.id={utub_id} from direct route")
    return jsonify(utub_data_serialized)


@utubs.route("/utubs", methods=["GET"])
@email_validation_required
def get_utubs():
    """
    User wants a summary of their UTubs in JSON format.
    """
    if (
        request.headers.get(URL_VALIDATION.X_REQUESTED_WITH, None)
        != URL_VALIDATION.XMLHTTPREQUEST
    ):
        # Ensure JSON not shown in the browser
        warning_log(f"User {current_user.id} did not make an AJAX request")
        abort(404)

    # TODO: Should serialized summary be utubID and utubName
    # instead of id and name?
    safe_add_log("Returning user's UTubs from direct route")
    return jsonify(current_user.serialized_on_initial_load)


@utubs.route("/utubs", methods=["POST"])
@email_validation_required
def create_utub():
    """
    User wants to create a new utub.
    Assocation Object:
    https://docs.sqlalchemy.org/en/14/orm/basic_relationships.html#many-to-many

    """
    utub_form: UTubForm = UTubForm()

    if utub_form.validate_on_submit():
        name = utub_form.name.data
        description = (
            utub_form.description.data if utub_form.description.data is not None else ""
        )
        new_utub = Utubs(
            name=name, utub_creator=current_user.id, utub_description=description  # type: ignore
        )
        db.session.add(new_utub)
        db.session.commit()

        creator_to_utub = Utub_Members()
        creator_to_utub.user_id = current_user.id
        creator_to_utub.utub_id = new_utub.id
        creator_to_utub.member_role = Member_Role.CREATOR
        db.session.add(creator_to_utub)
        db.session.commit()

        safe_add_many_logs(
            [
                "Created UTub",
                f"UTub.id={new_utub.id}",
                f"UTub.name={name}",
            ]
        )
        # Add time made?
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.SUCCESS,
                    UTUB_SUCCESS.UTUB_ID: new_utub.id,
                    UTUB_SUCCESS.UTUB_NAME: new_utub.name,
                    UTUB_SUCCESS.UTUB_DESCRIPTION: description,
                    UTUB_SUCCESS.UTUB_CREATOR_ID: current_user.id,
                }
            ),
            200,
        )

    # Invalid form inputs
    if utub_form.errors is not None:
        warning_log(
            f"User {current_user.id} | Invalid form: {turn_form_into_str_for_log(utub_form.errors)}"
        )
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: UTUB_FAILURE.UNABLE_TO_MAKE_UTUB,
                    STD_JSON.ERROR_CODE: 1,
                    STD_JSON.ERRORS: build_form_errors(utub_form),
                }
            ),
            400,
        )

    critical_log(f"User {current_user.id} failed to make UTub")
    return (
        jsonify(
            {
                STD_JSON.STATUS: STD_JSON.FAILURE,
                STD_JSON.MESSAGE: UTUB_FAILURE.UNABLE_TO_MAKE_UTUB,
                STD_JSON.ERROR_CODE: 2,
            }
        ),
        404,
    )


@utubs.route("/utubs/<int:utub_id>", methods=["DELETE"])
@email_validation_required
def delete_utub(utub_id: int):
    """
    Creator wants to delete their UTub. It deletes all associations between this UTub and its contained
    URLS, tags, and users.

    https://docs.sqlalchemy.org/en/13/orm/cascades.html#delete

    Args:
        utub_id (int): The ID of the UTub to be deleted
    """
    utub: Utubs = Utubs.query.get_or_404(utub_id)

    if current_user.id != utub.utub_creator:
        critical_log(
            f"User={current_user.id} is not the creator of UTub.id={utub.id} | UTub.name={utub.name}"
        )
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: UTUB_FAILURE.NOT_AUTHORIZED,
                }
            ),
            403,
        )

    else:
        db.session.delete(utub)
        db.session.commit()

        safe_add_many_logs(
            [
                "Deleted UTub",
                f"UTub.id={utub.id}",
                f"UTub.name={utub.name}",
            ]
        )

        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.SUCCESS,
                    STD_JSON.MESSAGE: UTUB_SUCCESS.UTUB_DELETED,
                    UTUB_SUCCESS.UTUB_ID: utub.id,
                    UTUB_SUCCESS.UTUB_NAME: utub.name,
                    UTUB_SUCCESS.UTUB_DESCRIPTION: utub.utub_description,
                }
            ),
            200,
        )


@utubs.route("/utubs/<int:utub_id>/name", methods=["PATCH"])
@email_validation_required
def update_utub_name(utub_id: int):
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
    current_utub: Utubs = Utubs.query.get_or_404(utub_id)

    if current_user.id != current_utub.utub_creator:
        warning_log(
            f"User {current_user.id} not creator: UTub.id={current_utub.id} | UTub.name={current_utub.name}"
        )
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: UTUB_FAILURE.NOT_AUTHORIZED,
                    STD_JSON.ERROR_CODE: 1,
                }
            ),
            403,
        )

    current_utub_name = current_utub.name

    utub_name_form: UTubNewNameForm = UTubNewNameForm()

    if utub_name_form.validate_on_submit():
        new_utub_name = utub_name_form.name.data

        if new_utub_name != current_utub_name:
            current_utub.name = new_utub_name  # type: ignore
            current_utub.set_last_updated()
            db.session.commit()

            safe_add_many_logs(
                [
                    "User updated UTub name",
                    f"UTub.id={current_utub.id}",
                    f"OLD UTub.name={current_utub_name}",
                    f"NEW UTub.name={new_utub_name}",
                ]
            )

        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.SUCCESS,
                    UTUB_SUCCESS.UTUB_ID: current_utub.id,
                    UTUB_SUCCESS.UTUB_NAME: current_utub.name,
                }
            ),
            200,
        )

    # Invalid form errors
    if utub_name_form.errors is not None:
        warning_log(
            f"User {current_user.id} | Invalid form: {turn_form_into_str_for_log(utub_name_form)}"
        )
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: UTUB_FAILURE.UNABLE_TO_MODIFY_UTUB_NAME,
                    STD_JSON.ERROR_CODE: 2,
                    STD_JSON.ERRORS: build_form_errors(utub_name_form),
                }
            ),
            400,
        )

    critical_log(f"User {current_user.id} | Unable to update UTub name")
    return (
        jsonify(
            {
                STD_JSON.STATUS: STD_JSON.FAILURE,
                STD_JSON.MESSAGE: UTUB_FAILURE.UNABLE_TO_MODIFY_UTUB_NAME,
                STD_JSON.ERROR_CODE: 3,
            }
        ),
        404,
    )


@utubs.route("/utubs/<int:utub_id>/description", methods=["PATCH"])
@email_validation_required
def update_utub_desc(utub_id: int):
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
    current_utub: Utubs = Utubs.query.get_or_404(utub_id)

    if current_user.id != current_utub.utub_creator:
        warning_log(
            f"User {current_user.id} not creator: UTub.id={current_utub.id} | UTub.name={current_utub.name}"
        )
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: UTUB_FAILURE.NOT_AUTHORIZED,
                    STD_JSON.ERROR_CODE: 1,
                }
            ),
            403,
        )

    current_utub_description = (
        "" if current_utub.utub_description is None else current_utub.utub_description
    )

    utub_desc_form: UTubDescriptionForm = UTubDescriptionForm()

    if utub_desc_form.validate_on_submit():
        new_utub_description = utub_desc_form.description.data

        if new_utub_description is None:
            warning_log(f"User {current_user.id} | UTub description was None")
            return (
                jsonify(
                    {
                        STD_JSON.STATUS: STD_JSON.FAILURE,
                        STD_JSON.MESSAGE: UTUB_FAILURE.UNABLE_TO_MODIFY_UTUB_DESC,
                        STD_JSON.ERROR_CODE: 2,
                    }
                ),
                400,
            )

        if new_utub_description != current_utub_description:
            current_utub.utub_description = new_utub_description
            current_utub.set_last_updated()
            db.session.commit()

            safe_add_many_logs(
                [
                    "Updated UTub description",
                    f"UTub.id={current_utub.id}",
                    f"OLD UTub.description={current_utub_description}",
                    f"NEW UTub.name={new_utub_description}",
                ]
            )

        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.SUCCESS,
                    UTUB_SUCCESS.UTUB_ID: current_utub.id,
                    UTUB_SUCCESS.UTUB_DESCRIPTION: current_utub.utub_description,
                }
            ),
            200,
        )

    # Invalid form input
    if utub_desc_form.errors is not None:
        warning_log(
            f"User {current_user.id} | Invalid form: {turn_form_into_str_for_log(utub_desc_form)}"
        )
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: UTUB_FAILURE.UNABLE_TO_MODIFY_UTUB_DESC,
                    STD_JSON.ERROR_CODE: 3,
                    STD_JSON.ERRORS: build_form_errors(utub_desc_form),
                }
            ),
            400,
        )

    critical_log(f"User {current_user.id} | Unable to update UTub description")
    return (
        jsonify(
            {
                STD_JSON.STATUS: STD_JSON.FAILURE,
                STD_JSON.MESSAGE: UTUB_FAILURE.UNABLE_TO_MODIFY_UTUB_DESC,
                STD_JSON.ERROR_CODE: 4,
            }
        ),
        404,
    )
