from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from urls4irl import db
from urls4irl.models import Utub, Utub_Urls, URLS, Url_Tags
from urls4irl.urls.forms import UTubNewURLForm, UTubEditURLForm, UTubEditURLDescriptionForm
from urls4irl.url_validation import InvalidURLError, check_request_head

urls = Blueprint('urls', __name__)

@urls.route('/url/remove/<int:utub_id>/<int:url_id>', methods=["POST"])
@login_required
def delete_url(utub_id: int, url_id: int):
    """
    User wants to delete a URL from a UTub. Only available to owner of that utub,
    or whoever added the URL into that Utub.

    Args:
        utub_id (int): The ID of the UTub that contains the URL to be deleted
        url_id (int): The ID of the URL to be deleted
    """
    utub = Utub.query.get_or_404(utub_id)
    utub_owner_id = int(utub.created_by.id)
    
    # Search through all urls in the UTub for the one that matches the prescribed URL ID and get the user who added it - should be only one
    url_in_utub = Utub_Urls.query.filter(Utub_Urls.url_id == url_id, Utub_Urls.utub_id == utub_id).first_or_404()

    if current_user.id == utub_owner_id or current_user.id == url_in_utub.user_id:
        # Store serialized data from URL association with UTub and associated tags
        serialized_url_in_utub = url_in_utub.serialized

        # Can only delete URLs as the creator of UTub, or as the adder of that URL
        db.session.delete(url_in_utub)

        # Remove all tags associated with this URL in this UTub as well
        Url_Tags.query.filter_by(utub_id=utub_id, url_id=url_id).delete()

        db.session.commit()
        
        return jsonify({
            "Status" : "Success",
            "Message": "URL removed from this UTub",
            "URL" : serialized_url_in_utub,
            "UTub_ID" : f"{utub.id}",
            "UTub_name" : f"{utub.name}"
        }), 200

    else:
        # Can only delete URLs you added, or if you are the creator of this UTub
        return jsonify({
                "Status" : "Failure",
                "Message" : "Unable to remove this URL",
            }), 403


@urls.route('/url/add/<int:utub_id>', methods=["POST"])
@login_required
def add_url(utub_id: int):
    """
    User wants to add URL to UTub. On success, adds the URL to the UTub.
    
    Args:
        utub_id (int): The Utub to add this URL to
    """
    utub = Utub.query.get_or_404(utub_id)

    if current_user.id not in [member.user_id for member in utub.members]:
        # Not authorized to add URL to this UTub
        return jsonify({
            "Status" : "Failure",
            "Message" : "Unable to add this URL",
            "Error_code": 1
        }), 403

    utub_new_url_form = UTubNewURLForm()

    if utub_new_url_form.validate_on_submit():
        url_string = utub_new_url_form.url_string.data

        try:
            normalized_url = check_request_head(url_string)
        except InvalidURLError:
            # URL was unable to be verified as a valid URL
            return jsonify({
                    "Status" : "Failure",
                    "Message" : "Unable to add this URL",
                    "Error_code": 2
            }), 400

        # Check if URL already exists
        already_created_url = URLS.query.filter_by(url_string=normalized_url).first()

        if not already_created_url:
            # If URL does not exist, add it and then associate it with the UTub
            new_url = URLS(normalized_url=normalized_url, current_user_id=current_user.get_id())

            # Commit new URL to the database
            db.session.add(new_url)
            db.session.commit()

            # Associate URL with given UTub
            url_id = new_url.id
            url_utub_user_add = Utub_Urls(utub_id=utub_id, url_id=url_id, user_id=current_user.id)
            db.session.add(url_utub_user_add)
            db.session.commit()

            # Successfully added a URL, and associated it to a UTub
            return jsonify({
                "Status" : "Success",
                "Message" : "New URL created and added to UTub",
                "URL" : {
                    "url_string": f"{normalized_url}",
                    "url_ID" : f"{url_id}"
                },
                "UTub_ID" : f"{utub_id}",
                "UTub_name" : f"{utub.name}",
                "Added_by" : f"{current_user.get_id()}"
            }), 200
        
        else:
            # If URL does already exist, check if associated with UTub
            url_id = already_created_url.id
            utub_url_if_already_exists = Utub_Urls.query.filter_by(utub_id=utub_id, url_id=url_id).first()

            if utub_url_if_already_exists is None:
                # URL exists and is not associated with a UTub, so associate this URL with this UTub
                new_url_utub_association = Utub_Urls(utub_id=utub_id, url_id=already_created_url.id, user_id=current_user.id)
                db.session.add(new_url_utub_association)
                db.session.commit()

                # Succesfully associated the URL with a new UTub
                return jsonify({
                    "Status" : "Success",
                    "Message" : "URL added to UTub",
                    "URL" : {
                        "url_string": f"{normalized_url}",
                        "url_ID" : f"{url_id}"
                    },
                    "UTub_ID" : f"{utub_id}",
                    "UTub_name" : f"{utub.name}",
                    "Added_by" : f"{current_user.get_id()}"
                }), 200
                
            else:
                # URL already exists in UTub
                return jsonify({
                        "Status" : "Failure",
                        "Message" : "URL already in UTub",
                        "Error_code": 3
                }), 400

    # Invalid form input
    if utub_new_url_form.errors is not None:
        return jsonify({
            "Status": "Failure",
            "Message": "Unable to add this URL, please check inputs",
            "Error_code": 4,
            "Errors": utub_new_url_form.errors
        }), 404

    # Something else went wrong
    return jsonify({
        "Status" : "Failure",
        "Message" : "Unable to add this URL",
        "Error_code": 5
    }), 404


@urls.route('/url/edit/<int:utub_id>/<int:url_id>', methods=["POST"])
@login_required
def edit_url(utub_id: int, url_id: int):
    """
    Edits the URL contained in the UTub.
    If user makes no edits or produces the same URL, then no edits occur.

    If the user provides a different URL, then remove the old URL from URL-UTUB association table, and 
    add in the new one. 
        If the new URL does not exist in the URLS table, first add it there.
    """
    print(request.data)
    return jsonify({"Status" : "Success"}), 200
