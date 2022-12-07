from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from urls4irl import db
from urls4irl.models import Utub, Utub_Urls, URLS
from urls4irl.urls.forms import UTubNewURLForm, UTubEditURLForm, UTubEditURLDescriptionForm
from urls4irl.url_validation import check_request_head, InvalidURLError

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
    utub = Utub.query.get(int(utub_id))
    owner_id = int(utub.created_by.id)
    
    # Search through all urls in the UTub for the one that matches the prescribed URL ID and get the user who added it - should be only one
    url_added_by = [url_in_utub.user_that_added_url.id for url_in_utub in utub.utub_urls if int(url_in_utub.url_id) == int(url_id)]

    if len(url_added_by) != 1 or not url_added_by:
        # No user added this URL, or multiple users did...
        return jsonify({
            "Status" : "Failure",
            "Message" : "Unable to remove this URL",
            "Error_code": 1
        }), 404

    # Otherwise, only one user should've added this url - retrieve them
    url_added_by = url_added_by[0]

    if int(current_user.get_id()) == owner_id or int(current_user.get_id()) == url_added_by:
        # User is creator of this UTub, or added the URL
        utub_url_user_row = Utub_Urls.query.filter_by(utub_id=utub_id, url_id=url_id).all()

        if len(utub_url_user_row) > 1:
            # How did this happen? URLs are unique to each UTub, so should only return one
            return jsonify({
                "Status" : "Failure",
                "Message" : "Unable to remove this URL",
                "Error_code": 2
            }), 404

        db.session.delete(utub_url_user_row[0])
        db.session.commit()
        
        return jsonify({
            "Status" : "Success",
            "Message": "URL removed from this UTub",
            "URL" : jsonify(URLS.query.get_or_404(url_id).serialized),
            "UTub_ID" : f"{utub.id}",
            "UTub_name" : f"{utub.name}"
        }), 200

    else:
        # Can only delete URLs you added, or if you are the creator of this UTub
        return jsonify({
                "Status" : "Failure",
                "Message" : "Unable to remove this URL",
                "Error_code": 3
            }), 403


@urls.route('/url/add/<int:utub_id>', methods=["POST"])
@login_required
def add_url(utub_id: int):
    """
    User wants to add URL to UTub. On success, adds the URL to the UTub.
    
    Args:
        utub_id (int): The Utub to add this URL to
    """
    utub = Utub.query.get(int(utub_id))

    if int(current_user.get_id()) not in [int(member.user_id) for member in utub.members]:
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
            validated_url = check_request_head(url_string)
        
        except InvalidURLError:
            return jsonify({
                "Status" : "Failure",
                "Message" : "Unable to add this URL",
                "Error_code": 2
            }), 400

        else: 
            # Get URL if already created
            print(f"Validated URL: {validated_url}")
            already_created_url = URLS.query.filter_by(url_string=validated_url).first()

            if already_created_url:

                # Get all urls currently in utub
                urls_in_utub = [utub_user_url_object.url_in_utub for utub_user_url_object in utub.utub_urls]
            
                #URL already generated, now confirm if within UTUB or not
                if already_created_url in urls_in_utub:
                    # URL already in UTUB
                    return jsonify({
                        "Status" : "Failure",
                        "Message" : "Unable to add this URL",
                        "Error_code": 3
                    }), 400


                url_utub_user_add = Utub_Urls(utub_id=utub_id, url_id=already_created_url.id, user_id=int(current_user.get_id()))
                url_id = already_created_url.id

            else:
                # Else create new URL and append to the UTUB
                new_url = URLS(url_string=validated_url, created_by=int(current_user.get_id()))
                db.session.add(new_url)
                db.session.commit()
                url_utub_user_add = Utub_Urls(utub_id=utub_id, url_id=new_url.id, user_id=int(current_user.get_id()))
                url_id = new_url.id
                
            db.session.add(url_utub_user_add)
            db.session.commit()

            # Successfully added URL to UTub
            return jsonify({
                "Status" : "Success",
                "Message" : "URL added to UTub",
                "URL" : {
                    "url_string": f"{validated_url}",
                    "url_ID" : f"{url_id}"
                },
                "UTub_ID" : f"{utub_id}",
                "UTub_name" : f"{utub.name}",
                "Added_by" : f"{current_user.get_id()}"
            }), 200
        
    return jsonify({
        "Status" : "Failure",
        "Message" : "Unable to add this URL",
        "Error_code": 4
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
