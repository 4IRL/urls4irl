from flask import Blueprint, jsonify
from flask_login import current_user

from src import db
from src.models.tags import Tags
from src.models.url_tags import Url_Tags
from src.models.utubs import Utubs
from src.models.utub_urls import Utub_Urls
from src.tags.forms import UTubNewUrlTagForm
from src.utils.strings.json_strs import STD_JSON_RESPONSE
from src.utils.strings.model_strs import MODELS
from src.utils.strings.tag_strs import TAGS_FAILURE, TAGS_NO_CHANGE, TAGS_SUCCESS
from src.utils.email_validation import email_validation_required

tags = Blueprint("tags", __name__)

# Standard response for JSON messages
STD_JSON = STD_JSON_RESPONSE


@tags.route("/utubs/<int:utub_id>/urls/<int:url_id>/tags", methods=["POST"])
@email_validation_required
def add_tag(utub_id: int, url_id: int):
    """
    User wants to add a tag to a URL. 5 tags per URL.
    # TODO: Do not allow empty tags

    Args:
        utub_id (int): The utub that this user is being added to
        url_id (int): The URL this user wants to add a tag to
    """
    utub_url_association = Utub_Urls.query.filter(
        Utub_Urls.utub_id == utub_id, Utub_Urls.url_id == url_id
    ).first_or_404()
    utub = utub_url_association.utub

    user_in_utub = [
        member.user_id for member in utub.members if member.user_id == current_user.id
    ]

    if not user_in_utub:
        # How did a user not in this utub get access to add a tag to this URL?
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: TAGS_FAILURE.UNABLE_TO_ADD_TAG_TO_URL,
                    STD_JSON.ERROR_CODE: 1,
                }
            ),
            403,
        )

    url_tag_form = UTubNewUrlTagForm()

    if url_tag_form.validate_on_submit():
        tag_to_add = url_tag_form.tag_string.data

        # If too many tags, disallow adding tag
        tags_already_on_this_url = [
            tags for tags in utub.utub_url_tags if tags.url_id == url_id
        ]

        if len(tags_already_on_this_url) >= 5:
            # Cannot have more than 5 tags on a URL
            return (
                jsonify(
                    {
                        STD_JSON.STATUS: STD_JSON.FAILURE,
                        STD_JSON.MESSAGE: TAGS_FAILURE.FIVE_TAGS_MAX,
                        STD_JSON.ERROR_CODE: 2,
                    }
                ),
                400,
            )

        # If not a tag already, create it
        tag_already_created = Tags.query.filter_by(tag_string=tag_to_add).first()

        if tag_already_created:
            # Check if tag already on url
            this_tag_is_already_on_this_url = [
                tags
                for tags in tags_already_on_this_url
                if tags.tag_id == tag_already_created.id
            ]

            if len(this_tag_is_already_on_this_url) == 1:
                # Tag is already on this URL
                return (
                    jsonify(
                        {
                            STD_JSON.STATUS: STD_JSON.FAILURE,
                            STD_JSON.MESSAGE: TAGS_FAILURE.TAG_ALREADY_ON_URL,
                            STD_JSON.ERROR_CODE: 3,
                        }
                    ),
                    400,
                )

            # Associate with the UTub and URL
            utub_url_tag = Url_Tags(
                utub_id=utub_id, url_id=url_id, tag_id=tag_already_created.id
            )
            tag_model = tag_already_created

        else:
            # Create tag, then associate with this UTub and URL
            new_tag = Tags(tag_string=tag_to_add, created_by=current_user.id)
            db.session.add(new_tag)
            db.session.commit()
            utub_url_tag = Url_Tags(utub_id=utub_id, url_id=url_id, tag_id=new_tag.id)
            tag_model = new_tag

        db.session.add(utub_url_tag)
        db.session.commit()

        # Successfully added tag to URL on UTub
        url_utub_association: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id, Utub_Urls.url_id == url_id
        ).first_or_404()

        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.SUCCESS,
                    STD_JSON.MESSAGE: TAGS_SUCCESS.TAG_ADDED_TO_URL,
                    TAGS_SUCCESS.URL_TAGS: url_utub_association.associated_tags,
                    TAGS_SUCCESS.TAG: tag_model.serialized,
                }
            ),
            200,
        )

    # Input form errors
    if url_tag_form.errors is not None:
        errors = {MODELS.TAG_STRING: url_tag_form.tag_string.errors}
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: TAGS_FAILURE.UNABLE_TO_ADD_TAG_TO_URL,
                    STD_JSON.ERROR_CODE: 4,
                    STD_JSON.ERRORS: errors,
                }
            ),
            400,
        )

    return (
        jsonify(
            {
                STD_JSON.STATUS: STD_JSON.FAILURE,
                STD_JSON.MESSAGE: TAGS_FAILURE.UNABLE_TO_ADD_TAG_TO_URL,
                STD_JSON.ERROR_CODE: 5,
            }
        ),
        404,
    )


