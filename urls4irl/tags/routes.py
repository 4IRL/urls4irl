from flask import Blueprint, jsonify
from flask_login import current_user, login_required
from urls4irl import db
from urls4irl.models import Utub, Url_Tags, Tags, Utub_Urls
from urls4irl.tags.forms import UTubNewUrlTagForm

tags = Blueprint('tags', __name__)

@tags.route('/tag/add/<int:utub_id>/<int:url_id>', methods=["POST"])
@login_required
def add_tag(utub_id: int, url_id: int):
    """
    User wants to add a tag to a URL. 5 tags per URL.
    # TODO: Do not allow empty tags
    
    Args:
        utub_id (int): The utub that this user is being added to
        url_id (int): The URL this user wants to add a tag to
    """
    utub = Utub.query.get_or_404(utub_id)
    utub_url = [url_in_utub for url_in_utub in utub.utub_urls if url_in_utub.url_id == url_id]
    user_in_utub = [int(member.user_id) for member in utub.members if int(member.user_id) == int(current_user.get_id())]

    if not user_in_utub or not utub_url:
        # How did a user not in this utub get access to add a tag to this URL?
        # How did a user try to add a tag to a URL not contained within the UTub?
        return jsonify({
            "Status" : "Failure",
            "Message" : "Unable to add tag to this URL",
            "Error_code" : 1
        }), 404
       
    url_tag_form = UTubNewUrlTagForm()

    if url_tag_form.validate_on_submit():

        tag_to_add = url_tag_form.tag_string.data

        # If too many tags, disallow adding tag
        tags_already_on_this_url = [tags for tags in utub.utub_url_tags if int(tags.url_id) == int(url_id)]

        if len(tags_already_on_this_url) > 4:
                # Cannot have more than 5 tags on a URL
                return jsonify({
                    "Status" : "Failure",
                    "Message" : "URLs can only have 5 tags max",
                    "Error_code" : 2
                }), 400

        # If not a tag already, create it
        tag_already_created = Tags.query.filter_by(tag_string=tag_to_add).first()

        if tag_already_created:
            # Check if tag already on url
            this_tag_is_already_on_this_url = [tags for tags in tags_already_on_this_url if int(tags.tag_id) == int(tag_already_created.id)]

            if this_tag_is_already_on_this_url:
                # Tag is already on this URL
                return jsonify({
                    "Status" : "Failure",
                    "Message" : "URL already has this tag",
                    "Error_code" : 3
                }), 400

            # Associate with the UTub and URL
            utub_url_tag = Url_Tags(utub_id=utub_id, url_id=url_id, tag_id=tag_already_created.id)
            tag_id = tag_already_created.id

        else:
            # Create tag, then associate with this UTub and URL
            new_tag = Tags(tag_string=tag_to_add, created_by=int(current_user.get_id()))
            db.session.add(new_tag)
            db.session.commit()
            utub_url_tag = Url_Tags(utub_id=utub_id, url_id=url_id, tag_id=new_tag.id)
            tag_id = new_tag.id

        db.session.add(utub_url_tag)
        db.session.commit()

        # Successfully added tag to URL on UTub
        url_utub_association = Utub_Urls.query.filter(Utub_Urls.utub_id == utub_id,
                                                        Utub_Urls.url_id == url_id).first_or_404()

        return jsonify({
            "Status" : "Success",
            "Message" : "Tag added to this URL",
            "Tag" : new_tag.serialized,  # Can I just serialize the Tag model here instead?
            "URL_ID" : url_utub_association.serialized, # Can I just serialize the Url_Utub model here instead?
            "UTub_ID" : f"{utub_id}"
        }), 200

    # Input form errors
    if url_tag_form.errors is not None:
        return jsonify({
            "Status" : "Failure",
            "Message" : "Unable to add tag to this URL",
            "Error_code" : 4,
            "Errors": url_tag_form.errors
        }), 404

    return jsonify({
        "Status" : "Failure",
        "Message" : "Unable to add tag to this URL",
        "Error_code" : 5
    }), 404

@tags.route('/tag/remove/<int:utub_id>/<int:url_id>/<int:tag_id>', methods=["POST"])
@login_required
def remove_tag(utub_id: int, url_id: int, tag_id: int):
    """
    User wants to delete a tag from a URL contained in a UTub. Only available to owner of that utub.

    TODO -> Have everybody remove tag!

    Args:
        utub_id (int): The ID of the UTub that contains the URL to be deleted
        url_id (int): The ID of the URL to be deleted
        tag_id (int): The ID of the tag
    """
    utub = Utub.query.get_or_404(int(utub_id))

    if int(current_user.get_id()) in [int(user.id) for user in utub.members]:
        # User is creator of this UTub
        tag_for_url_in_utub = Url_Tags.query.filter_by(utub_id=utub_id, url_id=url_id, tag_id=tag_id).first_or_404()
        tag_to_remove = tag_for_url_in_utub.tag_item
        url_to_remove_tag_from = tag_for_url_in_utub.tagged_url

        db.session.delete(tag_for_url_in_utub)
        db.session.commit()

        url_utub_association = Utub_Urls.query.filter(Utub_Urls.utub_id == utub.id, 
                                                        Utub_Urls.url_id == url_to_remove_tag_from.id).first_or_404()

        return jsonify({
            "Status" : "Success",
            "Message" : "Tag removed from URL",
            "Tag": tag_to_remove.serialized,
            "URL": url_utub_association.serialized,
            "UTub_ID": f"{utub_id}",
            "UTub_name": f"{utub.name}" 
        }), 200

    return jsonify({
        "Status" : "Failure",
        "Message" : "Only UTub members can remove tags"
    }), 403
