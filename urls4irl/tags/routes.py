from flask import Blueprint, jsonify
from flask_login import current_user, login_required
from urls4irl import db
from urls4irl.models import Utub, Url_Tags, Tags, Utub_Urls, URLS
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
    utub_url_association = Utub_Urls.query.filter(Utub_Urls.utub_id == utub_id, Utub_Urls.url_id == url_id).first_or_404()
    utub = utub_url_association.utub

    user_in_utub = [int(member.user_id) for member in utub.members if int(member.user_id) == int(current_user.get_id())]

    if not user_in_utub:
        # How did a user not in this utub get access to add a tag to this URL?
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

            if len(this_tag_is_already_on_this_url) == 1:
                # Tag is already on this URL
                return jsonify({
                    "Status" : "Failure",
                    "Message" : "URL already has this tag",
                    "Error_code" : 3
                }), 400

            # Associate with the UTub and URL
            utub_url_tag = Url_Tags(utub_id=utub_id, url_id=url_id, tag_id=tag_already_created.id)
            tag_model = tag_already_created

        else:
            # Create tag, then associate with this UTub and URL
            new_tag = Tags(tag_string=tag_to_add, created_by=int(current_user.get_id()))
            db.session.add(new_tag)
            db.session.commit()
            utub_url_tag = Url_Tags(utub_id=utub_id, url_id=url_id, tag_id=new_tag.id)
            tag_model = new_tag

        db.session.add(utub_url_tag)
        db.session.commit()

        # Successfully added tag to URL on UTub
        url_utub_association = Utub_Urls.query.filter(Utub_Urls.utub_id == utub_id,
                                                        Utub_Urls.url_id == url_id).first_or_404()

        return jsonify({
            "Status" : "Success",
            "Message" : "Tag added to this URL",
            "Tag" : tag_model.serialized,  # Can I just serialize the Tag model here instead?
            "URL" : url_utub_association.serialized, # Can I just serialize the Url_Utub model here instead?
            "UTub_ID" : utub.id,
            "UTub_name": utub.name
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

    # TODO : Indicate that tag no longer exists in UTub
    
    Args:
        utub_id (int): The ID of the UTub that contains the URL to be deleted
        url_id (int): The ID of the URL containing tag to be deleted
        tag_id (int): The ID of the tag to be deleted
    """
    utub = Utub.query.get_or_404(utub_id)

    if int(current_user.get_id()) in [user.user_id for user in utub.members]:
        # User is member of this UTub
        tag_for_url_in_utub = Url_Tags.query.filter_by(utub_id=utub_id, url_id=url_id, tag_id=tag_id).first_or_404()
        url_to_remove_tag_from = tag_for_url_in_utub.tagged_url
        tag_to_remove = tag_for_url_in_utub.tag_item

        db.session.delete(tag_for_url_in_utub)
        db.session.commit()

        num_left_in_utub = Url_Tags.query.filter_by(utub_id=utub_id, tag_id=tag_id).count()

        url_utub_association = Utub_Urls.query.filter(Utub_Urls.utub_id == utub.id, 
                                                        Utub_Urls.url_id == url_to_remove_tag_from.id).first_or_404()

        return jsonify({
            "Status" : "Success",
            "Message" : "Tag removed from URL",
            "Tag": tag_to_remove.serialized,
            "URL": url_utub_association.serialized,
            "UTub_ID": utub_id,
            "UTub_name": utub.name,
            "Count_in_UTub": num_left_in_utub 
        }), 200

    return jsonify({
        "Status" : "Failure",
        "Message" : "Only UTub members can remove tags"
    }), 403

@tags.route('/tag/url/modify/<int:utub_id>/<int:url_id>/<int:tag_id>', methods=["POST"])
@login_required
def modify_tag_on_url(utub_id: int, url_id: int, tag_id: int):
    """
    User wants to modify an existing tag on a URL

    Args:
        utub_id (int): The ID of the UTub that contains the URL to be modified
        url_id (int): The ID of the URL containing tag to be modified
        tag_id (int): The ID of the tag to be modified
    """
    utub = Utub.query.get_or_404(utub_id)

    # Verify user is in UTub
    if int(current_user.get_id()) not in [user.user_id for user in utub.members]:
        return jsonify({
            "Status" : "Failure", 
            "Message" : "Only UTub members can modify tags",
            "Error_code" : 1
        }), 404

    tag_on_url_in_utub = Url_Tags.query.filter_by(utub_id=utub_id, url_id=url_id, tag_id=tag_id).first_or_404()

    url_tag_form = UTubNewUrlTagForm()

    if url_tag_form.validate_on_submit():
        new_tag = url_tag_form.tag_string.data

        # Identical tag
        if new_tag == tag_on_url_in_utub.tag_item.tag_string:
            return jsonify({
                "Status" : "No change",
                "Message" : "Tag was not modified on this URL"
            }), 200

        tag_that_already_exists = Tags.query.filter_by(tag_string=new_tag).first()

        # Check if tag already in database
        if tag_that_already_exists is None:
            # Need to make a new tag
            new_tag = Tags(tag_string=new_tag, created_by=current_user.id)
            db.session.add(new_tag)
            db.session.commit()

            tag_that_already_exists = new_tag

        else:
            # Check if tag already on URL
            tag_on_url = Url_Tags.query.filter_by(utub_id=utub_id, url_id=url_id, tag_id=tag_that_already_exists.id).first()
            if tag_on_url is not None:
                return jsonify({
                    "Status" : "Failure", 
                    "Message" : "Tag already on URL",
                    "Error_code" : 2
                }), 404
            
        tag_on_url_in_utub.tag_id = tag_that_already_exists.id
        tag_on_url_in_utub.tag_item = tag_that_already_exists

        url_utub_association = Utub_Urls.query.filter(Utub_Urls.utub_id == utub.id, 
                                                        Utub_Urls.url_id == url_id).first_or_404()

        return jsonify({
            "Status" : "Success",
            "Message" : "Tag modified on URL",
            "Tag" : tag_that_already_exists.serialized,
            "URL": url_utub_association.serialized,
            "UTub_ID": utub_id,
            "UTub_name": utub.name 
        }), 200

    # Input form errors
    if url_tag_form.errors is not None:
        return jsonify({
            "Status" : "Failure",
            "Message" : "Unable to add tag to this URL",
            "Error_code" : 3,
            "Errors": url_tag_form.errors
        }), 404

    return jsonify({
        "Status" : "Failure",
        "Message" : "Unable to add tag to this URL",
        "Error_code" : 4
    }), 404
    
