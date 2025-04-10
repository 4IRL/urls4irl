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
        return render_template(
            "home.html",
            utubs_for_this_user=utub_details[MODELS.UTUBS],
            is_prod_or_testing=current_app.config.get(
                CONFIG_ENVS.TESTING_OR_PROD, True
            ),
        )

    if len(request.args) != 1 or UTUB_ID_QUERY_PARAM not in request.args.keys():
        abort(404)

    utub_id = request.args.get(UTUB_ID_QUERY_PARAM, "")
    try:
        if (
            Utubs.query.get_or_404(int(utub_id))
            and Utub_Members.query.get((int(utub_id), current_user.id)) is None
        ):
            return redirect(url_for(ROUTES.UTUBS.HOME))

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
        return redirect(url_for(ROUTES.UTUBS.HOME))

    assert Utub_Members.query.get_or_404((utub_id, current_user.id))

    utub: Utubs = Utubs.query.get_or_404(utub_id)
    utub_data_serialized = utub.serialized(current_user.id)

    utub.set_last_updated()
    db.session.commit()

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
        abort(404)

    # TODO: Should serialized summary be utubID and utubName
    # instead of id and name?
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
