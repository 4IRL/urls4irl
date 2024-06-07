from flask import Blueprint, jsonify, request, render_template, abort
from flask_login import current_user

from src import db
from src.models.utubs import Utubs
from src.models.utub_members import Member_Role, Utub_Members
from src.utubs.forms import UTubForm, UTubDescriptionForm, UTubNewNameForm
from src.utubs.utils import build_form_errors
from src.utils.strings.json_strs import STD_JSON_RESPONSE
from src.utils.strings.utub_strs import UTUB_SUCCESS, UTUB_FAILURE
from src.utils.email_validation import email_validation_required

utubs = Blueprint("utubs", __name__)

# Standard response for JSON messages
STD_JSON = STD_JSON_RESPONSE


@utubs.route("/home", methods=["GET"])
@email_validation_required
def home():
    """
    Home page for logged in user. Loads and displays all UTubs, and contained URLs.

    Args:
        /home : With no args, this returns all UTubIDs for the given user
        /home?UTubID=[int] = Where the integer value is the associated UTubID
                                that the user clicked on

    Returns:
        - All UTubIDs if no args
        - Requested UTubID if a valid arg

    """
    if not request.args:
        # User got here without any arguments in the URL
        # Therefore, only provide UTub name and UTub ID
        utub_details = jsonify(current_user.serialized_on_initial_load)
        return render_template("home.html", utubs_for_this_user=utub_details.json)

    elif "UTubID" in request.args and len(request.args) == 1:
        return get_single_utub(request.args.get("UTubID"))

    abort(404)


def get_single_utub(utub_id: str):
    """
    Retrieves data for a single UTub, and returns it in a serialized format
    """
    user_in_utub: Utub_Members = Utub_Members.query.get((utub_id, current_user.id))

    if user_in_utub is None:
        # User is not member of the UTub they are requesting
        abort(404)

    utub: Utubs = Utubs.query.get_or_404(utub_id)
    utub_data_serialized = utub.serialized(current_user.id)
    return jsonify(utub_data_serialized)


@utubs.route("/utubs", methods=["GET"])
@email_validation_required
def get_utubs():
    """
    User wants a summary of their UTubs in JSON format.
    """
    # TODO: Should serialized summary be utubID and utubName
    # instead of id and name?
    return jsonify(current_user.serialized_on_initial_load)


@utubs.route("/utubs", methods=["POST"])
@email_validation_required
def add_utub():
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
            name=name, utub_creator=current_user.id, utub_description=description
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
            current_utub.name = new_utub_name
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
                    STD_JSON.MESSAGE: UTUB_FAILURE.UTUB_DESC_TOO_LONG,
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