@tags.route(
    "/utubs/<int:utub_id>/urls/<int:url_id>/tags/<int:tag_id>", methods=["DELETE"]
)
@email_validation_required
def remove_tag(utub_id: int, url_id: int, tag_id: int):
    """
    User wants to delete a tag from a URL contained in a UTub. Only available to owner of that utub.

    Args:
        utub_id (int): The ID of the UTub that contains the URL to be deleted
        url_id (int): The ID of the URL containing tag to be deleted
        tag_id (int): The ID of the tag to be deleted
    """
    utub = Utubs.query.get_or_404(utub_id)

    if current_user.id not in [user.user_id for user in utub.members]:
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: TAGS_FAILURE.ONLY_UTUB_MEMBERS_REMOVE_TAGS,
                }
            ),
            403,
        )

    # User is member of this UTub
    tag_for_url_in_utub = Url_Tags.query.filter_by(
        utub_id=utub_id, url_id=url_id, tag_id=tag_id
    ).first_or_404()
    url_to_remove_tag_from = tag_for_url_in_utub.tagged_url
    tag_to_remove = tag_for_url_in_utub.tag_item

    db.session.delete(tag_for_url_in_utub)
    db.session.commit()

    num_left_in_utub: int = Url_Tags.query.filter_by(
        utub_id=utub_id, tag_id=tag_id
    ).count()

    url_utub_association = Utub_Urls.query.filter(
        Utub_Urls.utub_id == utub.id, Utub_Urls.url_id == url_to_remove_tag_from.id
    ).first_or_404()

    return (
        jsonify(
            {
                STD_JSON.STATUS: STD_JSON.SUCCESS,
                STD_JSON.MESSAGE: TAGS_SUCCESS.TAG_REMOVED_FROM_URL,
                TAGS_SUCCESS.URL_TAGS: url_utub_association.associated_tags,
                TAGS_SUCCESS.TAG_STILL_IN_UTUB: True if num_left_in_utub > 0 else False,
                TAGS_SUCCESS.TAG: tag_to_remove.serialized,
            }
        ),
        200,
    )


@tags.route("/utubs/<int:utub_id>/urls/<int:url_id>/tags/<int:tag_id>", methods=["PUT"])
@email_validation_required
def modify_tag_on_url(utub_id: int, url_id: int, tag_id: int):
    """
    User wants to modify an existing tag on a URL

    Args:
        utub_id (int): The ID of the UTub that contains the URL to be modified
        url_id (int): The ID of the URL containing tag to be modified
        tag_id (int): The ID of the tag to be modified
    """
    utub: Utubs = Utubs.query.get_or_404(utub_id)

    # Verify user is in UTub
    if current_user.id not in [user.user_id for user in utub.members]:
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: TAGS_FAILURE.ONLY_UTUB_MEMBERS_MODIFY_TAGS,
                    STD_JSON.ERROR_CODE: 1,
                }
            ),
            403,
        )

    tag_on_url_in_utub: Url_Tags = Url_Tags.query.filter_by(
        utub_id=utub_id, url_id=url_id, tag_id=tag_id
    ).first_or_404()

    url_tag_form = UTubNewUrlTagForm()

    if url_tag_form.validate_on_submit():
        new_tag = url_tag_form.tag_string.data

        # Identical tag
        if new_tag == tag_on_url_in_utub.tag_item.tag_string:
            return (
                jsonify(
                    {
                        STD_JSON.STATUS: STD_JSON.NO_CHANGE,
                        STD_JSON.MESSAGE: TAGS_NO_CHANGE.TAG_NOT_MODIFIED,
                    }
                ),
                200,
            )

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
            tag_on_url = Url_Tags.query.filter_by(
                utub_id=utub_id, url_id=url_id, tag_id=tag_that_already_exists.id
            ).first()
            if tag_on_url is not None:
                return (
                    jsonify(
                        {
                            STD_JSON.STATUS: STD_JSON.FAILURE,
                            STD_JSON.MESSAGE: TAGS_FAILURE.TAG_ALREADY_ON_URL,
                            STD_JSON.ERROR_CODE: 2,
                        }
                    ),
                    400,
                )

        tag_on_url_in_utub.tag_id = tag_that_already_exists.id
        tag_on_url_in_utub.tag_item = tag_that_already_exists

        url_utub_association: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub.id, Utub_Urls.url_id == url_id
        ).first_or_404()

        db.session.commit()

        previous_tag_count_in_utub: int = Url_Tags.query.filter_by(
            utub_id=utub_id, tag_id=tag_id
        ).count()

        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.SUCCESS,
                    STD_JSON.MESSAGE: TAGS_SUCCESS.TAG_MODIFIED_ON_URL,
                    TAGS_SUCCESS.URL_TAGS: url_utub_association.associated_tags,
                    TAGS_SUCCESS.TAG: tag_that_already_exists.serialized,
                    TAGS_SUCCESS.PREVIOUS_TAG: {
                        MODELS.ID: tag_id,
                        TAGS_SUCCESS.TAG_IN_UTUB: previous_tag_count_in_utub > 0,
                    },
                }
            ),
            200,
        )

    # Input form errors
    if url_tag_form.errors is not None:
        errors = {MODELS.TAG_STRING: url_tag_form.tag_string.errors}
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: TAGS_FAILURE.UNABLE_TO_ADD_TAG_TO_URL,
                    STD_JSON.ERROR_CODE: 3,
                    STD_JSON.ERRORS: errors,
                }
            ),
            400,
        )

    return (
        jsonify(
            {
                STD_JSON.STATUS: STD_JSON.FAILURE,
                STD_JSON.MESSAGE: TAGS_FAILURE.UNABLE_TO_ADD_TAG_TO_URL,
                STD_JSON.ERROR_CODE: 4,
            }
        ),
        404,
    )
