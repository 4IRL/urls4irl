from flask import Blueprint, jsonify
from flask_login import current_user
from urls4irl import db
from urls4irl.models import Utub, Utub_Users
from urls4irl.utubs.forms import UTubForm, UTubDescriptionForm, UTubNewNameForm
from urls4irl.utils import strings as U4I_STRINGS
from urls4irl.utils.email_validation import email_validation_required

utubs = Blueprint("utubs", __name__)

# Standard response for JSON messages
STD_JSON = U4I_STRINGS.STD_JSON_RESPONSE
UTUB_FAILURE = U4I_STRINGS.UTUB_FAILURE
UTUB_SUCCESS = U4I_STRINGS.UTUB_SUCCESS


@utubs.route("/utub/new", methods=["POST"])
@email_validation_required
def create_utub():
    """
    User wants to create a new utub.
    Assocation Object:
    https://docs.sqlalchemy.org/en/14/orm/basic_relationships.html#many-to-many

    """

    utub_form = UTubForm()

    if utub_form.validate_on_submit():
        name = utub_form.name.data
        description = (
            utub_form.description.data if utub_form.description.data is not None else ""
        )
        new_utub = Utub(
            name=name, utub_creator=current_user.get_id(), utub_description=description
        )
        creator_to_utub = Utub_Users()
        creator_to_utub.to_user = current_user
        new_utub.members.append(creator_to_utub)
        db.session.commit()

        # Add time made?
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.SUCCESS,
                    UTUB_SUCCESS.UTUB_ID: int(new_utub.id),
                    UTUB_SUCCESS.UTUB_NAME: f"{new_utub.name}",
                    UTUB_SUCCESS.UTUB_DESCRIPTION: f"{description}",
                    UTUB_SUCCESS.UTUB_CREATOR_ID: int(current_user.get_id()),
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
                    STD_JSON.ERRORS: utub_form.errors,
                }
            ),
            404,
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


@utubs.route("/utub/delete/<int:utub_id>", methods=["POST"])
@email_validation_required
def delete_utub(utub_id: int):
    """
    Creator wants to delete their UTub. It deletes all associations between this UTub and its contained
    URLS and users.

    https://docs.sqlalchemy.org/en/13/orm/cascades.html#delete

    Args:
        utub_id (int): The ID of the UTub to be deleted
    """
    utub_id_to_delete = int(utub_id)

    utub = Utub.query.get_or_404(utub_id_to_delete)

    if int(current_user.get_id()) != int(utub.created_by.id):
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
                    UTUB_SUCCESS.UTUB_ID: f"{utub.id}",
                    UTUB_SUCCESS.UTUB_NAME: f"{utub.name}",
                    UTUB_SUCCESS.UTUB_DESCRIPTION: f"{utub.utub_description}",
                }
            ),
            200,
        )


@utubs.route("/utub/edit_name/<int:utub_id>", methods=["POST"])
@email_validation_required
def update_utub_name(utub_id: int):
    """
    Creator wants to update their UTub name.
    Name limit is 30 characters.
    Form data required to be sent from the frontend with a parameter "name".

    Input is required and the new name cannot be empty. Members cannot update UTub names. Creators
    of other UTubs cannot update another UTub's name. The "name" field must be included in the form.

    On POST:
        The new name is saved to the database for that UTub.

    Args:
        utub_id (int): The ID of the UTub that will have its description updated
    """
    current_utub = Utub.query.get_or_404(utub_id)

    if int(current_user.get_id()) != current_utub.created_by.id:
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

    utub_name_form = UTubNewNameForm()

    if utub_name_form.validate_on_submit():
        new_utub_name = utub_name_form.name.data

        if new_utub_name != current_utub_name:
            current_utub.name = new_utub_name
            db.session.commit()

        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.SUCCESS,
                    UTUB_SUCCESS.UTUB_ID: current_utub.id,
                    UTUB_SUCCESS.UTUB_NAME: current_utub.name,
                    UTUB_SUCCESS.UTUB_DESCRIPTION: current_utub.utub_description,
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
                    STD_JSON.ERRORS: utub_name_form.errors,
                }
            ),
            404,
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


@utubs.route("/utub/edit_description/<int:utub_id>", methods=["POST"])
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
    current_utub = Utub.query.get_or_404(utub_id)

    if int(current_user.get_id()) != current_utub.created_by.id:
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: UTUB_FAILURE.NOT_AUTHORIZED,
                    STD_JSON.ERROR_CODE: 1,
                    UTUB_FAILURE.UTUB_DESCRIPTION: current_utub.utub_description,
                }
            ),
            403,
        )

    current_utub_description = (
        "" if current_utub.utub_description is None else current_utub.utub_description
    )

    utub_desc_form = UTubDescriptionForm()

    if utub_desc_form.validate_on_submit():
        new_utub_description = utub_desc_form.utub_description.data

        if new_utub_description is None:
            return (
                jsonify(
                    {
                        STD_JSON.STATUS: STD_JSON.FAILURE,
                        STD_JSON.MESSAGE: UTUB_FAILURE.UNABLE_TO_MODIFY_UTUB_DESC,
                        STD_JSON.ERROR_CODE: 2,
                    }
                ),
                404,
            )

        if new_utub_description != current_utub_description:
            current_utub.utub_description = new_utub_description
            db.session.commit()

        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.SUCCESS,
                    UTUB_SUCCESS.UTUB_ID: current_utub.id,
                    UTUB_SUCCESS.UTUB_NAME: current_utub.name,
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
                    STD_JSON.ERRORS: utub_desc_form.errors,
                }
            ),
            404,
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
