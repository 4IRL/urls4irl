from flask import Blueprint, jsonify
from flask_login import current_user, login_required
from urls4irl import db
from urls4irl.models import Utub, Utub_Users
from urls4irl.utubs.forms import UTubForm, UTubDescriptionForm

utubs = Blueprint('utubs', __name__)

@utubs.route('/utub/new', methods=["POST"])
@login_required
def create_utub():
    """
    User wants to create a new utub.
    Assocation Object:
    https://docs.sqlalchemy.org/en/14/orm/basic_relationships.html#many-to-many
    
    """

    utub_form = UTubForm()

    if utub_form.validate_on_submit():
        name = utub_form.name.data
        description = utub_form.description.data
        new_utub = Utub(name=name, utub_creator=current_user.get_id(), utub_description=description)
        creator_to_utub = Utub_Users()
        creator_to_utub.to_user = current_user
        new_utub.members.append(creator_to_utub)
        db.session.commit()
        
        # Add time made?
        return jsonify({
            "Status": "Success",
            "UTub_ID" : f"{new_utub.id}", 
            "UTub_name" : f"{new_utub.name}",
            "UTub_description" : f"{description}",
            "UTub_creator_id": f"{current_user.get_id()}"
        }), 200

    return jsonify({
        "Status": "Failure",
        "Message" : "Unable to generate a new UTub with that information."
    }), 404  

@utubs.route('/utub/delete/<int:utub_id>', methods=["POST"])
@login_required
def delete_utub(utub_id: int):
    """
    Creator wants to delete their UTub. It deletes all associations between this UTub and its contained
    URLS and users.

    https://docs.sqlalchemy.org/en/13/orm/cascades.html#delete

    Args:
        utub_id (int): The ID of the UTub to be deleted
    """
    try:
        # Is this necessary?
        utub_id_to_delete = int(utub_id)

    except ValueError: 
        return jsonify({
            "Status" : "Failure",
            "Message" : "You don't have permission to delete this UTub!"
        }), 404

    utub = Utub.query.get_or_404(utub_id_to_delete)

    if int(current_user.get_id()) != int(utub.created_by.id):  
        return jsonify({
            "Status" : "Failure",
            "Message": "You don't have permission to delete this UTub!"
        }), 403
    
    else:
        utub = Utub.query.get_or_404(int(utub_id))
        db.session.delete(utub)
        db.session.commit()

        return jsonify({
            "Status" : "Success",
            "Message" : "UTub deleted",
            "Utub_ID" : f"{utub.id}", 
            "Utub_name" : f"{utub.name}",
            "UTub_description" : f"{utub.utub_description}",
        }), 200

@utubs.route('/utub/edit_description/<int:utub_id>', methods=["POST"])
@login_required
def update_utub_desc(utub_id: int):
    """
    Creator wants to update their UTub description.
    Description limit is 500 characters.
    Form data required to be sent from the frontend with a parameter "url_description".
    
    On POST:
        The new description is saved to the database for that UTub.

    Args:
        utub_id (int): The ID of the UTub that will have its description updated
    """
    current_utub = Utub.query.get_or_404(int(utub_id))
    
    if int(current_user.get_id()) not in [int(member.user_id) for member in current_utub.members]:
        return jsonify({
            "Status" : "Failure",
            "Message": "You do not have permission to edit this UTub's description",
            "UTub_description": f"{current_utub.utub_description}"
        }), 403

    current_utub_description = "" if current_utub.utub_description is None else current_utub.utub_description

    utub_desc_form = UTubDescriptionForm()

    if utub_desc_form.validate_on_submit():
        new_utub_description = utub_desc_form.utub_description.data

        if new_utub_description != current_utub_description:
            current_utub.utub_description = new_utub_description
            db.session.commit()

        return jsonify({
            "Status": "Success",
            "UTub_ID": f"{current_utub.id}",
            "UTub_description": f"{current_utub.utub_description}"
        }), 200

    return jsonify({
        "Status" : "Failure",
        "Message" : "Unable to modify this UTub's description"
    }), 404
